"""Tests for the Stack Exchange and Lemmy community collector."""

import json
import sqlite3

import httpx
import pytest

from backend.collectors import community, reddit
from backend.database import Database


@pytest.fixture
def reddit_queries(monkeypatch):
    queries = []

    async def fetch_browser(query, limit):
        queries.append(query)
        return []

    monkeypatch.delenv("PRISMAFLOW_REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("PRISMAFLOW_REDDIT_PLAYWRIGHT", raising=False)
    monkeypatch.setattr(reddit, "_fetch_browser", fetch_browser)
    monkeypatch.setattr(reddit, "_throttle_lock", None)
    monkeypatch.setattr(reddit, "MIN_INTERVAL", 0)
    return queries


def _transport(calls: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.host == "api.stackexchange.com":
            q = request.url.params["q"]
            if q == "autistic children sport":
                return httpx.Response(200, json={"items": [], "quota_remaining": 290})
            return httpx.Response(
                200,
                json={
                    "quota_remaining": 289,
                    "items": [
                        {"title": "Autistic child avoids team sport", "body": "<p>He hates noise</p>", "score": 12, "answer_count": 3, "link": "https://parenting.stackexchange.com/q/1"},
                        {"title": "Unrelated vaccine question", "body": "nothing", "score": 30, "answer_count": 2, "link": "https://x"},
                        {"title": "Autistic teen at camp", "body": "", "score": 0, "answer_count": 0, "link": "https://y"},
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "posts": [
                    {"post": {"name": "Sport for autistic children ideas", "ap_id": "https://lemmy.world/post/1"}, "community": {"name": "autism"}, "counts": {"score": 50, "comments": 9}},
                    {"post": {"name": "Autistic children sport nsfw", "nsfw": True}, "community": {"name": "x"}, "counts": {"score": 99, "comments": 1}},
                    {"post": {"name": "Sport for autistic children in 2013", "published": "2013-05-01T00:00:00Z"}, "community": {"name": "autism"}, "counts": {"score": 900, "comments": 90}},
                    {"post": {"name": "Cats"}, "community": {"name": "cats"}, "counts": {"score": 500, "comments": 50}},
                ]
            },
        )

    return httpx.MockTransport(handler)


def test_site_choice_and_keywords() -> None:
    assert community.pick_sites("sport for autistic children") == ["parenting", "sports"]
    assert community.pick_sites("meal planning app")[0] in ("cooking", "softwarerecs")
    assert community.pick_sites("quantum gravity") == ["lifehacks", "softwarerecs"]
    assert community.keywords("sport for autistic children") == ["sport", "autistic", "children"]
    assert community.specific_word("sport for autistic children") == "autistic"
    assert community.specific_word("workout motivation") is None


async def test_search_merges_sources_and_filters_noise(db: Database, reddit_queries) -> None:
    community.MIN_INTERVAL = 0
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        posts = await community.search(db, client, "sport for autistic children", "en")
    titles = [p["title"] for p in posts]
    assert titles[0] == "Sport for autistic children ideas"
    assert "Autistic child avoids team sport" in titles
    assert all("vaccine" not in t and "nsfw" not in t and t != "Cats" for t in titles)
    assert "Autistic teen at camp" not in titles
    assert {p["platform"] for p in posts} == {"lemmy", "stackexchange"}
    assert posts[0]["place"] == "autism"
    assert "Sport for autistic children in 2013" not in titles
    assert all("fromdate=" in c for c in calls if "stackexchange" in c)
    assert any("q=autistic&" in c or "q=autistic" in c.split("&")[-1] or "q=autistic" in c for c in calls)

    calls.clear()
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        await community.search(db, client, "sport for autistic children", "en")
    assert calls == []
    assert reddit_queries == ["sport for autistic children"]


async def test_non_english_queries_skip_stack_exchange(db: Database, reddit_queries) -> None:
    community.MIN_INTERVAL = 0
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        await community.search(db, client, "sport dla dzieci", "pl")
    assert calls and all("lemmy.world" in c for c in calls)
    assert reddit_queries == ["sport dla dzieci"]


def test_evidence_table_is_migrated(tmp_path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, seed TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en', geo TEXT NOT NULL DEFAULT '', phase TEXT NOT NULL DEFAULT 'discover',
            stage TEXT NOT NULL DEFAULT 'compose', created_at REAL NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            node_id INTEGER,
            source TEXT NOT NULL CHECK (source IN ('autocomplete', 'reddit', 'trends', 'llm')),
            title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', url TEXT, weight REAL NOT NULL DEFAULT 0,
            meta TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL);
        INSERT INTO projects(name, seed, created_at, updated_at) VALUES ('sport', 'sport', 0, 0);
        INSERT INTO evidence(project_id, source, title, created_at) VALUES (1, 'reddit', 'Stare treningi', 0);
        """
    )
    conn.commit()
    conn.close()
    db = Database(path)
    assert db.search_evidence(1, "treningi")[0]["title"] == "Stare treningi"
    db.add_evidence(1, None, "community", "Nowy wątek", meta=json.loads('{"platform": "lemmy"}'))
    assert len(db.search_evidence(1, "wątek")) == 1


def test_cutoff_and_timestamps() -> None:
    assert community.cutoff(365, now=400 * 86400) == 35 * 86400
    assert community.timestamp("2024-01-01T00:00:00Z") == 1704067200
    assert community.timestamp("2024-01-01T00:00:00.123456") > 0
    assert community.timestamp(None) == 0.0 and community.timestamp("bad") == 0.0
