"""Community discussions collector: Stack Exchange questions and Lemmy threads.

Both sources expose documented, keyless public APIs. Stack Exchange questions are phrased as
problems people have, which makes them strong pain-point evidence; Lemmy is a federated,
Reddit-like forum. When Reddit OAuth credentials are configured, Reddit threads are added too.
"""

from __future__ import annotations

import asyncio
import html
import math
import re
import time
from typing import Any, Awaitable, Callable

import httpx

from ..config import settings
from ..database import Database
from . import reddit
from .base import CollectorUnavailable, cached

STACKEXCHANGE_ENDPOINT = "https://api.stackexchange.com/2.3/search/advanced"
LEMMY_ENDPOINT = "https://lemmy.world/api/v3/search"
TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")
MIN_INTERVAL = 0.4

SITES: dict[str, tuple[str, ...]] = {
    "fitness": ("workout", "train", "exerc", "gym", "fitne", "muscl", "weigh", "runni", "cardi", "yoga", "stret", "strength"),
    "parenting": ("child", "kid", "kids", "baby", "babie", "paren", "toddl", "teen", "famil", "mother", "fathe", "autis", "adhd"),
    "cooking": ("cook", "recip", "food", "meal", "bake", "bakin", "kitch", "diet", "nutri", "vegan"),
    "diy": ("repai", "renov", "house", "home", "tool", "plumb", "elect", "furni"),
    "money": ("money", "budge", "save", "savin", "inves", "finan", "debt", "tax", "loan", "salar", "price"),
    "pets": ("pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "anima", "veter"),
    "gardening": ("garde", "plant", "flowe", "veget", "lawn", "seed"),
    "travel": ("trave", "trip", "fligh", "hotel", "touri", "vacat", "holid"),
    "outdoors": ("hike", "hikin", "campi", "climb", "trail", "outdo"),
    "sports": ("sport", "footb", "socce", "tenni", "baske", "swim", "cycli", "athle", "coach"),
    "bicycles": ("bike", "bikes", "bicyc", "cycli"),
    "music": ("music", "guita", "piano", "sing", "song", "instr"),
    "photo": ("photo", "camer", "lens"),
    "ux": ("ux", "ui", "usabi", "inter", "desig", "onboa"),
    "workplace": ("work", "job", "jobs", "caree", "boss", "colle", "offic", "remot"),
    "interpersonal": ("frien", "relat", "lonel", "socia", "motiv", "anxie", "stres", "confi"),
    "academia": ("stude", "unive", "study", "studi", "exam", "thesi", "resea"),
    "language-learning": ("langu", "learn", "vocab", "gramm", "fluen"),
    "freelancing": ("freel", "clien", "invoi"),
    "medicalsciences": ("healt", "medic", "sympt", "disea", "thera", "senso"),
    "softwarerecs": ("app", "apps", "softw", "track", "plann", "remin", "tool"),
}
DEFAULT_SITES = ("lifehacks", "softwarerecs")
NSFW = re.compile(r"nsfw|porn|onlyfans|gonewild|hentai", re.IGNORECASE)

_locks: dict[str, asyncio.Lock] = {}
_last_call: dict[str, float] = {}
_backoff_until: dict[str, float] = {}


def _clean(text: str, limit: int) -> str:
    text = WHITESPACE.sub(" ", html.unescape(TAG.sub(" ", text or ""))).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def terms(query: str) -> list[str]:
    """Return 5-character stems of the meaningful words of a query."""
    words = re.findall(r"\w+", query.casefold())
    return [w[:5] for w in words if len(w) >= 3] or [w for w in words if w]


STOPWORDS = {"for", "the", "and", "with", "how", "what", "when", "your", "you", "from", "into", "about", "best", "app", "apps"}
GENERIC = {"motiv", "train", "worko", "child", "kids", "peopl", "probl", "help", "learn", "plann", "sport", "famil", "home", "work", "daily", "tips", "ideas", "start"}


def _matches(stem: str, key: str) -> bool:
    return stem == key or (len(key) >= 5 and stem.startswith(key)) or (len(stem) >= 5 and len(key) >= 4 and key.startswith(stem))


def keywords(query: str) -> list[str]:
    """Return the query's words without stop words, as Stack Exchange matches every word."""
    words = [w for w in re.findall(r"\w+", query.casefold()) if len(w) >= 3 and w not in STOPWORDS]
    return words or re.findall(r"\w+", query.casefold())


def specific_word(query: str) -> str | None:
    """Return the most specific word of a query: the longest one that is not a generic topic word."""
    words = sorted(keywords(query), key=len, reverse=True)
    for word in words:
        if word[:5] not in GENERIC:
            return word
    return None


def pick_sites(query: str, limit: int = 2) -> list[str]:
    """Choose the Stack Exchange sites whose topic words best match an English query."""
    stems = terms(query)
    scored = []
    for site, keys in SITES.items():
        hits = sum(1 for stem in stems for key in keys if _matches(stem, key))
        if hits:
            scored.append((hits, site))
    scored.sort(key=lambda item: -item[0])
    chosen = [site for _, site in scored[:limit]]
    for site in DEFAULT_SITES:
        if len(chosen) >= limit:
            break
        if site not in chosen:
            chosen.append(site)
    return chosen


def relevant(text: str, stems: list[str], minimum: float) -> bool:
    """Tell whether enough query stems occur in a text."""
    if not stems:
        return True
    folded = text.casefold()
    return sum(1 for stem in stems if stem in folded) >= max(1, math.ceil(len(stems) * minimum))


async def _paced(name: str, call: Callable[[], Awaitable[Any]]) -> Any:
    lock = _locks.setdefault(name, asyncio.Lock())
    async with lock:
        wait = max(MIN_INTERVAL - (time.monotonic() - _last_call.get(name, 0.0)), _backoff_until.get(name, 0.0) - time.monotonic())
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[name] = time.monotonic()
        return await call()


async def _get(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> Any:
    try:
        response = await client.get(url, params=params, headers={"User-Agent": settings.user_agent}, timeout=12)
    except httpx.HTTPError as exc:
        raise CollectorUnavailable(f"request failed: {exc}") from exc
    if response.status_code in (400, 401, 403, 429, 502, 503):
        raise CollectorUnavailable(f"source refused the request (HTTP {response.status_code})")
    if response.status_code != 200:
        raise CollectorUnavailable(f"source returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise CollectorUnavailable("source returned malformed JSON") from exc


async def fetch_stackexchange(
    client: httpx.AsyncClient, query: str, site: str, limit: int, fallback: bool = True
) -> list[dict[str, Any]]:
    """Search one Stack Exchange site; when the full query is too strict, retry with its most specific word."""
    posts = await _stackexchange_query(client, " ".join(keywords(query)), site, terms(query), 0.6)
    word = specific_word(query)
    if fallback and len(posts) < 3 and word and word != " ".join(keywords(query)):
        known = {p["title"] for p in posts}
        stem = word[:5]
        posts += [
            p
            for p in await _stackexchange_query(client, word, site, terms(word), 1.0)
            if p["title"] not in known and stem in p["title"].casefold()
        ]
    return posts[:limit]


async def _stackexchange_query(client: httpx.AsyncClient, q: str, site: str, stems: list[str], minimum: float) -> list[dict[str, Any]]:
    params = {"order": "desc", "sort": "relevance", "q": q, "site": site, "pagesize": 20, "filter": "withbody"}
    data = await _paced("stackexchange", lambda: _get(client, STACKEXCHANGE_ENDPOINT, params))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise CollectorUnavailable("stack exchange returned an unexpected payload")
    if data.get("backoff"):
        _backoff_until["stackexchange"] = time.monotonic() + float(data["backoff"])
    if data.get("quota_remaining") == 0:
        raise CollectorUnavailable("stack exchange daily quota reached")
    posts = []
    for item in data["items"]:
        title = _clean(item.get("title", ""), 240)
        body = _clean(item.get("body", ""), 600)
        if not title or not relevant(title, stems, minimum):
            continue
        if int(item.get("score") or 0) < 1 and not item.get("answer_count"):
            continue
        posts.append(
            {
                "title": title,
                "body": body,
                "platform": "stackexchange",
                "place": site,
                "score": int(item.get("score") or 0),
                "comments": int(item.get("answer_count") or 0),
                "url": item.get("link"),
                "created": float(item.get("creation_date") or 0),
            }
        )
    return posts


async def fetch_lemmy(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    """Search Lemmy posts federated to lemmy.world."""
    params = {"q": query, "type_": "Posts", "sort": "TopAll", "listing_type": "All", "limit": 40}
    data = await _paced("lemmy", lambda: _get(client, LEMMY_ENDPOINT, params))
    if not isinstance(data, dict) or not isinstance(data.get("posts"), list):
        raise CollectorUnavailable("lemmy returned an unexpected payload")
    stems = terms(query)
    posts = []
    for item in data["posts"]:
        post, community, counts = item.get("post", {}), item.get("community", {}), item.get("counts", {})
        if post.get("nsfw") or community.get("nsfw") or post.get("removed") or post.get("deleted"):
            continue
        name = community.get("name") or ""
        if NSFW.search(name):
            continue
        title = _clean(post.get("name", ""), 240)
        if not title or not relevant(title, stems, 0.6):
            continue
        posts.append(
            {
                "title": title,
                "body": _clean(post.get("body", ""), 600),
                "platform": "lemmy",
                "place": name,
                "score": int(counts.get("score") or 0),
                "comments": int(counts.get("comments") or 0),
                "url": post.get("ap_id") or post.get("url"),
                "created": 0.0,
            }
        )
    return posts[:limit]


def _rank(posts: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ranked = []
    for post in sorted(posts, key=lambda p: p["score"] + 2 * p["comments"], reverse=True):
        key = post["title"].casefold()
        if key in seen:
            continue
        seen.add(key)
        ranked.append(post)
    return ranked[:limit]


async def search(db: Database, client: httpx.AsyncClient, query: str, language: str = "en", limit: int = 8) -> list[dict[str, Any]]:
    """Return popular community discussions for a query from every available source.

    Stack Exchange is English-only, so it is queried only for English queries; Lemmy is
    queried in every language. A source that fails is skipped; the collector raises only
    when every source failed.
    """
    jobs: list[tuple[str, str, Callable[[], Awaitable[list[dict[str, Any]]]]]] = []
    if language == "en":
        for index, site in enumerate(pick_sites(query)):
            jobs.append(
                (
                    f"community:stackexchange:{site}",
                    query,
                    lambda site=site, first=index == 0: fetch_stackexchange(client, query, site, limit, fallback=first),
                )
            )
    jobs.append(("community:lemmy", query, lambda: fetch_lemmy(client, query, limit)))

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for source, cache_query, fetch in jobs:
        try:
            results.extend(
                await cached(db, source, cache_query, {"limit": limit}, fetch, settings.cache_ttl_seconds, settings.negative_cache_ttl_seconds)
            )
        except CollectorUnavailable as exc:
            errors.append(f"{source.split(':', 1)[1]}: {exc}")
    if reddit.credentials_configured():
        try:
            for post in await reddit.search(db, client, query, limit):
                results.append({**post, "platform": "reddit", "place": post.get("subreddit", "")})
        except CollectorUnavailable as exc:
            errors.append(f"reddit: {exc}")
    if errors and not results and len(errors) >= len(jobs):
        raise CollectorUnavailable("; ".join(errors))
    return _rank(results, limit)
