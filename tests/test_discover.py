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
    markets = evidence["trend"]["markets"]
    assert markets["pl"]["query"] == "młode kobiety"
    assert markets["en"]["query"] == "[en] młode kobiety"
    assert markets["en"]["anchor"] == "calendar"
    english = [q for q in evidence["quotes"] if q["meta"].get("lang") == "en"]
    assert english and english[0]["title"].startswith("[pl] I struggle with [en] ")
    assert english[0]["meta"]["original"].startswith("I struggle with [en] ")


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
    prompt = next(p for p in llm.prompts if "Focus node" in p)
    assert 'Focus node to expand: "taniec"' in prompt
    assert "taniec dla kobiet" in prompt
    assert "Classify each of these nodes: plan, taniec" in prompt


def test_growth_compares_last_quarter_with_previous_months() -> None:
    assert growth_3m_vs_9m([10.0] * 39 + [15.0] * 13) == 0.5
    assert growth_3m_vs_9m([1.0, 2.0]) is None
    assert growth_3m_vs_9m([2.0] * 13 + [0.0] * 39) is None


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


async def test_english_discussions_reuse_original_and_cache_translation(db: Database) -> None:
    project = db.create_project("sport", "pl", "PL")
    node = db.root_node(project["id"])
    db.add_evidence(project["id"], node["id"], "community", "Montaż kamery",
                    meta={"lang": "en", "original": "Installing a camera"})
    db.add_evidence(project["id"], node["id"], "reddit", "Taniec dla dzieci")
    llm = FakeLLM()
    for _ in range(2):
        result = discover.node_evidence(db, node["id"])
        await discover.english_discussions(db, llm, result)
        assert {q["title"] for q in result["quotes"]} == {"Installing a camera", "[en] Taniec dla dzieci"}
    assert len(llm.prompts) == 1
    assert {q["title"] for q in discover.node_evidence(db, node["id"])["quotes"]} == {"Montaż kamery", "Taniec dla dzieci"}


async def test_expand_drops_competitors_nobody_mentions(db: Database) -> None:
    project_id = _seed(db)
    plan = {
        "language": "pl",
        "classified": [],
        "new_nodes": [
            {"label": "edukacja.pl", "kind": "competitor", "connects_to": ["sport"], "search_query": "edukacja.pl"},
            {"label": "Strava", "kind": "competitor", "connects_to": ["sport"], "search_query": "strava"},
            {"label": "rodzice", "kind": "target_group", "connects_to": ["edukacja.pl"], "search_query": "rodzice"},
            {"label": "Aplikacja mobilna", "kind": "idea", "connects_to": ["sport"], "search_query": "aplikacja"},
        ],
    }
    posts = [{"title": "Studying is a waste of time", "body": "I switched to Strava for runs", "score": 3, "comments": 1, "url": "https://x"}]
    service = DiscoverService(db, FakeLLM(plan), offline_collectors(posts=posts))
    warnings: list[str] = []
    result = await service.expand(project_id, None, 3, _noop, warnings.append)

    nodes = {n["label"]: n for n in result["nodes"]}
    assert "edukacja.pl" not in nodes
    assert "Aplikacja mobilna" not in nodes
    assert nodes["Strava"]["kind"] == "competitor"
    assert warnings == ["competitor: edukacja.pl"]
    linked = {i for e in result["edges"] for i in (e["source_id"], e["target_id"])}
    assert nodes["rodzice"]["id"] in linked


def test_mentions_matches_whole_names() -> None:
    assert discover.mentions("Polecam Edukacja.pl do nauki", "edukacja.pl")
    assert not discover.mentions("edukacja publiczna", "edukacja.pl")
    assert not discover.mentions("superhellofresh box", "HelloFresh")
    assert discover.mentions("Używam Perspektywy ranking", "perspektywy")


