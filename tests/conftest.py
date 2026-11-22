"""Shared fixtures: in-memory database, fake LLM and offline collectors."""

from __future__ import annotations

from typing import Any

import pytest

from backend.database import Database
from backend.models import ExpansionPlan
from backend.ollama_client import OllamaError
from backend.services.discover import Collectors


class FakeLLM:
    """Returns a canned plan and records the prompts it receives."""

    def __init__(self, plan: dict[str, Any] | None = None, fail: bool = False) -> None:
        self.plan = plan or {}
        self.fail = fail
        self.prompts: list[str] = []

    async def structured(self, schema: Any, system: str, prompt: str, **_: Any) -> Any:
        self.prompts.append(prompt)
        if self.fail:
            raise OllamaError("offline")
        return ExpansionPlan.model_validate(self.plan)


def offline_collectors(posts: list[dict] | None = None, trend: dict | None = None) -> Collectors:
    """Collectors that answer from memory instead of the network."""

    async def suggestions(db, http, query, language, geo="", limit=24):
        return [f"{query} dla kobiet", f"{query} w domu", f"{query} aplikacja"]

    async def simple(db, http, query, language, geo=""):
        return [f"{query} opinie", f"{query} cena"]

    async def reddit_search(db, http, query, limit=8):
        return posts if posts is not None else [
            {"title": f"I struggle with {query}", "body": "help", "score": 40, "comments": 12, "url": "https://r/x"}
        ]

    async def trend_growth(db, keywords, geo="", language="en"):
        base = trend or {"series": [10.0] * 39 + [20.0] * 13, "dates": [], "growth": 1.0, "anchor_ratio": 2.0}
        return {k: dict(base) for k in keywords}

    return Collectors(
        suggestions=suggestions,
        simple_suggestions=simple,
        reddit_search=reddit_search,
        trend_growth=trend_growth,
    )


@pytest.fixture
def db() -> Database:
    return Database(":memory:")
