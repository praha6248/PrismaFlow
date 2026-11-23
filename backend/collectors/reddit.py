"""Reddit search via OAuth or the public search UI through Playwright."""

from __future__ import annotations

import asyncio
import html
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import settings
from ..database import Database
from .base import CollectorUnavailable, cached

OAUTH_ENDPOINT = "https://oauth.reddit.com/search"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
WEB_ENDPOINT = "https://www.reddit.com/search/"
POST_LINK = 'main a[href*="/r/"][href*="/comments/"]:visible'
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


async def _throttled(call, attempts: int = 3):
    """Serialise provider calls, keep a minimum gap and retry briefly on rate limits."""
    global _throttle_lock, _last_call
    if _throttle_lock is None:
        _throttle_lock = asyncio.Lock()
    async with _throttle_lock:
        for attempt in range(attempts):
            wait = MIN_INTERVAL - (time.monotonic() - _last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_call = time.monotonic()
            try:
                return await call()
            except RateLimited:
                if attempt == attempts - 1:
                    raise
                await asyncio.sleep(3 * (attempt + 1))


def credentials_configured() -> bool:
    """Tell whether the user supplied Reddit API credentials."""
    return bool(os.environ.get("PRISMAFLOW_REDDIT_CLIENT_ID"))


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
    secret = os.environ.get("PRISMAFLOW_REDDIT_CLIENT_SECRET", "")
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
    client_id = os.environ.get("PRISMAFLOW_REDDIT_CLIENT_ID", "")
    if not client_id:
        raise CollectorUnavailable("PRISMAFLOW_REDDIT_CLIENT_ID is not set")
    headers = {"User-Agent": settings.user_agent, "Authorization": f"bearer {await _access_token(client, client_id)}"}
    params = {"q": query, "limit": 25, "sort": "relevance", "t": "year", "raw_json": 1}
    data = await _get_json(client, OAUTH_ENDPOINT, params, headers)
    try:
        children = data["data"]["children"]
    except (KeyError, TypeError) as exc:
        raise CollectorUnavailable("reddit returned an unexpected payload") from exc
    return _rank([p for c in children if (p := _post(c.get("data", {})))], limit)


async def _fetch_browser(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        from playwright.async_api import Error, async_playwright
    except ImportError as exc:
        raise CollectorUnavailable("Playwright is required for Reddit browser search") from exc

    url = WEB_ENDPOINT + "?" + urlencode({"q": query, "type": "posts", "sort": "relevance", "t": "year"})
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(timeout=10_000)
            try:
                page = await browser.new_page(locale="en-US")
                response = await page.goto(url, wait_until="domcontentloaded", timeout=12_000)
                if response is not None and response.status == 429:
                    raise RateLimited("reddit rate limit reached")
                if response is None or not response.ok:
                    status = response.status if response else "no response"
                    raise CollectorUnavailable(f"reddit browser search failed ({status})")
                await page.locator(POST_LINK).first.or_(
                    page.get_by_text(re.compile(r"^(no results found|we couldn.t find any results)", re.I))
                ).first.wait_for(state="visible", timeout=5_000)
                rows = await page.locator(POST_LINK).evaluate_all(_READ_POSTS)
            finally:
                await browser.close()
    except Error as exc:
        detail = (exc.message or type(exc).__name__).splitlines()[0]
        raise CollectorUnavailable(f"reddit browser search unavailable: {detail}") from exc

    posts = []
    seen: set[str] = set()
    for row in rows:
        if row["permalink"] in seen:
            continue
        try:
            row["created_utc"] = datetime.fromisoformat(row["created_utc"].replace("Z", "+00:00")).timestamp()
        except ValueError:
            row["created_utc"] = 0
        if post := _post(row):
            seen.add(row["permalink"])
            posts.append(post)
    return sorted(posts, key=lambda post: post["score"] + 2 * post["comments"], reverse=True)[:limit]


_READ_POSTS = r"""
links => links.flatMap(link => {
    const url = new URL(link.href);
    const thread = url.pathname.match(/^\/r\/([\w]+)\/comments\/([\w]+)(?:\/[^/]+)?\/?$/i);
    if (url.origin !== "https://www.reddit.com" || !thread) return [];
    const card = link.closest("shreddit-post, search-telemetry-tracker, article, [data-testid='post-container']") ?? link;
    const title = card.getAttribute("post-title")
        || card.querySelector("[data-testid='post-title'], [slot='title'], h2, h3")?.innerText
        || link.innerText || link.getAttribute("aria-label") || "";
    const body = card.querySelector("[slot='text-body'], [data-testid='post-content'], [data-testid='post-snippet']")?.innerText || "";
    const count = (attribute, label) => {
        const value = card.getAttribute(attribute);
        if (value !== null && /^-?\d+$/.test(value)) return Number(value);
        const match = card.innerText.match(new RegExp("(-?[\\d,.]+)\\s*([kmb]?)\\s+" + label + "\\b", "i"));
        if (!match) return 0;
        const scale = {k: 1e3, m: 1e6, b: 1e9}[match[2].toLowerCase()] ?? 1;
        return Math.round(Number(match[1].replaceAll(",", "")) * scale) || 0;
    };
    return [{
        title, selftext: body, subreddit: thread[1],
        permalink: `/r/${thread[1]}/comments/${thread[2]}/`,
        created_utc: card.getAttribute("created-timestamp") || card.querySelector("time")?.dateTime || "",
        score: count("score", "(?:upvotes?|votes?)"),
        num_comments: count("comment-count", "comments?"),
        over_18: card.hasAttribute("nsfw") || card.hasAttribute("over-18")
            || !!card.querySelector("[aria-label='NSFW'], [data-testid='nsfw-tag']"),
    }];
})
"""


async def search(db: Database, client: httpx.AsyncClient, query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Return popular Reddit threads matching a query, cached in api_cache.

    After a provider fails the collector stays closed for the negative-cache window
    instead of hammering it with every remaining query.
    """
    use_browser = os.environ.get("PRISMAFLOW_REDDIT_PLAYWRIGHT") == "1" or not credentials_configured()
    name = "playwright" if use_browser else "oauth"

    async def fetch_source() -> list[dict[str, Any]]:
        if time.time() < _blocked_until.get(name, 0.0):
            raise CollectorUnavailable("reddit temporarily unavailable")
        try:
            if use_browser:
                return await _fetch_browser(query, limit)
            return await _throttled(lambda: _fetch_oauth(client, query, limit))
        except RateLimited:
            _blocked_until[name] = time.time() + RATE_LIMIT_PAUSE
            raise
        except CollectorUnavailable:
            _blocked_until[name] = time.time() + settings.negative_cache_ttl_seconds
            raise

    async def fetch() -> list[dict[str, Any]]:
        if use_browser:
            return await _throttled(fetch_source, attempts=1)
        return await fetch_source()

    return await cached(
        db,
        f"reddit:{name}",
        query,
        {"limit": limit},
        fetch,
        settings.cache_ttl_seconds,
        settings.negative_cache_ttl_seconds,
    )