class ScreeningLLM(FakeLLM):
    """Fake model with embeddings: vectors point along the topic when the text mentions the knee."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        def vector(text: str) -> list[float]:
            low = text.casefold()
            if "kolan" in low:
                return [1.0, 0.0]
            if "kot" in low:
                return [0.0, 1.0]
            return [0.5, 0.866]

        return [vector(t) for t in texts]


async def test_expand_screens_out_discussions_that_only_share_a_word(db: Database) -> None:
    project_id = discover.create_project(db, "Planer treningów po kontuzji kolana")["project"]["id"]
    discover.add_node(db, project_id, "rehabilitacja")
    plan = {
        "language": "pl",
        "classified": [{"label": "rehabilitacja", "kind": "idea", "search_query": "rehabilitacja kolana"}],
        "new_nodes": [{"label": "fizjoterapeuta", "kind": "target_group", "connects_to": ["rehabilitacja"], "search_query": "fizjoterapeuta kolano"}],
    }
    posts = [
        {"title": "Ćwiczenia na kolana po urazie", "body": "", "score": 50, "comments": 9, "url": "https://a"},
        {"title": "Kot z centrum rehabilitacji zwierząt", "body": "", "score": 900, "comments": 90, "url": "https://b"},
        {"title": "Fizjoterapia wróciła mi sprawność", "body": "", "score": 5, "comments": 1, "url": "https://c"},
        {"title": "Nowy film akcji w kinach", "body": "", "score": 300, "comments": 40, "url": "https://d"},
    ]
    llm = ScreeningLLM(plan)
    llm.relevant = "Fizjoterapia"
    service = DiscoverService(db, llm, offline_collectors(posts=posts))
    result = await service.expand(project_id, None, 3, _noop, _noop)

    nodes = {n["label"]: n for n in result["nodes"]}
    assert nodes["rehabilitacja"]["search_query"] == "rehabilitacja kolana"
    titles = {q["title"] for q in discover.node_evidence(db, nodes["rehabilitacja"]["id"])["quotes"]}
    assert "Ćwiczenia na kolana po urazie" in titles
    assert "Fizjoterapia wróciła mi sprawność" in titles
    assert not any("Kot" in t or "film" in t for t in titles)
    assert any("Niche:" in p and "Nowy film" in p for p in llm.prompts)


def test_guess_language_reads_letters_and_function_words() -> None:
    assert discover.guess_language(["App that finds quiet places to study in the city", "students"]) == "en"
    assert discover.guess_language(["Wspólny budżet domowy dla par"]) == "pl"
    assert discover.guess_language(["planer treningow dla osob po kontuzji"]) == "pl"
    assert discover.guess_language(["sport"]) is None


def test_create_project_takes_language_from_the_seed(db: Database) -> None:
    project = discover.create_project(db, "App that finds quiet places to study")["project"]
    assert project["language"] == "en"


async def test_trends_pause_after_429_and_double_while_it_repeats(db: Database, monkeypatch) -> None:
    from backend.collectors import trends

    calls: list[list[str]] = []

    def limited(keywords, geo, timeframe):
        calls.append(keywords)
        raise trends.RateLimited("google trends: too many requests (429)")

    monkeypatch.setattr(trends, "_download", limited)
    import pytest

    with pytest.raises(trends.RateLimited):
        await trends.interest(db, ["a", "kalendarz"], "PL")
    with pytest.raises(trends.RateLimited, match="paused"):
        await trends.interest(db, ["b", "kalendarz"], "PL")
    assert len(calls) == 1
    assert 29 * 60 < trends.cooldown_left(db) <= 30 * 60
    assert trends.start_cooldown(db) == 60 * 60


async def test_competitors_are_checked_as_brands_categories_or_unrelated(db: Database) -> None:
    project_id = discover.create_project(db, "Wspólny budżet domowy dla par")["project"]["id"]
    discover.add_node(db, project_id, "fizjoterapeuta")
    plan = {
        "language": "pl",
        "classified": [{"label": "fizjoterapeuta", "kind": "competitor"}],
        "new_nodes": [
            {"label": "Spendee", "kind": "competitor", "connects_to": ["Wspólny budżet domowy dla par"], "search_query": "spendee"},
            {"label": "edukacja.pl", "kind": "competitor", "connects_to": ["Wspólny budżet domowy dla par"], "search_query": "edukacja.pl"},
            {"label": "aplikacje budżetowe", "kind": "competitor", "connects_to": ["Wspólny budżet domowy dla par"], "search_query": "aplikacje budżetowe"},
        ],
    }
    posts = [{"title": "Jak dzielicie wydatki w związku?", "body": "", "score": 3, "comments": 2, "url": "https://x"}]
    llm = FakeLLM(plan)
    llm.relevant = "wydatki"
    llm.competitors = {
        "Spendee": {"proper_name": True, "serves_niche": True, "people": False},
        "edukacja.pl": {"proper_name": True, "serves_niche": False, "people": False},
        "aplikacje budżetowe": {"proper_name": False, "serves_niche": True, "people": False},
        "fizjoterapeuta": {"proper_name": True, "serves_niche": False, "people": True},
    }
    warnings: list[str] = []
    result = await DiscoverService(db, llm, offline_collectors(posts=posts)).expand(project_id, None, 3, _noop, warnings.append)

    nodes = {n["label"]: n for n in result["nodes"]}
    assert nodes["Spendee"]["kind"] == "competitor"
    assert "edukacja.pl" not in nodes
    assert nodes["aplikacje budżetowe"]["kind"] == "idea"
    assert nodes["fizjoterapeuta"]["kind"] == "target_group"
    assert "competitor: edukacja.pl" in warnings
