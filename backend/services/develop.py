"""Develop phase: an evidence-backed MoSCoW backlog for the persona chosen in Define."""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict
from typing import Any

from ..database import Database
from ..models import FeatureSet
from .discover import LANGUAGE_NAMES, StructuredLLM
from .jobs import ProgressFn, WarnFn

POOL_SIZE = 50

FEATURE_SYSTEM = """You are a product manager running the Develop phase of the Double Diamond.
You turn a persona's needs into a feature backlog for the first version of a product and prioritise it with MoSCoW.
Rules:
- Write in {language}.
- Propose 7 or 8 distinct features that directly help the persona with the chosen problem.
- Priorities: 2-3 "must" (the smallest useful MVP), 2 "should", 2 "could", 1 "wont" (tempting but out of scope).
- Features are user-facing capabilities, not technologies; no two features may overlap.
- Titles have 2-4 words; descriptions are a short benefit phrase of 3-8 words without a trailing period,
  for example "Dopasowanie do rytmu dnia".
- keywords are everyday words people use when they need the feature, so they can be matched against the evidence.
- evidence_ids lists only ids of evidence lines that really support the feature."""

WORD = re.compile(r"\w+")


def fold(text: str) -> str:
    """Lower-case text and strip diacritics for loose matching."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in normalized if not unicodedata.combining(c)).replace("ł", "l")


def stems(words: list[str]) -> list[str]:
    """Return 5-character stems of meaningful words."""
    result = []
    for word in words:
        for token in WORD.findall(fold(word)):
            if len(token) >= 4:
                result.append(token[:5])
    return list(dict.fromkeys(result))


def support(pool: dict[int, dict[str, Any]], keywords: list[str], cited: list[int]) -> list[int]:
    """Return ids of pool evidence that the model cited or that mention a distinctive keyword.

    Keywords found in more than half of a sizeable pool describe the whole niche rather than
    the feature, so they are ignored.
    """
    texts = {i: fold(f"{item['title']} {item.get('body') or ''}") for i, item in pool.items()}
    keys = stems(keywords)
    if len(pool) >= 6:
        keys = [k for k in keys if sum(k in t for t in texts.values()) <= len(pool) / 2]
    matched = list(dict.fromkeys(i for i in cited if i in pool))
    for item_id, text in texts.items():
        if item_id not in matched and any(key in text for key in keys):
            matched.append(item_id)
    return matched


def scored(pool: dict[int, dict[str, Any]], keywords: list[str], cited: list[int]) -> dict[str, Any]:
    """Compute support, pool size and demand for a feature."""
    ids = support(pool, keywords, cited)
    size = len(pool)
    return {
        "evidence_ids": ids,
        "support": len(ids),
        "pool": size,
        "demand": round(100 * len(ids) / size) if size else 0,
    }


def develop_state(db: Database, project_id: int) -> dict[str, Any]:
    """Return everything the Develop board needs."""
    project = db.get_project(project_id)
    if project is None:
        raise LookupError(f"project {project_id} not found")
    problem = next((p for p in db.list_problems(project_id) if p["chosen"]), None)
    return {
        "project": project,
        "problem": problem,
        "persona": db.chosen_persona(project_id),
        "features": db.list_features(project_id),
    }


class DevelopService:
    """Builds and scores the MoSCoW backlog."""

    def __init__(self, db: Database, llm: StructuredLLM) -> None:
        self.db = db
        self.llm = llm

    def pool(self, project_id: int) -> dict[int, dict[str, Any]]:
        """Collect the evidence sample used to measure demand: the chosen problem's nodes, starred topics and search hits."""
        problem = next((p for p in self.db.list_problems(project_id) if p["chosen"]), None)
        persona = self.db.chosen_persona(project_id)
        nodes = self.db.list_nodes(project_id)
        node_ids = list(problem["node_ids"]) if problem else []
        node_ids += [n["id"] for n in nodes if n["starred"] and n["id"] not in node_ids]
        if not node_ids:
            node_ids = [n["id"] for n in sorted(nodes, key=lambda n: n["score"], reverse=True)[:6]]
        items: OrderedDict[int, dict[str, Any]] = OrderedDict()
        queries = [problem["title"], problem["keyword"]] if problem else []
        if persona:
            queries.append(persona["focus"])
        for query in queries:
            for item in self.db.search_evidence(project_id, query, limit=15):
                if item["source"] in ("reddit", "autocomplete"):
                    items.setdefault(item["id"], item)
        for item in self.db.evidence_for_nodes(node_ids, per_node=10):
            items.setdefault(item["id"], item)
        if len(items) < POOL_SIZE:
            focus = set(node_ids)
            neighbours = []
            for edge in self.db.list_edges(project_id):
                for a, b in ((edge["source_id"], edge["target_id"]), (edge["target_id"], edge["source_id"])):
                    if a in focus and b not in focus and b not in neighbours:
                        neighbours.append(b)
            for item in self.db.evidence_for_nodes(neighbours, per_node=6):
                items.setdefault(item["id"], item)
        return dict(list(items.items())[:POOL_SIZE])

    async def generate(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Ask the local model for a MoSCoW backlog and score every feature against the evidence pool."""
        state = develop_state(self.db, project_id)
        project, problem, persona = state["project"], state["problem"], state["persona"]
        if problem is None or persona is None:
            raise ValueError("choose a problem and a persona in Define first")

        progress(0.1, "context")
        pool = self.pool(project_id)
        evidence_lines = [f"[{item_id}] ({item['source']}) {item['title']}" for item_id, item in pool.items()]
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                f"Problem: {problem['title']} — {problem['description']}",
                f"Persona: {persona['name']}, {persona['age']}, {persona['role']}",
                f'Persona says: "{persona["quote"]}"',
                f"Main need to solve first: {persona['focus']}",
                "",
                "Evidence from search suggestions and community threads:",
                *(evidence_lines or ["(none collected)"]),
            ]
        )

        progress(0.25, "thinking")
        language = LANGUAGE_NAMES.get(project["language"], "the niche's language")
        result = await self.llm.structured(FeatureSet, FEATURE_SYSTEM.format(language=language), prompt, temperature=0.5)

        progress(0.8, "scoring")
        seen: set[str] = set()
        rows = []
        positions: dict[str, int] = {}
        for draft in result.features:
            key = draft.title.casefold()
            if key in seen:
                continue
            seen.add(key)
            position = positions.get(draft.priority, 0)
            positions[draft.priority] = position + 1
            rows.append(
                {
                    "priority": draft.priority,
                    "position": position,
                    "title": draft.title,
                    "description": draft.description,
                    "keywords": draft.keywords,
                    **scored(pool, [*draft.keywords, draft.title], draft.evidence_ids),
                    "origin": "ai",
                }
            )
        if not any(r["priority"] == "must" for r in rows) and rows:
            best = max(rows, key=lambda r: r["demand"])
            best["priority"] = "must"

        progress(0.95, "saving")
        self.db.replace_features(project_id, rows)
        self.db.update_project(project_id, phase="develop", stage="board")
        return develop_state(self.db, project_id)

    def add(self, project_id: int, title: str, description: str, priority: str) -> dict[str, Any]:
        """Add a user-written feature scored against the same evidence pool."""
        pool = self.pool(project_id)
        keywords = stems([title, description])[:6]
        return self.db.add_feature(
            project_id,
            {
                "priority": priority,
                "title": title,
                "description": description,
                "keywords": keywords,
                **scored(pool, [title, description], []),
                "origin": "user",
            },
        )

    def rescore(self, feature_id: int) -> dict[str, Any] | None:
        """Recompute a feature's demand after its text changed."""
        feature = self.db.get_feature(feature_id)
        if feature is None:
            return None
        pool = self.pool(feature["project_id"])
        keywords = feature["keywords"] if feature["origin"] == "ai" else stems([feature["title"], feature["description"]])
        cited = [i for i in feature["evidence_ids"] if i in pool] if feature["origin"] == "ai" else []
        return self.db.update_feature(feature_id, **scored(pool, [*keywords, feature["title"]], cited))
