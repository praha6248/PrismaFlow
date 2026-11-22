"""Tests for the Develop phase backlog and MoSCoW board."""

from typing import Any

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import Database
from backend.services import discover
from backend.services.define import DefineService
from backend.services.develop import DevelopService, fold, stems, support

from .conftest import FakeLLM, offline_collectors
from .test_define import SchemaLLM, _noop, _project, define_collectors

FEATURES = {
    "features": [
        {"title": "elastyczny plan tygodnia", "description": "Dopasowanie do rytmu dnia.", "priority": "must", "keywords": ["plan"], "evidence_ids": []},
        {"title": "Łagodny powrót", "description": "Prosty restart.", "priority": "must", "keywords": ["powrót"], "evidence_ids": [999]},
        {"title": "Przypomnienia", "description": "W odpowiedniej chwili.", "priority": "should", "keywords": ["przypomnienie"], "evidence_ids": []},
        {"title": "Małe postępy", "description": "Docenienie regularności.", "priority": "should", "keywords": ["postęp"], "evidence_ids": []},
        {"title": "Trening z przyjaciółką", "description": "Wspólne cele.", "priority": "could", "keywords": ["przyjaciel"], "evidence_ids": []},
        {"title": "Wyzwania", "description": "Krótkie wyzwania.", "priority": "could", "keywords": ["wyzwanie"], "evidence_ids": []},
        {"title": "Ranking publiczny", "description": "Porównanie wyników.", "priority": "wont", "keywords": ["ranking"], "evidence_ids": []},
    ]
}


class BacklogLLM(SchemaLLM):
    """Adds the canned feature backlog to the Define fake."""

    async def structured(self, schema: Any, system: str, prompt: str, **kwargs: Any) -> Any:
        if schema.__name__ == "FeatureSet":
            self.prompts.append(prompt)
            return schema.model_validate(FEATURES)
        return await super().structured(schema, system, prompt, **kwargs)


async def _defined(db: Database, llm: SchemaLLM) -> int:
    project_id = await _project(db)
    service = DefineService(db, llm, define_collectors())
    state = await service.generate_problems(project_id, _noop, _noop)
    db.choose_problem(state["problems"][0]["id"])
    state = await service.generate_personas(project_id, _noop, _noop)
    db.choose_persona(state["personas"][0]["id"], 1)
    return project_id


def test_matching_helpers() -> None:
    assert fold("Łagodny POWRÓT") == "lagodny powrot"
    assert stems(["plan treningowy", "do"]) == ["plan", "treni"]
    pool = {1: {"title": "Mój plan treningów", "body": ""}, 2: {"title": "Motywacja", "body": "brak"}}
    assert support(pool, ["treningi"], [2, 7]) == [2, 1]


async def test_backlog_is_scored_against_evidence(db: Database) -> None:
    llm = BacklogLLM()
    project_id = await _defined(db, llm)
    state = await DevelopService(db, llm).generate(project_id, _noop, _noop)

    features = state["features"]
    assert [f["priority"] for f in features] == ["must", "must", "should", "should", "could", "could", "wont"]
    plan = features[0]
    assert plan["title"] == "Elastyczny plan tygodnia"
    assert plan["support"] >= 1 and plan["pool"] >= plan["support"]
    assert plan["demand"] == round(100 * plan["support"] / plan["pool"])
    assert 999 not in features[1]["evidence_ids"]
    assert state["persona"]["focus"] == "Sztywny plan"
    assert state["project"]["phase"] == "develop"
    assert "Sztywny plan" in llm.prompts[-1]


async def test_generation_requires_a_persona(db: Database) -> None:
    project_id = await _project(db)
    try:
        await DevelopService(db, BacklogLLM()).generate(project_id, _noop, _noop)
    except ValueError as exc:
        assert "persona" in str(exc)
    else:
        raise AssertionError("expected ValueError")


async def test_user_features_survive_regeneration(db: Database) -> None:
    llm = BacklogLLM()
    project_id = await _defined(db, llm)
    service = DevelopService(db, llm)
    await service.generate(project_id, _noop, _noop)
    mine = service.add(project_id, "Plan na urlop", "Trening w podróży", "could")
    assert mine["origin"] == "user" and mine["position"] == 2
    await service.generate(project_id, _noop, _noop)
    titles = [f["title"] for f in db.list_features(project_id)]
    assert "Plan na urlop" in titles and len(titles) == 8


def test_develop_endpoints(tmp_path) -> None:
    db = Database(":memory:")
    llm = BacklogLLM()
    app = create_app(
        db=db,
        llm=FakeLLM(),
        service=discover.DiscoverService(db, llm, offline_collectors()),
        define_service=DefineService(db, llm, define_collectors()),
        develop_service=DevelopService(db, llm),
        frontend_dist=tmp_path,
    )
    with TestClient(app) as client:
        project_id = client.post("/api/projects", json={"seed": "sport"}).json()["project"]["id"]
        assert client.post("/api/develop/features", json={"project_id": project_id}).status_code == 400

        created = client.post(f"/api/projects/{project_id}/features", json={"title": "Plan", "priority": "must"})
        assert created.status_code == 201
        feature = created.json()
        moved = client.put(
            f"/api/projects/{project_id}/features/order",
            json={"items": [{"id": feature["id"], "priority": "wont", "position": 0}]},
        ).json()
        assert moved[0]["priority"] == "wont"

        edited = client.patch(f"/api/features/{feature['id']}", json={"title": "Plan tygodnia"}).json()
        assert edited["title"] == "Plan tygodnia"
        assert client.patch(f"/api/features/{feature['id']}", json={"priority": "maybe"}).status_code == 422

        assert client.delete(f"/api/features/{feature['id']}").status_code == 204
        assert client.get(f"/api/projects/{project_id}/develop").json()["features"] == []
