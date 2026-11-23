"""Tests for the Define phase service and endpoints."""

from typing import Any

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.collectors import CollectorUnavailable
from backend.database import Database
from backend.services import discover
from backend.services.define import DefineCollectors, DefineService, define_state, monthly, summarize_trend

from .conftest import FakeLLM, offline_collectors

PROBLEMS = {
    "problems": [
        {
            "title": "trudno utrzymać regularność treningów",
            "description": "Brakuje prostego planu.",
            "trend_keyword": "plan treningowy",
            "quote_id": 0,
            "node_labels": ["plan"],
        },
        {
            "title": "Brakuje motywacji do ćwiczeń",
            "description": "Zapał szybko znika.",
            "trend_keyword": "motywacja",
            "quote_id": -1,
            "node_labels": ["brak motywacji"],
        },
        {
            "title": "Trening nie mieści się w planie dnia",
            "description": "Praca zabiera czas.",
            "trend_keyword": "trening w domu",
            "quote_id": 0,
            "node_labels": [],
        },
    ]
}

PROFILE = {
    "situation": "W drodze na trening po pracy.",
    "device": "Telefon, w autobusie tylko jedna ręka jest wolna.",
    "goal": "Wybrać zestaw na dzisiejszy trening.",
    "workaround": "Szuka zdjęcia planu w galerii telefonu.",
    "barrier": "Ma tylko kilka minut przed przesiadką.",
    "success": "Otwiera gotowy plan przed wejściem na salę.",
    "question": "Jak wyglądało przygotowanie do ostatniego treningu?",
}

PERSONAS = {
    "personas": [
        {"profile": PROFILE, "name": "marta", "age": 28, "role": "koordynatorka projektów", "quote": "Zaczynam z zapałem.", "problems": ["Trudno wrócić", "Sztywny plan"]},
        {"profile": PROFILE, "name": "Karolina", "age": 34, "role": "Pracująca mama", "quote": "Mam mało czasu.", "problems": ["Obowiązki", "Za długie treningi"]},
        {"profile": PROFILE, "name": "Julia", "age": 23, "role": "Studentka", "quote": "Nie wiem, od czego zacząć.", "problems": ["Sprzeczne porady", "Brak postępów"]},
    ]
}


class SchemaLLM(FakeLLM):
    """Answers with the canned payload matching the requested schema."""

    async def structured(self, schema: Any, system: str, prompt: str, **_: Any) -> Any:
        if schema.__name__ == "Translations":
            return await super().structured(schema, system, prompt)
        self.prompts.append(prompt)
        payload = PROBLEMS if schema.__name__ == "ProblemSet" else PERSONAS
        return schema.model_validate(payload)


def define_collectors(fail_trends: bool = False) -> DefineCollectors:
    async def interest(db, keywords, geo="", timeframe="today 12-m"):
        if fail_trends:
            raise CollectorUnavailable("429")
        dates = [f"2026-{(i // 4) % 12 + 1:02d}-{(i % 4) * 7 + 1:02d}" for i in range(52)]
        return {"dates": dates, "series": {k: [float(10 + i % 5 + idx) for i in range(52)] for idx, k in enumerate(keywords)}}

    return DefineCollectors(interest=interest)


async def _project(db: Database) -> int:
    project_id = discover.create_project(db, "sport")["project"]["id"]
    discover.add_node(db, project_id, "plan")
    discover.add_node(db, project_id, "brak motywacji")
    plan = db.find_node(project_id, "plan")
    db.add_evidence(project_id, plan["id"], "reddit", "Can't stick to my training plan", weight=50)
    db.update_node(plan["id"], starred=True)
    return project_id


def _noop(*_: object) -> None:
    return None


async def test_problems_are_grounded_scored_and_quoted(db: Database) -> None:
    project_id = await _project(db)
    llm = SchemaLLM()
    service = DefineService(db, llm, define_collectors())
    state = await service.generate_problems(project_id, _noop, _noop)

    problems = state["problems"]
    assert [p["title"] for p in problems][0] == "Trudno utrzymać regularność treningów"
    assert problems[0]["quote"] is None
    assert problems[0]["node_ids"] == [db.find_node(project_id, "plan")["id"]]
    assert all(p["trend"]["available"] and len(p["trend"]["months"]) == 12 for p in problems)
    markets = problems[0]["trend"]["markets"]
    assert markets["pl"]["query"] == "plan treningowy"
    assert markets["en"]["query"] == "[en] plan treningowy"
    assert markets["en"]["available"]
    assert problems[0]["trend"]["anchor"] == "kalendarz"
    assert problems[0]["trend"]["anchor_ratio"] is not None
    assert state["project"]["phase"] == "define"
    assert "Can't stick to my training plan" in llm.prompts[0]


