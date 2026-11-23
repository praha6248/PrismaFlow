"""Tests for the Deliver phase: flow audit, suggestions and handoff."""

import math
from typing import Any

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import Database
from backend.models import Flow, FlowDraft
from backend.ollama_client import OllamaError
from backend.services import discover
from backend.services.deliver import (
    DeliverService,
    apply_suggestion,
    audit,
    fallback_suggestions,
    fitts_index,
    from_draft,
    hick_time,
    klm_time,
    movement_time,
)

from .conftest import FakeLLM


def sample_flow() -> Flow:
    return Flow.model_validate(
        {
            "screens": [
                {
                    "id": "s1",
                    "name": "Start",
                    "kind": "start",
                    "elements": [
                        {"id": "e1", "label": "Wybierz plan", "size": "L", "zone": "bottom", "target": "s2"},
                        {"id": "e2", "label": "Ustawienia", "type": "link", "size": "S", "zone": "top", "target": "s4"},
                        {"id": "e3", "label": "Kategorie", "type": "list", "options": 9},
                    ],
                },
                {
                    "id": "s2",
                    "name": "Plan tygodnia",
                    "elements": [{"id": "e4", "label": "Rozpocznij", "size": "M", "zone": "bottom", "target": "s3"}],
                },
                {
                    "id": "s3",
                    "name": "Trening",
                    "kind": "goal",
                    "elements": [{"id": "e5", "label": "Pomiń", "type": "link", "size": "S", "zone": "top"}],
                },
                {"id": "s4", "name": "Ustawienia", "elements": [{"id": "e6", "label": "Język", "type": "select"}]},
                {"id": "s5", "name": "Sierota", "elements": []},
            ]
        }
    )


def test_laws() -> None:
    assert math.isclose(hick_time(11), 0.25 + 0.15 * math.log2(12))
    assert math.isclose(fitts_index("S", "top"), math.log2(2 * 560 / 24))
    assert fitts_index("L", "bottom") < 2.5


def test_audit_reports_every_metric() -> None:
    report = audit(sample_flow())
    assert report["steps"] == {"value": 2, "path": ["Start", "Plan tygodnia", "Trening"], "status": "ok"}
    assert report["transitions"] == 3
    assert report["hick"][0]["screen"] == "Start" and report["hick"][0]["element"] == "Kategorie"
    assert report["hick"][0]["options"] == 9 and report["hick"][0]["warning"] and report["hick"][0]["hide"] == 4
    actions = next(h for h in report["hick"] if h["element"] is None)
    assert actions["screen"] == "Start" and actions["options"] == 2 and not actions["warning"]
    assert report["klm"]["steps"][0]["seconds"] == round(1.35 + hick_time(2) + movement_time("L", "bottom"), 2)
    assert {f["element"] for f in report["fitts"]} == {"Ustawienia", "Pomiń"}
    assert [d["screen"] for d in report["dead_ends"]] == ["Ustawienia", "Sierota"]
    assert [d["screen"] for d in report["unreachable"]] == ["Sierota"]
    assert report["klm"]["seconds"] > 2 * 1.35
    assert [s["element"] for s in report["klm"]["steps"]] == ["Wybierz plan", "Rozpocznij"]
    targets = report["targets"]
    assert targets["total"] == 6 and targets["aa"] == 6 and targets["aaa"] == 1
    assert {t["element"] for t in targets["below_aaa"] if t["primary"]} == {"Ustawienia", "Rozpocznij"}


def test_klm_needs_a_path() -> None:
    assert klm_time(sample_flow(), ["s1"]) is None


def test_fallback_suggestions_fix_the_flow() -> None:
    flow = sample_flow()
    report = audit(flow)
    suggestions = fallback_suggestions(report, flow)
    ops = [s["op"] for s in suggestions]
    assert ops[0] == "add_transition" and "move_zone" in ops and "group_options" in ops and "resize" in ops
    for suggestion in suggestions:
        flow = apply_suggestion(flow, suggestion)
    after = audit(flow)
    assert len(after["dead_ends"]) < len(report["dead_ends"])
    assert len(after["fitts"]) < len(report["fitts"])
    assert all(not h["warning"] for h in after["hick"])


def test_draft_resolves_targets_and_features() -> None:
    draft = FlowDraft.model_validate(
        {
            "screens": [
                {"name": "Start", "kind": "start", "features": [], "elements": [{"label": "dalej", "type": "button", "size": "L", "zone": "bottom", "options": 1, "target": "plan"}]},
                {"name": "Plan", "kind": "step", "features": ["Elastyczny plan"], "elements": [{"label": "Start", "type": "button", "size": "L", "zone": "bottom", "options": 1, "target": "Cel"}]},
                {"name": "Cel", "kind": "step", "features": [], "elements": [{"label": "Zapisz", "type": "button", "size": "L", "zone": "bottom", "options": 1, "target": ""}]},
            ]
        }
    )
    flow = from_draft(draft, [{"id": 7, "title": "Elastyczny plan"}])
    assert [s.kind for s in flow.screens] == ["start", "step", "goal"]
    assert flow.screens[0].elements[0].target == flow.screens[1].id
    assert flow.screens[0].elements[0].label == "Dalej"
    assert flow.screens[1].feature_ids == [7]
    assert [s.x for s in flow.screens] == [0, 250, 500]
    assert audit(flow)["steps"]["value"] == 2


