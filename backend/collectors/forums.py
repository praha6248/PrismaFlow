"""Read public forum RSS and Atom feeds once and search their entries locally."""

from __future__ import annotations

import html
import os
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx

from ..database import Database
from .base import CollectorUnavailable, cached

def feeds(language: str) -> list[str]:
    raw = os.environ.get(f"PRISMAFLOW_RSS_FEEDS_{language.upper()}", "")
    return list(dict.fromkeys(url.strip() for url in raw.split(",") if url.strip().startswith(("https://", "http://"))))


def plain(text: str, limit: int) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())[:limit]


async def fetch(client: httpx.AsyncClient, url: str) -> list[dict]:
    try:
        async with client.stream("GET", url, follow_redirects=True, timeout=12) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise CollectorUnavailable("forum feed exceeds 2 MB")
            base = str(response.url)
        if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
            raise CollectorUnavailable("unexpected XML declaration in forum feed")
        root = ElementTree.fromstring(data)
    except (httpx.HTTPError, ElementTree.ParseError) as exc:
        raise CollectorUnavailable(f"forum feed unavailable: {type(exc).__name__}") from exc
    if root.tag.rsplit("}", 1)[-1] not in ("rss", "feed", "RDF"):
        raise CollectorUnavailable("unexpected forum feed format")

    posts = []
    for entry in [*root.findall(".//{*}item"), *root.findall("{*}entry")][:150]:
        title = plain(entry.findtext("{*}title") or "", 240)
        link = next((el.get("href") or el.text for el in entry.findall("{*}link")
                     if el.get("rel", "alternate") == "alternate"), None)
        if not title or not link:
            continue
        permalink = urljoin(base, link)
        if urlsplit(permalink).scheme not in ("http", "https"):
            continue
        date = entry.findtext("{*}pubDate") or entry.findtext("{*}published") or entry.findtext("{*}updated") or ""
        try:
            created = parsedate_to_datetime(date).timestamp()
        except (ValueError, TypeError, OverflowError):
            try:
                created = datetime.fromisoformat(date.replace("Z", "+00:00")).timestamp()
            except (ValueError, OverflowError):
                created = 0
        body = entry.findtext("{*}description") or entry.findtext("{*}summary") or entry.findtext("{*}content") or ""
        posts.append(dict(title=title, body=plain(body, 600), platform="rss", place=urlsplit(base).hostname,
                          url=permalink, created=created, score=0, comments=0))
    return posts


async def recent(db: Database, client: httpx.AsyncClient, url: str, max_age_days: int) -> list[dict]:
    posts = await cached(db, "forum-feed", url, {}, lambda: fetch(client, url), 3600, 600)
    oldest = time.time() - max_age_days * 86400
    return [post for post in posts if post["created"] >= oldest]
