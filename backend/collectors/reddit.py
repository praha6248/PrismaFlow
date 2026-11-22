"""Reddit search through the official OAuth API.

Used only when PRISMFLOW_REDDIT_CLIENT_ID is set: an approved "installed app" needs only the
client id, a "script" or "web app" also needs PRISMFLOW_REDDIT_CLIENT_SECRET. Without
credentials, community evidence comes from Stack Exchange and Lemmy instead.
"""

from __future__ import annotations

import asyncio
import html
import os
import re
import time
import uuid
from typing import Any

import httpx

from ..config import settings
from ..database import Database
from .base import CollectorUnavailable, cached

OAUTH_ENDPOINT = "https://oauth.reddit.com/search"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
WHITESPACE = re.compile(r"\s+")
_blocked_until: dict[str, float] = {}
_token: tuple[str, float] | None = None
_device_id = uuid.uuid4().hex
_throttle_lock: asyncio.Lock | None = None
_last_call = 0.0
MIN_INTERVAL = 1.1
RATE_LIMIT_PAUSE = 60.0


class RateLimited(CollectorUnavailable):
    """Raised when the provider asks the client to slow down."""


async def _throttled(call):
    """Serialise provider calls, keep a minimum gap and retry briefly on rate limits."""
    global _throttle_lock, _last_call
    if _throttle_lock is None:
        _throttle_lock = asyncio.Lock()
    async with _throttle_lock:
        for attempt in range(3):
            wait = MIN_INTERVAL - (time.monotonic() - _last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_call = time.monotonic()
            try:
                return await call()
            except RateLimited:
                if attempt == 2:
                    raise
                await asyncio.sleep(3 * (attempt + 1))


def credentials_configured() -> bool:
    """Tell whether the user supplied Reddit API credentials."""
    return bool(os.environ.get("PRISMFLOW_REDDIT_CLIENT_ID"))


def _clean(text: str, limit: int) -> str:
    text = WHITESPACE.sub(" ", html.unescape(text or "")).strip()
    if text in ("[removed]", "[deleted]"):
        return ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _post(data: dict[str, Any]) -> dict[str, Any] | None:
    if data.get("over_18") or data.get("removed_by_category"):
        return None
    title = _clean(data.get("title", ""), 240)
    if not title:
        return None
    permalink = data.get("permalink") or ""
    return {
        "title": title,
        "body": _clean(data.get("selftext", ""), 600),
        "subreddit": data.get("subreddit", ""),
        "score": int(float(data.get("score") or 0)),
        "comments": int(float(data.get("num_comments") or 0)),
        "url": "https://www.reddit.com" + permalink if permalink.startswith("/") else permalink,
        "created": float(data.get("created_utc") or 0),
    }


def _rank(posts: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ranked = []
    for post in sorted(posts, key=lambda p: p["score"] + 2 * p["comments"], reverse=True):
        key = post["title"].casefold()
        if key in seen or (post["score"] < 2 and post["comments"] < 2):
            continue
        seen.add(key)
        ranked.append(post)
    return ranked[:limit]


async def _access_token(client: httpx.AsyncClient, client_id: str) -> str:
    """Obtain or reuse an application-only OAuth token."""
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
            TOKEN_URL, data=grant, auth=(client_id, secret), headers={"User-Agent": settings.user_agent}
        )
    except httpx.HTTPError as exc:
        raise CollectorUnavailable(f"reddit token request failed: {exc}") from exc
    if response.status_code != 200 or "access_token" not in response.text:
        raise CollectorUnavailable(f"reddit rejected the app credentials (HTTP {response.status_code})")
    data = response.json()
    _token = (data["access_token"], time.time() + float(data.get("expires_in", 3600)))
    return _token[0]


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any], headers: dict[str, str]) -> Any:
    try:
        response = await client.get(url, params=params, headers=headers, follow_redirects=True, timeout=12)
    except httpx.HTTPError as exc:
        raise CollectorUnavailable(f"reddit request failed: {exc}") from exc
    if response.status_code in (401, 403):
        raise CollectorUnavailable(f"reddit source refused access (HTTP {response.status_code})")
    if response.status_code == 429:
        raise RateLimited("reddit rate limit reached")
    if response.status_code != 200:
        raise CollectorUnavailable(f"reddit source returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise CollectorUnavailable("reddit source returned malformed JSON") from exc


async def _fetch_oauth(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    client_id = os.environ.get("PRISMFLOW_REDDIT_CLIENT_ID", "")
    if not client_id:
        raise CollectorUnavailable("PRISMFLOW_REDDIT_CLIENT_ID is not set")
    headers = {"User-Agent": settings.user_agent, "Authorization": f"bearer {await _access_token(client, client_id)}"}
    params = {"q": query, "limit": 25, "sort": "relevance", "t": "year", "raw_json": 1}
    data = await _get_json(client, OAUTH_ENDPOINT, params, headers)
    try:
        children = data["data"]["children"]
    except (KeyError, TypeError) as exc:
        raise CollectorUnavailable("reddit returned an unexpected payload") from exc
    return _rank([p for c in children if (p := _post(c.get("data", {})))], limit)


async def search(db: Database, client: httpx.AsyncClient, query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Return popular Reddit threads matching a query, cached in api_cache.

    After a provider fails the collector stays closed for the negative-cache window
    instead of hammering it with every remaining query.
    """
    name = "oauth"

    async def fetch() -> list[dict[str, Any]]:
        if time.time() < _blocked_until.get(name, 0.0):
            raise CollectorUnavailable("reddit temporarily unavailable")
        try:
            return await _throttled(lambda: _fetch_oauth(client, query, limit))
        except RateLimited:
            _blocked_until[name] = time.time() + RATE_LIMIT_PAUSE
            raise
        except CollectorUnavailable:
            _blocked_until[name] = time.time() + settings.negative_cache_ttl_seconds
            raise

    return await cached(
        db,
        f"reddit:{name}",
        query,
        {"limit": limit},
        fetch,
        settings.cache_ttl_seconds,
        settings.negative_cache_ttl_seconds,
    )
