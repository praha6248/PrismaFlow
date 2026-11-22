"""Google Autocomplete suggestions collector."""

from __future__ import annotations

import httpx

from ..config import settings
from ..database import Database
from .base import CollectorUnavailable, cached

ENDPOINT = "https://suggestqueries.google.com/complete/search"

EXPANSIONS = {
    "pl": ("", " dla", " jak", " problem", " aplikacja"),
    "en": ("", " for", " how to", " problem", " app"),
    "de": ("", " für", " wie", " problem", " app"),
}


async def _fetch(client: httpx.AsyncClient, query: str, language: str, geo: str) -> list[str]:
    params = {"client": "firefox", "q": query, "hl": language}
    if geo:
        params["gl"] = geo.lower()
    try:
        response = await client.get(ENDPOINT, params=params)
    except httpx.HTTPError as exc:
        raise CollectorUnavailable(f"autocomplete request failed: {exc}") from exc
    if response.status_code != 200:
        raise CollectorUnavailable(f"autocomplete returned HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise CollectorUnavailable("autocomplete returned malformed JSON") from exc
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return []
    return [str(s) for s in data[1] if isinstance(s, str)]


async def suggestions(
    db: Database,
    client: httpx.AsyncClient,
    query: str,
    language: str,
    geo: str = "",
) -> list[str]:
    """Return autocomplete suggestions for a single query, cached in api_cache."""
    return await cached(
        db,
        "autocomplete",
        query,
        {"hl": language, "gl": geo},
        lambda: _fetch(client, query, language, geo),
        settings.cache_ttl_seconds,
        settings.negative_cache_ttl_seconds,
    )


async def expanded_suggestions(
    db: Database,
    client: httpx.AsyncClient,
    query: str,
    language: str,
    geo: str = "",
    limit: int = 24,
) -> list[str]:
    """Return de-duplicated suggestions for a query and its intent-revealing variants."""
    seen: dict[str, None] = {}
    base = query.strip().lower()
    for suffix in EXPANSIONS.get(language, EXPANSIONS["en"]):
        try:
            batch = await suggestions(db, client, f"{query}{suffix}", language, geo)
        except CollectorUnavailable:
            if not suffix:
                raise
            continue
        for item in batch:
            text = item.strip()
            if text and text.lower() != base:
                seen.setdefault(text, None)
        if len(seen) >= limit:
            break
    return list(seen)[:limit]
