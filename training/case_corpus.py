"""Real UX case studies as a local style corpus for the case study narratives.

Reads the page list in corpus.json (designers' own portfolio case studies, all rights reserved, plus
public-sector case studies under the Open Government Licence v3.0 or in the US public domain) and extracts
headings and paragraphs per section. Everything derived from the pages stays next to the corpus, outside the
repository: plain text, style statistics and a phrasebook of section lead-ins that recur across several
authors. build_case_study.py reads the phrasebook and statistics from there; nothing quoted from a page is
written into the repository.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

DEFAULT_CORPUS = Path.home() / ".local/share/PrismaFlow-training/case-studies"

SECTIONS = {
    "summary": r"overview|summary|tl;?dr|introduction|about the project|project brief|background|the brief",
    "context": r"problem|challenge|context|opportunity|goal|why|statement",
    "research": r"research|survey|interview|competit|discover|audit|benchmark|insight|findings|data",
    "synthesis": r"persona|affinity|journey|empathy|synthes|define|how might|mental model|user needs|pain",
    "ideation": r"ideat|brainstorm|priorit|feature|moscow|scope|mvp|crazy|sketch|concept",
    "design": r"design|flow|wirefram|prototyp|architecture|sitemap|ui|visual|style|solution|iteration|hi-?fi|lo-?fi",
    "testing": r"test|usability|validat|feedback|evaluat",
    "outcomes": r"outcome|result|impact|metric|measur",
    "reflection": r"reflect|learn|takeaway|retro|next step|what'?s next|conclusion|lesson|future|liked|lacked|longed",
}
SKIP = re.compile(r"(?i)cookie|subscribe|all rights reserved|powered by|back to top|let'?s (talk|connect|work)|contact me|©")


def section_of(heading: str) -> str | None:
    text = heading.lower()
    for key, pattern in SECTIONS.items():
        if re.search(pattern, text):
            return key
    return None


def extract(html: str) -> list[tuple[str | None, str]]:
    """(section, paragraph) pairs in page order; the section is taken from the closest heading above."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    current, out, seen = None, [], set()
    for node in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
        if not text or text in seen or SKIP.search(text):
            continue
        seen.add(text)
        if node.name.startswith("h") and len(text.split()) <= 12:
            current = section_of(text) or current
        elif len(text.split()) >= 8:
            out.append((current, text))
    return out


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"‘])", text) if len(s.split()) >= 4]


def lead_in(sentence: str) -> str | None:
    """The opening clause of a sentence when it is a short, fact-free connective."""
    match = re.match(r"^([A-Z][^,;:]{3,40})[,:]\s", sentence)
    if not match:
        return None
    clause = match.group(1)
    if re.search(r"\d|[A-Z]", clause[1:]) or len(clause.split()) > 6:
        return None
    return clause


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS, help="folder with corpus.json and pages/")
    args = parser.parse_args()
    pages = json.loads((args.corpus / "corpus.json").read_text(encoding="utf-8"))
    (args.corpus / "text").mkdir(exist_ok=True)

    per_section: dict[str, list[str]] = defaultdict(list)
    leads: dict[str, Counter] = defaultdict(Counter)
    lead_docs: dict[tuple[str, str], set[str]] = defaultdict(set)
    kinds: dict[str, list[str]] = defaultdict(list)
    manifest = []
    for page in pages:
        path = Path(page["file"])
        if not path.exists():
            continue
        pairs = extract(path.read_text(encoding="utf-8", errors="replace"))
        name = path.stem + ".txt"
        (args.corpus / "text" / name).write_text(
            f"Source: {page['url']}\nLicence: {page['license']}\n\n" + "\n\n".join(f"[{s or '-'}] {p}" for s, p in pairs) + "\n", encoding="utf-8"
        )
        for section, paragraph in pairs:
            for sentence in sentences(paragraph):
                kinds[page["kind"]].append(sentence)
                if section:
                    per_section[section].append(sentence)
                    clause = lead_in(sentence)
                    if clause:
                        leads[section][clause.lower()] += 1
                        lead_docs[(section, clause.lower())].add(page["url"])
        manifest.append({"url": page["url"], "kind": page["kind"], "licence": page["license"], "paragraphs": len(pairs), "text": f"text/{name}"})

    def measures(rows: list[str]) -> dict:
        lengths = sorted(len(s.split()) for s in rows) or [0]
        return {
            "sentences": len(rows),
            "sentence_words_median": lengths[len(lengths) // 2],
            "sentence_words_p90": lengths[int(len(lengths) * 0.9)],
            "we_share": round(sum(1 for s in rows if re.search(r"\b(we|our|us)\b", s, re.I)) / max(1, len(rows)), 3),
            "i_share": round(sum(1 for s in rows if re.search(r"\b(I|my|me)\b", s)) / max(1, len(rows)), 3),
            "x_of_y_share": round(sum(1 for s in rows if re.search(r"\b\d+ (of|out of) \d+\b", s)) / max(1, len(rows)), 3),
            "number_share": round(sum(1 for s in rows if re.search(r"\d", s)) / max(1, len(rows)), 3),
        }

    style = {
        "pages": len(manifest),
        "by_kind": {kind: measures(rows) for kind, rows in kinds.items()},
        "by_section": {key: measures(rows) for key, rows in per_section.items()},
    }
    phrasebook = {
        section: [clause for clause, count in counter.most_common() if len(lead_docs[(section, clause)]) >= 2][:15]
        for section, counter in leads.items()
    }
    (args.corpus / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (args.corpus / "style.json").write_text(json.dumps(style, indent=1, ensure_ascii=False), encoding="utf-8")
    (args.corpus / "phrasebook.json").write_text(json.dumps(phrasebook, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(style, indent=1))
    print(json.dumps(phrasebook, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
