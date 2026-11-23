"""Scrape an openly licensed UI/UX text corpus used to distil the UX knowledge set.

Only sources whose licence allows reuse with attribution are fetched:
- W3C WCAG 2.2 Understanding documents (W3C Software and Document License),
- GOV.UK Design System components and patterns (Open Government Licence v3.0),
- MDN Web Docs accessibility guides (CC BY-SA 2.5),
- Wikipedia articles in English and Polish (CC BY-SA 4.0), read from /wiki/ pages because robots.txt blocks the API.
Copyrighted guidelines and books are cited in docs/bibliography.md but never scraped.
robots.txt is honoured and requests are rate limited. Raw text stays in corpus/raw (not committed);
corpus/manifest.json records the URL, licence and size of every document.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "corpus" / "raw"
MANIFEST = ROOT / "corpus" / "manifest.json"
AGENT = "PrismaFlow-corpus/0.1 (local research script)"
DELAY = 0.6

W3C = "W3C Software and Document License"
OGL = "Open Government Licence v3.0"
MDN = "CC BY-SA 2.5 (MDN contributors)"
WIKI = "CC BY-SA 4.0 (Wikipedia contributors)"

WIKI_EN = [
    "Usability", "User experience", "User experience design", "User interface design", "Interaction design",
    "Human–computer interaction", "Fitts's law", "Hick's law", "Keystroke-level model", "GOMS",
    "Cognitive load", "The Magical Number Seven, Plus or Minus Two", "Heuristic evaluation", "Usability testing",
    "Affordance", "Signifier (semiotics)", "Gestalt psychology", "Principles of grouping", "Visual hierarchy",
    "Information architecture", "Progressive disclosure", "Dark pattern", "Mental model", "Card sorting",
    "Persona (user experience)", "User journey", "Customer journey", "Wireframe", "Website wireframe",
    "Responsive web design", "Mobile app development", "Web accessibility", "Accessibility",
    "Web Content Accessibility Guidelines", "Material Design", "Human interface guidelines", "Design system",
    "Flat design", "Skeuomorph", "Microinteraction", "Double Diamond (design process model)", "MoSCoW method",
    "Design thinking", "User-centered design", "Participatory design", "System usability scale",
    "Think aloud protocol", "A/B testing", "Cognitive walkthrough", "Paper prototyping", "Software prototyping",
    "Typography", "Readability", "Legibility", "Color contrast", "Contrast (vision)", "Color blindness",
    "Navigation bar", "Hamburger button", "Breadcrumb navigation", "Tab (interface)", "Modal window",
    "Form (document)", "Placeholder text", "Error message", "Onboarding", "Skeleton screen", "Infinite scrolling",
    "Pagination", "Touchscreen", "Multi-touch", "Gesture recognition", "Haptic technology", "Dialog box",
    "Toast (computing)", "Tooltip", "Drop-down list", "Checkbox", "Radio button", "Toggle switch (widget)",
    "Slider (computing)", "Icon (computing)", "Font size", "White space (visual arts)", "Grid (graphic design)",
    "F-pattern", "Banner blindness", "Serial-position effect", "Von Restorff effect", "Zeigarnik effect",
    "Peak–end rule", "Aesthetic–usability effect", "Choice overload", "Paradox of choice", "Decision fatigue",
    "Nudge theory", "Persuasive technology", "Gamification", "Information foraging", "Human factors and ergonomics",
    "ISO 9241", "Jakob Nielsen (usability consultant)", "Don Norman", "The Design of Everyday Things",
    "Don't Make Me Think", "Ben Shneiderman", "Direct manipulation interface", "WIMP (computing)",
    "Graphical user interface", "Look and feel", "Usability engineering", "Contextual inquiry",
    "Affinity diagram", "Storyboard", "Use case", "User story", "Minimum viable product", "Kano model",
]

WIKI_PL = [
    "Użyteczność", "User experience", "Projektowanie interakcji", "Interakcja człowiek-komputer",
    "Prawo Fittsa", "Prawo Hicka", "Ergonomia", "Psychologia postaci", "Architektura informacji",
    "Graficzny interfejs użytkownika", "Interfejs użytkownika", "Dostępność (projektowanie)",
    "Web Content Accessibility Guidelines", "Prototyp", "Makieta", "Persona (marketing)", "Typografia",
    "Czytelność", "Kontrast", "Daltonizm", "Ekran dotykowy", "Grywalizacja", "Metoda MoSCoW",
    "Design thinking", "Test A/B", "Obciążenie poznawcze", "Pamięć robocza", "Projektowanie zorientowane na użytkownika",
    "Responsive web design", "Material Design", "Skeuomorfizm", "Flat design", "Ikona (informatyka)",
    "Okno dialogowe", "Pole wyboru", "Przycisk opcji", "Lista rozwijana", "Pasek nawigacji", "Menu (informatyka)",
    "Minimum viable product", "Model Kano", "Historyjka użytkownika",
]

MDN_PAGES = [
    "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Accessibility/What_is_accessibility",
    "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Accessibility/HTML",
    "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Accessibility/CSS_and_JavaScript",
    "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Accessibility/WAI-ARIA_basics",
    "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Accessibility/Multimedia",
    "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Accessibility/Mobile",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Perceivable",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Operable",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Understandable",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Robust",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Perceivable/Color_contrast",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Keyboard",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Mobile_accessibility_checklist",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Information_for_Web_authors",
    "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Cognitive_accessibility",
    "https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Using_for_accessibility",
]


class Fetcher:
    """Polite HTTP client that honours robots.txt and spaces out requests."""

    def __init__(self) -> None:
        self.client = httpx.Client(headers={"User-Agent": AGENT}, timeout=30, follow_redirects=True)
        self.robots: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        """Return whether robots.txt of the host allows the URL."""
        host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if host not in self.robots:
            parser = RobotFileParser()
            try:
                response = self.client.get(f"{host}/robots.txt")
                parser.parse(response.text.splitlines() if response.status_code == 200 else [])
                self.robots[host] = parser
            except httpx.HTTPError:
                self.robots[host] = None
        parser = self.robots[host]
        return parser is None or parser.can_fetch(AGENT, url)

    def get(self, url: str, **params: str) -> httpx.Response | None:
        """GET a URL when allowed, returning None on errors."""
        if not self.allowed(url):
            print(f"robots.txt disallows {url}")
            return None
        time.sleep(DELAY)
        try:
            response = self.client.get(url, params=params or None)
        except httpx.HTTPError as exc:
            print(f"error {url}: {exc}")
            return None
        if response.status_code != 200:
            print(f"{response.status_code} {url}")
            return None
        return response


def clean(text: str) -> str:
    """Collapse whitespace and drop empty lines."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def html_text(html: str, selector: str) -> tuple[str, str]:
    """Return the page title and the readable text of its main content."""
    soup = BeautifulSoup(html, "lxml")
    title = (soup.find("h1") or soup.title or soup).get_text(" ", strip=True)
    main = soup.select_one(selector) or soup.body or soup
    for tag in main.select("script, style, nav, header, footer, aside, .app-pane__subnav, .govuk-breadcrumbs, pre, code, form"):
        tag.decompose()
    return title, clean(main.get_text("\n"))