class FlowLLM(FakeLLM):
    async def structured(self, schema: Any, system: str, prompt: str, **_: Any) -> Any:
        if schema.__name__ == "FlowDraft":
            return schema.model_validate(
                {
                    "screens": [
                        {"name": "Start", "kind": "start", "features": ["Plan"], "elements": [{"label": "Dalej", "type": "button", "size": "S", "zone": "top", "options": 1, "target": "Cel"}]},
                        {"name": "Cel", "kind": "goal", "features": [], "elements": [{"label": "Gotowe", "type": "button", "size": "L", "zone": "bottom", "options": 1, "target": ""}]},
                        {"name": "Pomoc", "kind": "step", "features": [], "elements": [{"label": "Czytaj", "type": "link", "size": "S", "zone": "center", "options": 1, "target": ""}]},
                    ]
                }
            )
        if schema.__name__ == "SuggestionSet":
            return schema.model_validate(
                {
                    "suggestions": [
                        {"title": "Przenieś dalej na dół", "reason": "Fitts", "op": "move_zone", "screen": "start", "element": "dalej", "value": "bottom"},
                        {"title": "Zła", "reason": "x", "op": "resize", "screen": "Nieistnieje", "element": "x", "value": "L"},
                    ]
                }
            )
        raise OllamaError("offline")


def _deliver_client(tmp_path, llm) -> tuple[TestClient, Database]:
    db = Database(":memory:")
    app = create_app(
        db=db,
        llm=FakeLLM(),
        service=discover.DiscoverService(db, llm),
        deliver_service=DeliverService(db, llm, export_root=tmp_path / "exports"),
        frontend_dist=tmp_path,
    )
    return TestClient(app), db


def _wait(client: TestClient, job: dict) -> dict:
    for _ in range(200):
        state = client.get(f"/api/jobs/{job['id']}").json()
        if state["status"] != "running":
            return state
    raise AssertionError("job did not finish")


def test_deliver_endpoints(tmp_path) -> None:
    client, db = _deliver_client(tmp_path, FlowLLM())
    with client:
        project_id = client.post("/api/projects", json={"seed": "sport"}).json()["project"]["id"]
        assert client.post("/api/deliver/flow", json={"project_id": project_id}).status_code == 400
        client.post(f"/api/projects/{project_id}/features", json={"title": "Plan", "priority": "must"})

        state = _wait(client, client.post("/api/deliver/flow", json={"project_id": project_id}).json())
        assert state["status"] == "done", state
        result = state["result"]
        assert result["project"]["phase"] == "deliver"
        assert result["audit"]["steps"]["value"] == 1
        assert result["flow"]["screens"][0]["feature_ids"] == [result["features"][0]["id"]]

        state = _wait(client, client.post("/api/deliver/optimize", json={"project_id": project_id}).json())
        suggestions = state["result"]["suggestions"]
        assert suggestions[0]["title"] == "Przenieś dalej na dół" and suggestions[0]["value"] == "bottom"
        assert all(s["title"] != "Zła" for s in suggestions) and len(suggestions) >= 2

        accepted = client.post(f"/api/projects/{project_id}/suggestions/{suggestions[0]['id']}/accept").json()
        start = accepted["flow"]["screens"][0]["elements"][0]
        assert start["zone"] == "bottom" and len(accepted["suggestions"]) == len(suggestions) - 1
        dismissed = client.delete(f"/api/projects/{project_id}/suggestions/{suggestions[1]['id']}").json()
        assert len(dismissed["suggestions"]) == len(suggestions) - 2

        flow = accepted["flow"]
        flow["screens"][2]["elements"][0]["target"] = "missing"
        saved = client.put(f"/api/projects/{project_id}/flow", json={"flow": flow}).json()
        assert saved["flow"]["screens"][2]["elements"][0]["target"] is None

        pack = client.post(f"/api/projects/{project_id}/handoff").json()
        assert "Start" in pack["figma_prompt"] and "MoSCoW" in pack["claude_md"]
        assert "KLM" in pack["claude_md"] and "WCAG" in pack["claude_md"]
        assert (tmp_path / "exports" / "sport" / "CLAUDE.md").is_file()


def test_optimize_falls_back_without_the_model(tmp_path) -> None:
    client, db = _deliver_client(tmp_path, FakeLLM(fail=True))
    with client:
        project_id = client.post("/api/projects", json={"seed": "sport"}).json()["project"]["id"]
        client.put(f"/api/projects/{project_id}/flow", json={"flow": sample_flow().model_dump()})
        state = _wait(client, client.post("/api/deliver/optimize", json={"project_id": project_id}).json())
        assert state["status"] == "done"
        assert state["result"]["suggestions"][0]["op"] == "add_transition"
