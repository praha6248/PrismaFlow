"""Forum quotes the user pastes by hand, stored as community evidence of the project."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from ..database import Database

MIN_WORDS = 4
MAX_CHARS = 600


def split_quotes(text: str) -> list[str]:
    """One quote per paragraph; single lines are kept together unless every line is a quote of its own."""
    blocks = [b for b in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if b.strip()]
    if len(blocks) == 1 and all(len(line.split()) >= MIN_WORDS for line in blocks[0].splitlines() if line.strip()):
        blocks = [line for line in blocks[0].splitlines() if line.strip()]
    quotes = []
    for block in blocks:
        quote = " ".join(block.split()).strip().strip("\"'„”“‘’«»").strip()
        if len(quote.split()) >= MIN_WORDS:
            quotes.append(quote[:MAX_CHARS])
    return list(dict.fromkeys(quotes))


def place_of(url: str | None, place: str) -> str:
    if place.strip():
        return place.strip()[:80]
    host = urlparse(url or "").hostname or ""
    return host.removeprefix("www.") or "forum"


def pasted_quotes(db: Database, project_id: int) -> list[dict[str, Any]]:
    """Every quote the user pasted into the project, newest first."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, node_id, source, title, body, url, weight, meta FROM evidence "
            "WHERE project_id = ? AND json_extract(meta, '$.pasted') = 1 ORDER BY created_at DESC, id DESC",
            (project_id,),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["meta"] = json.loads(item["meta"] or "{}")
        out.append(item)
    return out


def add_quotes(db: Database, project_id: int, text: str, url: str | None = None, place: str = "") -> dict[str, Any]:
    """Store pasted quotes on the project's root node and return how many were new."""
    root = next((n for n in db.list_nodes(project_id) if n["is_root"]), None)
    if root is None:
        raise ValueError("project has no map yet")
    quotes = split_quotes(text)
    if not quotes:
        raise ValueError(f"no quote with at least {MIN_WORDS} words")
    before = len(pasted_quotes(db, project_id))
    platform = place_of(url, place)
    for quote in quotes:
        db.add_evidence(
            project_id,
            root["id"],
            "community",
            quote,
            body=quote,
            url=url or None,
            weight=5.0,
            meta={"pasted": True, "platform": platform, "place": platform},
        )
    items = pasted_quotes(db, project_id)
    return {"added": len(items) - before, "quotes": items}


def remove_quote(db: Database, project_id: int, evidence_id: int) -> dict[str, Any]:
    """Delete one pasted quote; evidence collected from the web is never touched."""
    with db.connect() as conn:
        conn.execute(
            "DELETE FROM evidence WHERE id = ? AND project_id = ? AND json_extract(meta, '$.pasted') = 1",
            (evidence_id, project_id),
        )
    return {"quotes": pasted_quotes(db, project_id)}


def quote_notes(db: Database, project_id: int) -> list[dict[str, Any]]:
    """Pasted quotes in the shape of real notes, so a persona can quote one word for word."""
    return [{"text": q["body"] or q["title"], "source": "forum", "label": q["meta"].get("platform", "forum")} for q in pasted_quotes(db, project_id)]
