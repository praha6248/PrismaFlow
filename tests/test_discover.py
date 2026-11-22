"""Tests for the Discover service."""

from backend.collectors.trends import growth_3m_vs_9m
from backend.database import Database
from backend.services import discover
from backend.services.discover import DiscoverService, score_node

from .conftest import FakeLLM, offline_collectors

PLAN = {
    "language": "pl",
    "classified": [{"label": "plan", "kind": "idea"}, {"label": "taniec", "kind": "idea"}],
    "new_nodes": [
        {"label": "młode kobiety", "kind": "target_group", "connects_to": ["taniec", "plan"], "search_query": "taniec dla kobiet"},
        {"label": "słaba_organizacja", "kind": "pain_point", "connects_to": ["sport", "młode kobiety"], "search_query": "brak czasu"},
        {"label": "Plan", "kind": "idea", "connects_to": ["sport"], "search_query": "duplicate"},
        {"label": "orphan", "kind": "competitor", "connects_to": ["missing"], "search_query": "orphan"},
    ],
}


def _noop(*_: object) -> None:
    return None


def _seed(db: Database) -> int:
    graph = discover.create_project(db, "sport")
    project_id = graph["project"]["id"]
    discover.add_node(db, project_id, "plan")
    discover.add_node(db, project_id, "taniec")
    return project_id


async def test_expand_classifies_creates_links_and_scores(db: Database) -> None:
    project_id = _seed(db)
    service = DiscoverService(db, FakeLLM(PLAN), offline_collectors())
    warnings: list[str] = []
    result = await service.expand(project_id, None, 3, _noop, warnings.append)

    nodes = {n["label"]: n for n in result["nodes"]}
    assert nodes["plan"]["kind"] == "idea"
    assert nodes["młode kobiety"]["kind"] == "target_group"
    assert nodes["słaba organizacja"]["kind"] == "pain_point"
    assert nodes["orphan"]["kind"] == "competitor"
    assert "Plan" not in nodes
    assert all(n["score"] > 0 for n in result["nodes"])
    assert nodes["sport"]["trend_growth"] == 1.0
    assert result["project"]["stage"] == "select"
    assert warnings == []

    ids = {n["id"]: n["label"] for n in result["nodes"]}
    pairs = {frozenset((ids[e["source_id"]], ids[e["target_id"]])) for e in result["edges"]}
    assert frozenset(("taniec", "młode kobiety")) in pairs
    assert frozenset(("słaba organizacja", "młode kobiety")) in pairs
    assert frozenset(("sport", "orphan")) in pairs

    evidence = discover.node_evidence(db, nodes["młode kobiety"]["id"])
    assert evidence["quotes"] and evidence["suggestions"]
    assert evidence["trend"]["growth"] == 1.0


async def test_expand_respects_count_limit(db: Database) -> None:
    project_id = _seed(db)
    service = DiscoverService(db, FakeLLM(PLAN), offline_collectors())
    result = await service.expand(project_id, None, 1, _noop, _noop)
    assert len(result["nodes"]) == 4


async def test_expand_falls_back_to_suggestions_without_llm(db: Database) -> None:
    project_id = _seed(db)
    service = DiscoverService(db, FakeLLM(fail=True), offline_collectors())
    warnings: list[str] = []
    result = await service.expand(project_id, None, 2, _noop, warnings.append)
    labels = {n["label"] for n in result["nodes"]}
    assert {"dla kobiet", "w domu"} <= labels
    assert any(w.startswith("llm:") for w in warnings)
    assert all(n["kind"] for n in result["nodes"])


async def test_prompt_lists_map_and_suggestions(db: Database) -> None:
    project_id = _seed(db)
    llm = FakeLLM(PLAN)
    service = DiscoverService(db, llm, offline_collectors())
    taniec = db.find_node(project_id, "taniec")
    await service.expand(project_id, taniec["id"], 2, _noop, _noop)
    prompt = llm.prompts[0]
    assert 'Focus node to expand: "taniec"' in prompt
    assert "taniec dla kobiet" in prompt
    assert "Classify each of these nodes: plan, taniec" in prompt


def test_growth_compares_last_quarter_with_previous_months() -> None:
    assert growth_3m_vs_9m([10.0] * 39 + [15.0] * 13) == 0.5
    assert growth_3m_vs_9m([1.0, 2.0]) is None


def test_score_is_bounded() -> None:
    assert 0 <= score_node(0, None, None) <= 1
    high = score_node(10, [{"score": 10000, "comments": 0}], {"series": [1], "anchor_ratio": 50, "growth": 3})
    assert 0.9 <= high <= 1


def test_llm_schema_requires_new_nodes() -> None:
    from backend.models import ExpansionPlan
    from backend.ollama_client import inline_schema

    schema = inline_schema(ExpansionPlan)
    assert schema["properties"]["new_nodes"]["minItems"] == 1
    assert "$ref" not in str(schema)
