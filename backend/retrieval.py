"""Hybrid evidence retrieval: dense vectors from a local embedding model, boosted by the mind-map graph."""

from __future__ import annotations

import math
from array import array
from typing import Any, Callable, Protocol

from .config import settings
from .database import Database

BATCH = 32


class Embedder(Protocol):
    """Anything that turns texts into vectors."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def pack(vector: list[float]) -> bytes:
    """Normalise a vector to unit length and serialise it as float32."""
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return array("f", (v / norm for v in vector)).tobytes()


def unpack(blob: bytes) -> array:
    """Deserialise a float32 vector."""
    values = array("f")
    values.frombytes(blob)
    return values


def similarity(a: array, b: array) -> float:
    """Cosine similarity of two unit vectors."""
    return sum(x * y for x, y in zip(a, b))


def evidence_text(item: dict[str, Any]) -> str:
    """Text that represents an evidence item in vector space."""
    body = (item.get("body") or "")[:600]
    return f"{item['title']}\n{body}".strip()


class Retriever:
    """Embeds evidence lazily and answers nearest-neighbour queries from the stored vectors.

    Without an embedder, or when the embedding model is missing, every method degrades to a no-op
    so the full-text and graph retrieval keep working on their own.
    """

    def __init__(self, db: Database, embedder: Any = None, model: str | None = None) -> None:
        self.db = db
        self.embedder: Embedder | None = embedder if callable(getattr(embedder, "embed", None)) else None
        self.model = model or settings.embed_model

    async def prepare(self, project_id: int, queries: list[str], warn: Callable[[str], None] | None = None) -> bool:
        """Embed new evidence of the project and the given queries; return whether vectors are usable."""
        if self.embedder is None:
            return False
        try:
            pending = self.db.unembedded_evidence(project_id, self.model)
            for start in range(0, len(pending), BATCH):
                chunk = pending[start : start + BATCH]
                vectors = await self.embedder.embed([evidence_text(item) for item in chunk])
                self.db.save_evidence_vectors(self.model, [(item["id"], pack(v)) for item, v in zip(chunk, vectors)])
            missing = [q for q in dict.fromkeys(q.strip() for q in queries) if q and self.db.query_vector(self.model, q) is None]
            if missing:
                for query, vector in zip(missing, await self.embedder.embed(missing)):
                    self.db.save_query_vector(self.model, query, pack(vector))
        except Exception as exc:
            if warn:
                warn(f"embeddings: {exc}")
            return False
        return True

    def nearest(
        self,
        project_id: int,
        query: str,
        limit: int = 12,
        boost: dict[int, float] | None = None,
        min_score: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Return evidence closest to an already prepared query, with graph proximity added to the score."""
        blob = self.db.query_vector(self.model, query.strip())
        if blob is None:
            return []
        target = unpack(blob)
        boost = boost or {}
        scored = []
        for item in self.db.evidence_vectors(project_id, self.model):
            score = similarity(target, unpack(item.pop("vector")))
            if score < min_score:
                continue
            item["score"] = round(score + boost.get(item["node_id"], 0.0), 4)
            scored.append(item)
        scored.sort(key=lambda i: i["score"], reverse=True)
        return scored[:limit]


def graph_boost(focus: set[int], edges: list[dict[str, Any]], focus_bonus: float = 0.1, neighbour_bonus: float = 0.05) -> dict[int, float]:
    """Score bonus for evidence on focus nodes and on their direct neighbours in the mind map."""
    boost = {node_id: focus_bonus for node_id in focus}
    for edge in edges:
        for a, b in ((edge["source_id"], edge["target_id"]), (edge["target_id"], edge["source_id"])):
            if a in focus and b not in focus:
                boost[b] = neighbour_bonus
    return boost
