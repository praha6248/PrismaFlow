"""Reddit public JSON search collector."""

from __future__ import annotations

import html
import re
import time

import httpx

from ..config import settings
from ..database import Database
from .base import CollectorUnavailable, cached

ENDPOINT = "https://www.reddit.com/search.json"
WHITESPACE = re.compile(r"\s+")
_blocked_until = 0.0


def _clean(text: str, limit: int) -> str:
    text = WHITESPACE.sub(" ", html.unescape(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


async def _fetch(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    try:
        response = await client.get(
            ENDPOINT,
            params={"q": query, "limit": limit, "sort": "relevance", "t": "year", "raw_json": 1},
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise CollectorUnavailable(f"reddit request failed: {exc}") from exc
    if response.status_code in (401, 403):
        raise CollectorUnavailable("reddit refused anonymous access")
    if response.status_code == 429:
        raise CollectorUnavailable("reddit rate limit reached")
    if response.status_code != 200:
        raise CollectorUnavailable(f"reddit returned HTTP {response.status_code}")
    try:
        children = response.json()["data"]["children"]
    except (ValueError, KeyError, TypeError) as exc:
        raise CollectorUnavailable("reddit returned malformed JSON") from exc
    posts = []
    for child in children:
        data = child.get("data", {})
        if data.get("over_18"):
            continue
        posts.append(
            {
                "title": _clean(data.get("title", ""), 240),
                "body": _clean(data.get("selftext", ""), 600),
                "subreddit": data.get("subreddit", ""),
                "score": int(data.get("score") or 0),
                "comments": int(data.get("num_comments") or 0),
                "url": "https://www.reddit.com" + data.get("permalink", ""),
                "created": float(data.get("created_utc") or 0),
            }
        )
    return posts


async def search(db: Database, client: httpx.AsyncClient, query: str, limit: int = 8) -> list[dict]:
    """Return recent Reddit threads matching a query, cached in api_cache.

    After Reddit refuses a request the collector stays closed for the negative-cache
    window instead of hammering the endpoint with every remaining query.
    """

    async def fetch() -> list[dict]:
        global _blocked_until
        if time.time() < _blocked_until:
            raise CollectorUnavailable("reddit temporarily unavailable")
        try:
            return await _fetch(client, query, limit)
        except CollectorUnavailable:
            _blocked_until = time.time() + settings.negative_cache_ttl_seconds
            raise

    return await cached(
        db,
        "reddit",
        query,
        {"limit": limit},
        fetch,
        settings.cache_ttl_seconds,
        settings.negative_cache_ttl_seconds,
    )
