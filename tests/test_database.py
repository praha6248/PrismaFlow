"""Tests for the SQLite workspace layer."""

from backend.database import Database


def test_project_creates_root_node(db: Database) -> None:
    project = db.create_project("sport", "pl", "PL")
    root = db.root_node(project["id"])
    assert root["label"] == "sport"
    assert root["kind"] == "niche"
    assert root["is_root"] is True


def test_labels_are_unique_per_project_case_insensitive(db: Database) -> None:
    project = db.create_project("sport", "pl", "PL")
    first = db.insert_node(project["id"], "Taniec")
    second = db.insert_node(project["id"], "taniec")
    assert first["id"] == second["id"]
    assert len(db.list_nodes(project["id"])) == 2


def test_edges_are_undirected_and_deduplicated(db: Database) -> None:
    project = db.create_project("sport", "pl", "PL")
    root = db.root_node(project["id"])
    node = db.insert_node(project["id"], "plan")
    db.insert_edge(project["id"], root["id"], node["id"])
    db.insert_edge(project["id"], node["id"], root["id"])
    assert db.insert_edge(project["id"], node["id"], node["id"]) is None
    assert len(db.list_edges(project["id"])) == 1


def test_root_cannot_be_deleted_and_children_cascade(db: Database) -> None:
    project = db.create_project("sport", "pl", "PL")
    root = db.root_node(project["id"])
    node = db.insert_node(project["id"], "plan")
    db.insert_edge(project["id"], root["id"], node["id"])
    db.add_evidence(project["id"], node["id"], "reddit", "title", "body")
    db.delete_node(root["id"])
    db.delete_node(node["id"])
    assert [n["label"] for n in db.list_nodes(project["id"])] == ["sport"]
    assert db.list_edges(project["id"]) == []


def test_evidence_full_text_search_ignores_diacritics(db: Database) -> None:
    project = db.create_project("sport", "pl", "PL")
    node = db.insert_node(project["id"], "organizacja")
    db.add_evidence(project["id"], node["id"], "reddit", "Słaba organizacja treningów", "Nie mam czasu")
    db.add_evidence(project["id"], node["id"], "autocomplete", "plan treningowy")
    hits = db.search_evidence(project["id"], "slaba organizacja")
    assert [h["title"] for h in hits] == ["Słaba organizacja treningów"]


def test_cache_respects_status_specific_ttl(db: Database) -> None:
    db.cache_put("k1", "autocomplete", "q", "ok", ["a"])
    db.cache_put("k2", "reddit", "q", "error", {"message": "nope"})
    assert db.cache_get("k1", 100, 0) == ("ok", ["a"])
    assert db.cache_get("k2", 100, -1) is None


def test_trend_series_roundtrip(db: Database) -> None:
    project = db.create_project("sport", "pl", "PL")
    root = db.root_node(project["id"])
    updated = db.update_node(root["id"], trend_series={"series": [1, 2]}, trend_growth=0.5, starred=True)
    assert updated["trend_series"] == {"series": [1, 2]}
    assert updated["starred"] is True
