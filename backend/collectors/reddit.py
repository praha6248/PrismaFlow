"""Reddit search collector.

Uses the official OAuth API with an application-only token when PRISMFLOW_REDDIT_CLIENT_ID
is set: an "installed app" needs only the client id, a "script" or "web app" also needs
PRISMFLOW_REDDIT_CLIENT_SECRET. Without credentials the public JSON endpoint is used, which
Reddit may refuse for anonymous clients.
"""

from __future__ import annotations

import html
import os
import re
import time
import uuid

import httpx

from ..config import settings
from ..database import Database
from .base import CollectorUnavailable, cached

ENDPOINT = "https://www.reddit.com/search.json"
OAUTH_ENDPOINT = "https://oauth.reddit.com/search"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
WHITESPACE = re.compile(r"\s+")
_blocked_until = 0.0
_token: tuple[str, float] | None = None
_device_id = uuid.uuid4().hex


def credentials_configured() -> bool:
    """Tell whether the user supplied Reddit API credentials."""
    return bool(os.environ.get("PRISMFLOW_REDDIT_CLIENT_ID"))


async def _access_token(client: httpx.AsyncClient, client_id: str) -> str:
    """Obtain or reuse an application-only OAuth token for an installed app."""
    global _token
    if _token and _token[1] > time.time() + 60:
        return _token[0]
    secret = os.environ.get("PRISMFLOW_REDDIT_CLIENT_SECRET", "")
    if secret:
        grant = {"grant_type": "client_credentials"}
    else:
        grant = {"grant_type": "https://oauth.reddit.com/grants/installed_client", "device_id": _device_id}
    try:
        response = await client.post(
            TOKEN_URL,
            data=grant,
            auth=(client_id, secret),
            headers={"User-Agent": settings.user_agent},
        )
    except httpx.HTTPError as exc:
        raise CollectorUnavailable(f"reddit token request failed: {exc}") from exc
    if response.status_code != 200 or "access_token" not in response.text:
        raise CollectorUnavailable(f"reddit rejected the app credentials (HTTP {response.status_code})")
    data = response.json()
    _token = (data["access_token"], time.time() + float(data.get("expires_in", 3600)))
    return _token[0]


def _clean(text: str, limit: int) -> str:
    text = WHITESPACE.sub(" ", html.unescape(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


async def _fetch(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    params = {"q": query, "limit": limit, "sort": "relevance", "t": "year", "raw_json": 1}
    headers = {"User-Agent": settings.user_agent}
    url = ENDPOINT
    client_id = os.environ.get("PRISMFLOW_REDDIT_CLIENT_ID")
    if client_id:
        headers["Authorization"] = f"bearer {await _access_token(client, client_id)}"
        url = OAUTH_ENDPOINT
    try:
        response = await client.get(url, params=params, headers=headers, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise CollectorUnavailable(f"reddit request failed: {exc}") from exc
    if response.status_code in (401, 403):
        raise CollectorUnavailable(
            "reddit refused access" + ("" if client_id else "; set PRISMFLOW_REDDIT_CLIENT_ID to use the OAuth API")
        )
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
