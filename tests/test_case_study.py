"""Tests for the case study generator: grounded narrative, gaps and exported files."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import Database
from backend.models import CaseStudyDraft
from backend.ollama_client import OllamaError
from backend.services import discover, report
from backend.services.case_study import GUIDE, GUIDE_SOURCES, grounded
from backend.services.deliver import DeliverService

from .conftest import FakeLLM
from .test_deliver import sample_flow


class StoryLLM:
    """Writes every section with one true and one invented number."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.prompts: list[str] = []

    async def structured(self, schema: Any, system: str, prompt: str, **_: Any) -> Any:
        self.prompts.append(prompt)
        if self.fail:
            raise OllamaError("offline")
        assert schema is CaseStudyDraft
        text = "Zadanie ukończyła 1 z 2 osób. Konwersja wzrosła o 35%."
        return CaseStudyDraft(
            headline="Plan treningu bez zgadywania",
            summary=text,
            context=text,
            research=text,
            synthesis=text,
            ideation=text,
            design=text,
            testing=text,
            reflection=text,
        )


@pytest.fixture(autouse=True)
def no_chromium(monkeypatch) -> None:
    async def skip(html_path, pdf_path) -> bool:
        return False

    monkeypatch.setattr(report, "write_pdf", skip)


def _client(tmp_path, llm) -> tuple[TestClient, Database]:
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


def _project(client: TestClient, db: Database) -> int:
    project_id = client.post("/api/projects", json={"seed": "sport"}).json()["project"]["id"]
    client.put(f"/api/projects/{project_id}/flow", json={"flow": sample_flow().model_dump()})
    client.post(f"/api/projects/{project_id}/features", json={"title": "Plan", "priority": "must"})
    db.save_document(
        project_id,
        "board",
        {
            "notes": [{"id": "n1", "text": "Nie wiem, od czego zacząć.", "source": "interview", "label": "Ola", "theme": "t1"}],
            "themes": [{"id": "t1", "name": "Brak planu", "insight": "Ludzie nie wiedzą, od czego zacząć."}],
        },
    )
    db.save_document(
        project_id,
        "tests",
        {
            "tasks": [{"id": "k1", "goal": "s3", "scenario": "Zacznij trening."}],
            "sessions": [
                {"id": "a", "participant": "P1", "results": [{"task": "k1", "success": True, "seconds": 12.0, "path": ["s1", "s2", "s3"], "quote": "Szybko poszło"}]},
                {"id": "b", "participant": "P2", "results": [{"task": "k1", "success": False, "seconds": 30.0, "path": ["s1", "s4"], "quote": ""}]},
            ],
        },
    )
    return project_id


def test_grounded_drops_sentences_with_unknown_numbers() -> None:
    text, dropped = grounded("Sukces 1 z 2. Czas 6,8 s. Wzrost o 40%. Bez liczb.", "sukces 1 z 2; KLM 6.8 s")
    assert text == "Sukces 1 z 2. Czas 6,8 s. Bez liczb."
    assert dropped == ["Wzrost o 40%."]


def test_guide_follows_the_researched_order() -> None:
    keys = [key for key, _, _ in GUIDE]
    assert keys[0] == "summary" and keys[-1] == "reflection"
    assert keys.index("research") < keys.index("synthesis") < keys.index("design") < keys.index("testing") < keys.index("outcomes")
    assert all(url.startswith("https://") for url in GUIDE_SOURCES)


def test_case_study_is_grounded_in_project_data(tmp_path) -> None:
    llm = StoryLLM()
    client, db = _client(tmp_path, llm)
    with client:
        project_id = _project(client, db)
        state = _wait(client, client.post(f"/api/projects/{project_id}/case-study").json())
    assert state["status"] == "done", state
    result = state["result"]
    markdown = result["markdown"]
    assert "35%" not in markdown and "Konwersja wzrosła o 35%." in result["removed"]
    assert "Zadanie ukończyła 1 z 2 osób." in markdown
    assert "# Plan treningu bez zgadywania" in markdown
    assert "sukces 1 z 2 (50%)" in markdown and "„Szybko poszło” _(P1)_" in markdown
    assert "Brak planu (notatki: 1)" in markdown and "„Nie wiem, od czego zacząć.” _(Ola)_" in markdown
    assert "do uzupełnienia: Twoja rola w projekcie" in markdown
    assert "do uzupełnienia: wpływ biznesowy" in markdown
    assert result["gaps"] > 0 and result["narrative"] is True
    directory = tmp_path / "exports" / "sport"
    assert result["files"] == ["case-study.md", "case-study.html"]
    assert (directory / "case-study.md").read_text(encoding="utf-8") == markdown
    assert "<h2>Testy użyteczności</h2>" in (directory / "case-study.html").read_text(encoding="utf-8")
    assert "Missing (do not mention)" in llm.prompts[0] and "1 z 2" in llm.prompts[0]


def test_case_study_without_the_model_keeps_the_facts(tmp_path) -> None:
    client, db = _client(tmp_path, StoryLLM(fail=True))
    with client:
        project_id = _project(client, db)
        state = _wait(client, client.post(f"/api/projects/{project_id}/case-study").json())
    assert state["status"] == "done"
    assert any(w.startswith("llm:") for w in state["warnings"])
    result = state["result"]
    assert result["narrative"] is False
    assert "Konwersja" not in result["markdown"] and "sukces 1 z 2 (50%)" in result["markdown"]


def test_case_study_for_a_missing_project(tmp_path) -> None:
    client, _ = _client(tmp_path, StoryLLM())
    with client:
        assert client.post("/api/projects/999/case-study").status_code == 404
