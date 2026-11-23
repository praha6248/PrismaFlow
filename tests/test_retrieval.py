"""Hybrid retrieval: lazy embedding, nearest neighbours and graph boost."""

from __future__ import annotations

import asyncio

from backend.database import Database
from backend.retrieval import Retriever, graph_boost

TOPICS = {"sen": [1.0, 0.0, 0.0], "dieta": [0.0, 1.0, 0.0], "trening": [0.0, 0.0, 1.0]}


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [next((v for k, v in TOPICS.items() if k in t), [0.3, 0.3, 0.3]) for t in texts]


def seeded() -> tuple[Database, int, list[int]]:
    db = Database(":memory:")
    project = db.create_project("zdrowie", "pl", "PL")
    root = db.root_node(project["id"])
    a = db.insert_node(project["id"], "sen", origin="user")
    b = db.insert_node(project["id"], "dieta", origin="user")
    db.insert_edge(project["id"], root["id"], a["id"])
    db.add_evidence(project["id"], a["id"], "community", "problemy ze sen w nocy")
    db.add_evidence(project["id"], b["id"], "community", "dieta keto opinie")
    db.add_evidence(project["id"], b["id"], "trends", "sen trend")
    return db, project["id"], [root["id"], a["id"], b["id"]]


def test_prepare_embeds_once_and_finds_nearest():
    db, pid, _ = seeded()
    embedder = FakeEmbedder()
    retriever = Retriever(db, embedder, model="fake")
    assert asyncio.run(retriever.prepare(pid, ["jak lepiej spać sen"]))
    assert asyncio.run(retriever.prepare(pid, ["jak lepiej spać sen"]))
    assert sum(len(c) for c in embedder.calls) == 3
    hits = retriever.nearest(pid, "jak lepiej spać sen")
    assert [h["title"] for h in hits] == ["problemy ze sen w nocy"]


def test_without_embedder_retrieval_is_empty():
    db, pid, _ = seeded()
    retriever = Retriever(db, object(), model="fake")
    assert not asyncio.run(retriever.prepare(pid, ["sen"]))
    assert retriever.nearest(pid, "sen") == []


def test_failing_embedder_warns():
    class Broken:
        async def embed(self, texts):
            raise RuntimeError("model missing")

    db, pid, _ = seeded()
    warnings: list[str] = []
    assert not asyncio.run(Retriever(db, Broken(), model="fake").prepare(pid, ["sen"], warnings.append))
    assert warnings == ["embeddings: model missing"]


def test_graph_boost_covers_focus_and_neighbours():
    edges = [{"source_id": 1, "target_id": 2}, {"source_id": 3, "target_id": 1}, {"source_id": 4, "target_id": 5}]
    assert graph_boost({1}, edges) == {1: 0.1, 2: 0.05, 3: 0.05}
