"""Google Trends collector built on trendspy, calibrated against a fixed anchor keyword."""

from __future__ import annotations

import asyncio
import threading
import time
from statistics import mean
from typing import Any

from ..config import settings
from ..database import Database
from .base import CollectorUnavailable, cache_key, cached

MAX_KEYWORDS = 5
COOLDOWN_KEY = "trends:cooldown"
COOLDOWN_FIRST = 30 * 60
COOLDOWN_MAX = 6 * 60 * 60
_lock = threading.Lock()


class RateLimited(CollectorUnavailable):
    """Google Trends answered 429 and asks clients to slow down."""


def cooldown_left(db: Database, now: float | None = None) -> float:
    """Seconds until Google Trends may be asked again after a 429."""
    hit = db.cache_get(COOLDOWN_KEY, COOLDOWN_MAX * 4, 0)
    if hit is None:
        return 0.0
    return max(0.0, hit[1].get("until", 0.0) - (now or time.time()))


def start_cooldown(db: Database, now: float | None = None) -> float:
    """Pause all Trends requests, doubling the pause while 429s keep coming."""
    now = now or time.time()
    hit = db.cache_get(COOLDOWN_KEY, COOLDOWN_MAX * 4, 0)
    previous = hit[1].get("pause", 0.0) if hit else 0.0
    pause = min(COOLDOWN_MAX, previous * 2) if previous else COOLDOWN_FIRST
    db.cache_put(COOLDOWN_KEY, "trends", "cooldown", "ok", {"until": now + pause, "pause": pause})
    return pause


def growth_3m_vs_9m(series: list[float]) -> float | None:
    """Compare the mean of the last quarter with the mean of the nine months before it."""
    if len(series) < 16 or mean(series) < 1:
        return None
    window = max(1, round(len(series) / 4))
    recent = series[-window:]
    previous = series[:-window]
    base = mean(previous)
    if base <= 0:
        return 1.0 if mean(recent) > 0 else 0.0
    return (mean(recent) - base) / base


def _download(keywords: list[str], geo: str, timeframe: str) -> dict[str, Any]:
    from trendspy import Trends

    with _lock:
        try:
            frame = Trends(request_delay=1.5).interest_over_time(keywords, timeframe=timeframe, geo=geo)
        except Exception as exc:
            text = str(exc)
            if "429" in text or "Too Many Requests" in text:
                raise RateLimited("google trends: too many requests (429)") from exc
            raise CollectorUnavailable(f"google trends failed: {exc.__class__.__name__}: {text[:200]}") from exc
    if frame is None or frame.empty:
        return {"dates": [], "series": {k: [] for k in keywords}}
    if "isPartial" in frame.columns:
        frame = frame[~frame["isPartial"].astype(bool)]
    dates = [index.strftime("%Y-%m-%d") for index in frame.index]
    series = {}
    for keyword in keywords:
        column = keyword if keyword in frame.columns else None
        series[keyword] = [float(v) for v in frame[column].tolist()] if column else []
    return {"dates": dates, "series": series}


async def interest(
    db: Database,
    keywords: list[str],
    geo: str = "",
    timeframe: str = "today 12-m",
) -> dict[str, Any]:
    """Fetch interest over time for up to five keywords as one comparable batch."""
    unique = list(dict.fromkeys(k.strip() for k in keywords if k.strip()))[:MAX_KEYWORDS]
    if not unique:
        return {"dates": [], "series": {}}
    key = cache_key("trends", "|".join(unique), {"geo": geo, "tf": timeframe})
    hit = db.cache_get(key, settings.cache_ttl_seconds, 0)
    if hit is not None and hit[0] == "ok":
        return hit[1]
    left = cooldown_left(db)
    if left > 0:
        raise RateLimited(f"google trends: paused for {round(left / 60)} more min after a 429")
    try:
        data = await cached(
            db,
            "trends",
            "|".join(unique),
            {"geo": geo, "tf": timeframe},
            lambda: asyncio.to_thread(_download, unique, geo, timeframe),
            settings.cache_ttl_seconds,
            settings.negative_cache_ttl_seconds,
        )
    except RateLimited:
        start_cooldown(db)
        raise
    db.cache_put(COOLDOWN_KEY, "trends", "cooldown", "ok", {"until": 0.0, "pause": 0.0})
    return data


ANCHORS = {"pl": "kalendarz", "de": "kalender", "es": "calendario", "fr": "calendrier", "it": "calendario"}


def anchor_for(language: str) -> str:
    """Return the calibration keyword for a language, honouring an explicit override."""
    if settings.trend_anchor != "calendar":
        return settings.trend_anchor
    return ANCHORS.get(language, "calendar")


async def calibrated_growth(
    db: Database, keywords: list[str], geo: str = "", language: str = "en"
) -> dict[str, dict[str, Any]]:
    """Return per-keyword series and growth, batching keywords alongside the calibration anchor."""
    anchor = anchor_for(language)
    result: dict[str, dict[str, Any]] = {}
    pending = [k for k in dict.fromkeys(keywords) if k.lower() != anchor.lower()]
    step = MAX_KEYWORDS - 1
    for start in range(0, len(pending), step):
        batch = pending[start : start + step]
        data = await interest(db, [*batch, anchor], geo)
        anchor_series = data["series"].get(anchor) or []
        anchor_mean = mean(anchor_series) if anchor_series else 0.0
        for keyword in batch:
            series = data["series"].get(keyword) or []
            result[keyword] = {
                "dates": data["dates"],
                "series": series,
                "growth": growth_3m_vs_9m(series),
                "mean": mean(series) if series else 0.0,
                "anchor_ratio": (mean(series) / anchor_mean) if series and anchor_mean > 0 else None,
            }
    return result
