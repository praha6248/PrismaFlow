"""Shared plumbing for market-data collectors: caching and error typing."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable

from ..database import Database


class CollectorUnavailable(RuntimeError):
    """Raised when a remote source refuses or fails to answer."""


def cache_key(source: str, query: str, params: dict[str, Any] | None = None) -> str:
    """Build a stable cache key for a collector request."""
    blob = json.dumps({"s": source, "q": query.lower().strip(), "p": params or {}}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


async def cached(
    db: Database,
    source: str,
    query: str,
    params: dict[str, Any],
    fetch: Callable[[], Awaitable[Any]],
    ttl: float,
    error_ttl: float,
) -> Any:
    """Serve a collector call from api_cache, fetching and storing it on a miss."""
    key = cache_key(source, query, params)
    hit = db.cache_get(key, ttl, error_ttl)
    if hit is not None:
        status, payload = hit
        if status == "error":
            raise CollectorUnavailable(payload.get("message", f"{source} unavailable"))
        return payload
    try:
        payload = await fetch()
    except CollectorUnavailable as exc:
        db.cache_put(key, source, query, "error", {"message": str(exc)})
        raise
    db.cache_put(key, source, query, "ok", payload)
    return payload
