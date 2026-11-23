"""Collect public top-level comments on relevant review and tutorial videos."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from ..config import settings
from .base import CollectorUnavailable

API = "https://www.googleapis.com/youtube/v3"
_quota_retry = 0.0


def api_key() -> str:
    return os.environ.get("PRISMAFLOW_YOUTUBE_API_KEY", "").strip()


async def items(client: httpx.AsyncClient, resource: str, **params: str) -> list[dict]:
    global _quota_retry
    if time.monotonic() < _quota_retry:
        raise CollectorUnavailable("YouTube quota temporarily exhausted")
    try:
        response = await client.get(f"{API}/{resource}", params=params, headers={"X-Goog-Api-Key": api_key()}, timeout=12)
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CollectorUnavailable(f"YouTube request failed: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise CollectorUnavailable("unexpected YouTube response")
    if response.status_code != 200:
        reasons = {e.get("reason") for e in data.get("error", {}).get("errors", [])}
        if "commentsDisabled" in reasons or "videoNotFound" in reasons:
            return []
        if {"quotaExceeded", "dailyLimitExceeded"} & reasons:
            _quota_retry = time.monotonic() + 3600
        raise CollectorUnavailable(f"YouTube returned HTTP {response.status_code}")
    if not isinstance(data.get("items"), list):
        raise CollectorUnavailable("unexpected YouTube response")
    return data["items"]


async def search(client: httpx.AsyncClient, query: str, language: str) -> list[dict]:
    qualifiers = "recenzja|poradnik" if language == "pl" else "review|tutorial"
    oldest = time.time() - settings.discussion_max_age_days * 86400
    videos = await items(client, "search", part="snippet", type="video", maxResults="3",
                         q=f"{query} {qualifiers}", relevanceLanguage=language,
                         publishedAfter=datetime.fromtimestamp(oldest, timezone.utc).isoformat())
    posts = []
    for video in videos:
        video_id = video.get("id", {}).get("videoId")
        if not video_id:
            continue
        threads = await items(client, "commentThreads", part="snippet", videoId=video_id,
                              textFormat="plainText", order="relevance", maxResults="20")
        for thread in threads:
            info = thread.get("snippet", {})
            comment = info.get("topLevelComment", {})
            snippet = comment.get("snippet", {})
            text = (snippet.get("textDisplay") or "").strip()
            try:
                created = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")).timestamp()
            except (KeyError, ValueError):
                continue
            if not text or not comment.get("id") or created < oldest:
                continue
            posts.append(dict(title=text[:240], body=text[:1200], platform="youtube",
                              place=video.get("snippet", {}).get("channelTitle", ""),
                              url="https://www.youtube.com/watch?" + urlencode({"v": video_id, "lc": comment["id"]}),
                              created=created, score=snippet.get("likeCount", 0), comments=info.get("totalReplyCount", 0)))
    # Relevance is checked against the comment itself by the common collector before ranking and limiting.
    return posts