async def test_problem_quote_prefers_selected_evidence(db: Database) -> None:
    project_id = await _project(db)
    evidence_id = db.list_evidence(db.find_node(project_id, "plan")["id"])[0]["id"]
    payload = {"problems": [dict(p, quote_id=evidence_id) for p in PROBLEMS["problems"]]}

    class Picky(SchemaLLM):
        async def structured(self, schema, system, prompt, **_):
            if schema.__name__ == "RelevantItems":
                return schema(relevant=[1])
            return schema.model_validate(payload if schema.__name__ == "ProblemSet" else PERSONAS)

    state = await DefineService(db, Picky(), define_collectors()).generate_problems(project_id, _noop, _noop)
    assert state["problems"][0]["quote"] == "Can't stick to my training plan"
    assert state["problems"][0]["quote_source"] == "reddit"
    assert all(p["quote"] is None and not p["evidence_ids"] for p in state["problems"][1:])


async def test_trends_failure_is_a_warning(db: Database) -> None:
    project_id = await _project(db)
    warnings: list[str] = []
    state = await DefineService(db, SchemaLLM(), define_collectors(fail_trends=True)).generate_problems(
        project_id, _noop, warnings.append
    )
    assert all(p["trend"]["available"] is False for p in state["problems"])
    assert warnings and warnings[0].startswith("trends:")


async def test_personas_follow_the_chosen_problem(db: Database) -> None:
    project_id = await _project(db)
    service = DefineService(db, SchemaLLM(), define_collectors())
    state = await service.generate_problems(project_id, _noop, _noop)
    chosen = db.choose_problem(state["problems"][1]["id"])
    assert chosen["chosen"] is True

    state = await service.generate_personas(project_id, _noop, _noop)
    assert state["personas"][0]["profile"] == PROFILE
    assert [p["name"] for p in state["personas"]] == ["Marta", "Karolina", "Julia"]
    assert state["chosen_problem_id"] == chosen["id"]

    persona = db.choose_persona(state["personas"][2]["id"], 1)
    assert persona["chosen_option"] == 1
    assert db.choose_persona(state["personas"][0]["id"], 5) is None
    assert [p["chosen_option"] for p in db.list_personas(chosen["id"])] == [None, None, 1]


def test_monthly_aggregation_and_summary() -> None:
    dates = ["2026-01-04", "2026-01-11", "2026-02-01"]
    assert monthly(dates, [10, 20, 30]) == [{"month": "2026-01", "value": 15.0}, {"month": "2026-02", "value": 30.0}]
    summary = summarize_trend(dates, [10, 20, 30], "kalendarz", 2.0)
    assert summary["index"] == 20 and summary["anchor_ratio"] == 2.0
    assert summarize_trend([], [], "kalendarz", None)["available"] is False


def test_define_endpoints(tmp_path) -> None:
    db = Database(":memory:")
    llm = SchemaLLM()
    app = create_app(
        db=db,
        service=discover.DiscoverService(db, llm, offline_collectors()),
        define_service=DefineService(db, llm, define_collectors()),
        frontend_dist=tmp_path,
    )
    with TestClient(app) as client:
        project_id = client.post("/api/projects", json={"seed": "sport"}).json()["project"]["id"]
        client.post(f"/api/projects/{project_id}/nodes", json={"label": "plan"})
        assert client.post("/api/define/personas", json={"project_id": project_id}).status_code == 400

        job = client.post("/api/define/problems", json={"project_id": project_id}).json()
        for _ in range(200):
            state = client.get(f"/api/jobs/{job['id']}").json()
            if state["status"] != "running":
                break
        assert state["status"] == "done", state
        problem_id = state["result"]["problems"][0]["id"]

        chosen = client.post(f"/api/problems/{problem_id}/choose").json()
        assert chosen["chosen_problem_id"] == problem_id

        job = client.post("/api/define/personas", json={"project_id": project_id}).json()
        for _ in range(200):
            state = client.get(f"/api/jobs/{job['id']}").json()
            if state["status"] != "running":
                break
        persona_id = state["result"]["personas"][0]["id"]
        picked = client.post(f"/api/personas/{persona_id}/choose", json={"option": 1}).json()
        assert picked["personas"][0]["chosen_option"] == 1
        assert client.post(f"/api/personas/{persona_id}/choose", json={"option": 3}).status_code == 422


def test_inline_schema_keeps_fields_named_title() -> None:
    from backend.models import ProblemSet
    from backend.ollama_client import inline_schema

    item = inline_schema(ProblemSet)["properties"]["problems"]["items"]
    assert "title" in item["properties"]
    assert "title" in item["required"]
    assert "title" not in item