def links(html: str, base: str, pattern: str) -> list[str]:
    """Return unique absolute links whose path matches the pattern."""
    soup = BeautifulSoup(html, "lxml")
    found = []
    for a in soup.find_all("a", href=True):
        url = urljoin(base, a["href"]).split("#", 1)[0]
        if re.search(pattern, urlparse(url).path) and url not in found:
            found.append(url)
    return found


def wcag(fetch: Fetcher) -> list[dict]:
    """Fetch every WCAG 2.2 Understanding document."""
    base = "https://www.w3.org/WAI/WCAG22/Understanding/"
    index = fetch.get(base)
    if index is None:
        return []
    docs = []
    for url in links(index.text, base, r"^/WAI/WCAG22/Understanding/[a-z0-9-]+(\.html)?$"):
        page = fetch.get(url)
        if page is None:
            continue
        title, text = html_text(page.text, "main")
        docs.append({"source": "wcag22", "url": url, "title": title, "lang": "en", "license": W3C, "text": text})
    return docs


def govuk(fetch: Fetcher) -> list[dict]:
    """Fetch GOV.UK Design System component and pattern guidance."""
    docs = []
    for section in ("components", "patterns", "styles"):
        base = f"https://design-system.service.gov.uk/{section}/"
        index = fetch.get(base)
        if index is None:
            continue
        for url in links(index.text, base, rf"^/{section}/[a-z0-9-]+/$"):
            page = fetch.get(url)
            if page is None:
                continue
            title, text = html_text(page.text, "main")
            docs.append({"source": "govuk", "url": url, "title": title, "lang": "en", "license": OGL, "text": text})
    return docs


