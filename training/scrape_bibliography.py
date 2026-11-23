"""Collect an extended UI/UX bibliography from the open OpenAlex catalogue (CC0 metadata).

Only bibliographic metadata is stored: authors, title, venue, year, DOI, open-access link and
citation count. Results are written to docs/bibliography-extended.md and corpus/openalex.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
DOCS = ROOT.parent / "docs" / "bibliography-extended.md"
OUT = ROOT / "corpus" / "openalex.json"
API = "https://api.openalex.org/works"
HEADERS = {"User-Agent": "PrismaFlow-bibliography/0.1 (local research script)"}
PER_TOPIC = 12

TOPICS = {
    "Pointing, Fitts' law and touch input": [
        "fitts law", "touch screen target size", "thumb interaction mobile", "pointing performance touch",
        "one-handed mobile interaction",
    ],
    "Choice, decision time and cognitive load": [
        "hick hyman law", "cognitive load theory", "working memory capacity chunks", "choice reaction time menu",
    ],
    "Task-time models (GOMS, KLM)": ["keystroke-level model", "GOMS model", "cognitive modeling interface"],
    "Menus, navigation and information architecture": [
        "menu selection performance", "information architecture navigation", "card sorting", "information scent",
    ],
    "Visual design, perception and layout": [
        "visual hierarchy interface", "gestalt principles interface design", "visual complexity web pages aesthetics",
        "first impressions website aesthetics", "eye tracking web page layout", "color contrast readability",
        "typography legibility screen",
    ],
    "Usability evaluation and heuristics": [
        "heuristic evaluation", "usability testing", "system usability scale", "think aloud usability",
        "usability inspection methods",
    ],
    "User experience, emotion and satisfaction": [
        "user experience definition", "hedonic pragmatic quality", "aesthetic usability effect", "user engagement scale",
    ],
    "Mobile UI design": ["mobile user interface design", "mobile usability", "smartphone app usability guidelines"],
    "Accessibility": [
        "web accessibility guidelines", "WCAG evaluation", "accessibility mobile apps", "motor impairment touch screen",
    ],
    "Forms, input and errors": ["web form design", "input error prevention interface", "text entry mobile"],
    "Onboarding, persuasion and dark patterns": ["dark patterns", "persuasive technology", "onboarding mobile apps"],
    "Design process and methods": [
        "user-centered design", "design thinking", "personas design", "participatory design", "double diamond design",
        "requirements prioritization MoSCoW",
    ],
    "Design systems and UI components": ["design system components", "user interface patterns", "wireframing prototyping"],
}


def fetch(client: httpx.Client, query: str) -> list[dict]:
    """Return the most cited works whose title matches the query."""
    params = {
        "filter": f"title.search:{query},type:article|conference-paper|book|book-chapter|review|standard",
        "sort": "cited_by_count:desc",
        "per_page": PER_TOPIC,
        "select": "id,doi,title,publication_year,cited_by_count,authorships,primary_location,open_access,type",
    }
    for attempt in range(3):
        response = client.get(API, params=params)
        if response.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        response.raise_for_status()
        return response.json().get("results", [])
    return []


def entry(work: dict, topic: str, query: str) -> dict:
    """Flatten an OpenAlex work into a citation record."""
    authors = [a["author"]["display_name"] for a in work.get("authorships", []) if a.get("author")]
    source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name")
    return {
        "openalex": work["id"],
        "title": (work.get("title") or "").strip(),
        "year": work.get("publication_year"),
        "authors": authors,
        "venue": source,
        "doi": work.get("doi"),
        "oa_url": (work.get("open_access") or {}).get("oa_url"),
        "cited_by": work.get("cited_by_count", 0),
        "type": work.get("type"),
        "topic": topic,
        "query": query,
    }


def cite(item: dict) -> str:
    """Format one record as a Markdown list item."""
    names = item["authors"]
    who = ", ".join(names[:3]) + (" et al." if len(names) > 3 else "") if names else "Anon."
    venue = f" *{item['venue']}*." if item["venue"] else ""
    link = item["doi"] or item["openalex"]
    oa = f" [open access]({item['oa_url']})" if item["oa_url"] and item["oa_url"] != item["doi"] else ""
    return f"- {who} ({item['year']}). {item['title']}.{venue} {link}{oa} — cited {item['cited_by']}×"


def main() -> None:
    """Query every topic, de-duplicate and write the JSON and Markdown outputs."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict] = {}
    with httpx.Client(headers=HEADERS, timeout=30) as client:
        for topic, queries in TOPICS.items():
            for query in queries:
                for work in fetch(client, query):
                    if not work.get("title") or work["id"] in records:
                        continue
                    records[work["id"]] = entry(work, topic, query)
                time.sleep(0.3)
    items = sorted(records.values(), key=lambda r: (-r["cited_by"]))
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [
        "# Extended UI/UX bibliography",
        "",
        "Collected automatically by `training/scrape_bibliography.py` from the OpenAlex catalogue (CC0 metadata).",
        f"For each query the most cited matching works are listed: {len(items)} unique works in total.",
        "Only metadata is stored here. Read the works through their DOI or open-access link.",
        "The curated core list, with the rules PrismaFlow uses, is in [bibliography.md](bibliography.md).",
        "",
    ]
    for topic in TOPICS:
        group = [r for r in items if r["topic"] == topic]
        if not group:
            continue
        lines += [f"## {topic}", ""] + [cite(r) for r in group] + [""]
    DOCS.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(items)} works -> {DOCS}")


if __name__ == "__main__":
    main()