def test_persona_ages_must_fit_their_roles() -> None:
    from backend.services.define import age_issues, fix_ages

    personas = [
        {"name": "Ania", "age": 18, "role": "Studentka pierwszego roku"},
        {"name": "Piotr", "age": 26, "role": "Rodzic, wspierający córkę"},
        {"name": "Magda", "age": 41, "role": "Doradczyni zawodowa w liceum"},
    ]
    issues = age_issues(personas)
    assert len(issues) == 1 and issues[0].startswith("Piotr")
    fixed = fix_ages(personas)
    assert fixed[1]["age"] >= 36 and fixed[0]["age"] == 18 and fixed[2]["age"] == 41
    assert age_issues(fixed) == []
    assert age_issues([{"name": "Ola", "age": 20, "role": "Nauczycielka"}, {"name": "Jan", "age": 12, "role": "Emeryt"}]) != []


async def test_problems_and_personas_cite_real_evidence(db: Database) -> None:
    project_id = await _project(db)
    evidence_id = db.list_evidence(db.find_node(project_id, "plan")["id"])[0]["id"]
    problems = {"problems": [dict(p, evidence_ids=[evidence_id, 99999]) for p in PROBLEMS["problems"]]}
    personas = {"personas": [dict(p, evidence_ids=[evidence_id] if i else []) for i, p in enumerate(PERSONAS["personas"])]}

    class Citing(SchemaLLM):
        async def structured(self, schema, system, prompt, **_):
            self.prompts.append(prompt)
            if schema.__name__ == "RelevantItems":
                return schema(relevant=[1, 2, 3])
            return schema.model_validate(problems if schema.__name__ == "ProblemSet" else personas)

    llm = Citing()
    service = DefineService(db, llm, define_collectors())
    state = await service.generate_problems(project_id, _noop, _noop)
    assert [p["evidence_ids"] for p in state["problems"]] == [[evidence_id], [], []]
    assert state["problems"][0]["evidence"][0]["title"] == "Can't stick to my training plan"

    db.choose_problem(state["problems"][0]["id"])
    state = await service.generate_personas(project_id, _noop, _noop)
    assert "cites no evidence" in llm.prompts[-1]
    assert [len(p["evidence"]) for p in state["personas"]] == [0, 1, 1]


def test_saved_persona_excludes_unrelated_news_and_search_suggestions(db: Database) -> None:
    project = discover.create_project(db, "i")["project"]["id"]
    node = db.root_node(project)["id"]
    db.replace_problems(project, [dict(title="Dzieci otrzymują nieodpowiednie treści AI", description="", keyword="dzieci", node_ids=[], evidence_ids=[])])
    problem = db.list_problems(project)[0]
    db.choose_problem(problem["id"])
    titles = [
        ("community", "Minister nazywa broń zabawkami dla dzieci"),
        ("community", "Łódź z zabawkami dla głodujących dzieci"),
        ("autocomplete", "Zabawki AI dla dzieci"),
        ("community", "Jak chronić dzieci przed nieodpowiednimi treściami AI w zabawkach?"),
    ]
    for source, title in titles:
        db.add_evidence(project, node, source, title)
    ids = [e["id"] for e in db.list_evidence(node)]
    db.replace_personas(project, problem["id"], [dict(name="Marcin", age=46, role="Tata", quote="Co usłyszy moje dziecko?", options=["A", "B"], evidence_ids=ids)])
    persona = define_state(db, project)["personas"][0]
    assert [e["title"] for e in persona["evidence"]] == [titles[-1][1]]
    assert persona["evidence_ids"] == [persona["evidence"][0]["id"]]


def test_saved_search_suggestion_cannot_be_a_problem_quote(db: Database) -> None:
    project = discover.create_project(db, "Planowanie posiłków dla jednej osoby")["project"]["id"]
    root = db.root_node(project)["id"]
    hint = "resztki świetności budowli warownej"
    db.add_evidence(project, root, "autocomplete", hint)
    evidence_id = db.list_evidence(root)[0]["id"]
    db.replace_problems(project, [dict(
        title="Trudno wykorzystać resztki z obiadu", description="", keyword="resztki",
        quote=hint, quote_source="autocomplete", evidence_ids=[evidence_id], node_ids=[],
    )])
    problem = define_state(db, project)["problems"][0]
    assert problem["quote"] is None and problem["quote_source"] is None
    assert problem["evidence"] == []
    assert db.list_evidence(root)[0]["title"] == hint


def test_saved_news_about_food_waste_does_not_support_portion_sizes(db: Database) -> None:
    project = discover.create_project(db, "Planowanie posiłków dla jednej osoby")["project"]["id"]
    title = "Opóźnienia w wypłatach SNAP a miliardy dolarów zmarnowanego jedzenia"
    node = db.root_node(project)["id"]
    db.add_evidence(project, node, "community", title)
    news = db.list_evidence(node)[0]
    db.replace_problems(project, [dict(
        title="Przepisy dają zbyt duże porcje", description="", keyword="przepis na jedną osobę",
        quote=title, quote_source="community", evidence_ids=[news["id"]], node_ids=[],
    )])
    problem = db.list_problems(project)[0]
    assert problem["quote"] is None and not problem["evidence_ids"]