def mdn(fetch: Fetcher) -> list[dict]:
    """Fetch MDN accessibility guides."""
    docs = []
    for url in MDN_PAGES:
        page = fetch.get(url)
        if page is None:
            continue
        title, text = html_text(page.text, "main article, main")
        docs.append({"source": "mdn", "url": str(page.url), "title": title, "lang": "en", "license": MDN, "text": text})
    return docs


def wikipedia(fetch: Fetcher, lang: str, titles: list[str]) -> list[dict]:
    """Fetch Wikipedia article pages (robots.txt allows /wiki/ but not the API) and keep the prose."""
    stop = {"See also", "References", "External links", "Further reading", "Notes", "Bibliography",
            "Zobacz też", "Przypisy", "Bibliografia", "Linki zewnętrzne", "Uwagi"}
    docs = []
    for title in titles:
        url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
        page = fetch.get(url)
        if page is None:
            continue
        soup = BeautifulSoup(page.text, "lxml")
        body = soup.select_one("#mw-content-text .mw-parser-output")
        if body is None:
            continue
        for tag in body.select("table, sup, style, script, figure, .mw-editsection, .navbox, .reflist, .thumb, .hatnote, .metadata, .infobox"):
            tag.decompose()
        parts = []
        for node in body.find_all(["h2", "h3", "p", "li"], recursive=True):
            text = node.get_text(" ", strip=True)
            if node.name == "h2" and text in stop:
                break
            if node.name in ("h2", "h3"):
                parts.append(f"\n## {text}")
            elif len(text) > 30:
                parts.append(text)
        text = clean("\n".join(parts))
        if len(text) < 400:
            continue
        heading = soup.select_one("#firstHeading")
        docs.append({
            "source": f"wikipedia-{lang}",
            "url": str(page.url),
            "title": heading.get_text(" ", strip=True) if heading else title,
            "lang": lang,
            "license": WIKI,
            "text": text,
        })
    return docs


def slug(text: str) -> str:
    """Filesystem-safe file name."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70] or "doc"


def main() -> None:
    """Scrape all sources and write raw text files plus the manifest."""
    RAW.mkdir(parents=True, exist_ok=True)
    fetch = Fetcher()
    docs = wcag(fetch) + govuk(fetch) + mdn(fetch) + wikipedia(fetch, "en", WIKI_EN) + wikipedia(fetch, "pl", WIKI_PL)
    docs = list({d["url"]: d for d in docs}.values())
    manifest = []
    for doc in docs:
        name = f"{doc['source']}--{slug(doc['title'])}.txt"
        (RAW / name).write_text(f"{doc['title']}\n{doc['url']}\n\n{doc['text']}\n", encoding="utf-8")
        manifest.append({k: doc[k] for k in ("source", "url", "title", "lang", "license")} | {"file": name, "chars": len(doc["text"])})
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    by_source: dict[str, list[int]] = {}
    for item in manifest:
        by_source.setdefault(item["source"], []).append(item["chars"])
    for source, sizes in by_source.items():
        print(f"{source}: {len(sizes)} docs, {sum(sizes):,} chars")


if __name__ == "__main__":
    main()
