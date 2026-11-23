"""Openly licensed public-sector case studies as a style corpus for the case study narratives.

Reads raw HTML fetched earlier with the PrismaFlow User-Agent (robots.txt honoured), keeps only pages from
*.blog.gov.uk (Open Government Licence v3.0), digital.gov and blog.18f.org (US federal works, public domain),
and stores plain text with attribution outside the repository. It then measures the house style the narrative
templates in build_case_study.py follow: sentence length, voice, sentence openers and section headings.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = Path.home() / ".local/share/PrismaFlow/training-data/case-studies"

LICENCES = {
    "blog.gov.uk": ("Open Government Licence v3.0", "Contains public sector information licensed under the Open Government Licence v3.0."),
    "digital.gov": ("US public domain", "Work of the US General Services Administration, not subject to copyright in the United States."),
    "blog.18f.org": ("US public domain", "Work of 18F (US General Services Administration) staff, not subject to copyright in the United States."),
}


def licence(url: str) -> tuple[str, str] | None:
    host = urlparse(url).hostname or ""
    if host.endswith(".blog.gov.uk"):
        return LICENCES["blog.gov.uk"]
    if host in ("digital.gov", "blog.18f.org"):
        return LICENCES[host]
    return None


def article(html: str) -> tuple[str, list[tuple[int, str]], list[str]]:
    """Title, headings and paragraphs of the main post body."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    title = (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
    headings, paragraphs = [], []
    for node in root.find_all(["h2", "h3", "p", "li"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name in ("h2", "h3"):
            headings.append((int(node.name[1]), text))
        elif len(text.split()) >= 8 and not re.search(r"(?i)cookie|subscribe|share this|sharing and comments|leave a comment", text):
            paragraphs.append(text)
    return title, headings, paragraphs


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"‘])", text) if len(s.split()) >= 3]


def style(docs: list[dict]) -> dict:
    """Corpus-level style measures used to shape the target narratives."""
    all_sentences = [s for d in docs for p in d["paragraphs"] for s in sentences(p)]
    lengths = sorted(len(s.split()) for s in all_sentences)
    openers = Counter(" ".join(s.split()[:2]).strip(",").lower() for s in all_sentences)
    we = sum(1 for s in all_sentences if re.search(r"\b(we|our|us)\b", s, re.I))
    i_voice = sum(1 for s in all_sentences if re.search(r"\bI\b", s))
    ratio = sum(1 for s in all_sentences if re.search(r"\b\d+ (of|out of) \d+\b", s))
    percent = sum(1 for s in all_sentences if "%" in s or "per cent" in s or "percent" in s)
    hedges = Counter(m.lower() for s in all_sentences for m in re.findall(r"\b(some|most|many|few|several|often|sometimes|all|every|none)\b", s, re.I))
    claims = Counter(m.lower() for s in all_sentences for m in re.findall(r"\b(we found|we learned|we learnt|we saw|we noticed|we heard|we tested|we changed|we will|we’ll|we're going to|next steps?|what we learned)\b", s, re.I))
    headings = Counter(h.lower() for d in docs for _, h in d["headings"])
    return {
        "documents": len(docs),
        "words": sum(len(p.split()) for d in docs for p in d["paragraphs"]),
        "sentences": len(all_sentences),
        "sentence_words_median": lengths[len(lengths) // 2] if lengths else 0,
        "sentence_words_p90": lengths[int(len(lengths) * 0.9)] if lengths else 0,
        "first_person_plural_share": round(we / max(1, len(all_sentences)), 3),
        "first_person_singular_share": round(i_voice / max(1, len(all_sentences)), 3),
        "x_of_y_sentences": ratio,
        "percent_sentences": percent,
        "quantifiers": dict(hedges.most_common(12)),
        "finding_phrases": dict(claims.most_common(15)),
        "top_openers": dict(openers.most_common(30)),
        "top_headings": dict(headings.most_common(30)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True, help="folder with the fetched HTML pages")
    parser.add_argument("--index", type=Path, required=True, help="structure3.json listing the fetched URLs")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "text").mkdir(exist_ok=True)

    docs, manifest, skipped = [], [], []
    for page in json.loads(args.index.read_text(encoding="utf-8")):
        url = page["url"]
        terms = licence(url)
        path = args.raw / (re.sub(r"\W+", "_", url)[-80:] + ".html")
        if page.get("status") != 200 or not path.exists():
            skipped.append({"url": url, "reason": "not fetched"})
            continue
        if not terms:
            skipped.append({"url": url, "reason": "licence not open"})
            continue
        title, headings, paragraphs = article(path.read_text(encoding="utf-8", errors="replace"))
        words = sum(len(p.split()) for p in paragraphs)
        if words < 300:
            skipped.append({"url": url, "reason": f"too short ({words} words)"})
            continue
        slug = re.sub(r"\W+", "-", urlparse(url).path).strip("-")[-90:] or "index"
        name = f"{urlparse(url).hostname}--{slug}.txt"
        body = "\n\n".join([f"# {title}", *[f"{'#' * level} {text}" for level, text in headings], *paragraphs])
        (args.out / "text" / name).write_text(f"Source: {url}\nLicence: {terms[0]}\nAttribution: {terms[1]}\n\n{body}\n", encoding="utf-8")
        docs.append({"url": url, "title": title, "headings": headings, "paragraphs": paragraphs})
        manifest.append({"url": url, "title": title, "licence": terms[0], "attribution": terms[1], "file": f"text/{name}", "words": words})

    stats = style(docs)
    (args.out / "manifest.json").write_text(json.dumps({"documents": manifest, "skipped": skipped}, indent=1, ensure_ascii=False), encoding="utf-8")
    (args.out / "style.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "corpus" / "case_study_style.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "corpus" / "case_study_manifest.json").write_text(
        json.dumps([{k: d[k] for k in ("url", "title", "licence", "words")} for d in manifest], indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"kept {len(manifest)} documents, {stats['words']} words; skipped {len(skipped)}")


if __name__ == "__main__":
    main()
