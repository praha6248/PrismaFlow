"""Google Trends collector built on trendspy, calibrated against a fixed anchor keyword."""

from __future__ import annotations

import asyncio
import threading
from statistics import mean
from typing import Any

from ..config import settings
from ..database import Database
from .base import CollectorUnavailable, cached

MAX_KEYWORDS = 5
_lock = threading.Lock()


def growth_3m_vs_9m(series: list[float]) -> float | None:
    """Compare the mean of the last quarter with the mean of the nine months before it."""
    if len(series) < 16:
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
            raise CollectorUnavailable(f"google trends failed: {exc.__class__.__name__}: {exc}") from exc
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
    return await cached(
        db,
        "trends",
        "|".join(unique),
        {"geo": geo, "tf": timeframe},
        lambda: asyncio.to_thread(_download, unique, geo, timeframe),
        settings.cache_ttl_seconds,
        settings.negative_cache_ttl_seconds,
    )


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
