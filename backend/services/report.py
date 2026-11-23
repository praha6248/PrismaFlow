"""Research report (Markdown, HTML, PDF) and an SVG of the prototype screens that Figma imports."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from ..models import Flow

TEXT = {
    "pl": {
        "title": "Raport z badań",
        "problem": "Problem",
        "persona": "Persona",
        "quote_real": "cytat z notatek",
        "quote_model": "cytat wygenerowany przez model",
        "themes": "Tematy z tablicy",
        "notes": "notatek",
        "empathy": "Mapa empatii",
        "says": "Mówi",
        "thinks": "Myśli",
        "does": "Robi",
        "feels": "Czuje",
        "journey": "Ścieżka użytkownika",
        "phase": {"before": "Przed", "during": "W trakcie", "after": "Po"},
        "pain": "Frustracja",
        "hmw": "Jak moglibyśmy",
        "hypotheses": "Hipotezy z wywiadów",
        "status": {"open": "do sprawdzenia", "confirmed": "potwierdzona", "rejected": "obalona"},
        "backlog": "Backlog (MoSCoW i RICE)",
        "rice": "RICE",
        "flow": "Ekrany",
        "tests": "Testy z użytkownikami",
        "success": "sukces",
        "seconds": "średni czas",
        "predicted": "przewidywany (KLM)",
        "misclicks": "kliknięć bez efektu na osobę",
        "none": "Brak danych.",
        "source": "źródło",
        "inferred": "wniosek modelu",
        "footer": "Wygenerowano w PrismaFlow. Elementy oznaczone jako wniosek modelu wymagają sprawdzenia z ludźmi.",
        "sources": {"evidence": "sieć", "note": "notatka", "interview": "wywiad", "test": "test"},
    },
    "en": {
        "title": "Research report",
        "problem": "Problem",
        "persona": "Persona",
        "quote_real": "quote from notes",
        "quote_model": "quote written by the model",
        "themes": "Affinity board themes",
        "notes": "notes",
        "empathy": "Empathy map",
        "says": "Says",
        "thinks": "Thinks",
        "does": "Does",
        "feels": "Feels",
        "journey": "User journey",
        "phase": {"before": "Before", "during": "During", "after": "After"},
        "pain": "Pain point",
        "hmw": "How might we",
        "hypotheses": "Interview hypotheses",
        "status": {"open": "open", "confirmed": "confirmed", "rejected": "rejected"},
        "backlog": "Backlog (MoSCoW and RICE)",
        "rice": "RICE",
        "flow": "Screens",
        "tests": "Usability tests",
        "success": "success",
        "seconds": "mean time",
        "predicted": "predicted (KLM)",
        "misclicks": "dead taps per person",
        "none": "No data.",
        "source": "source",
        "inferred": "model inference",
        "footer": "Generated with PrismaFlow. Items marked as model inference still need checking with people.",
        "sources": {"evidence": "web", "note": "note", "interview": "interview", "test": "test"},
    },
}


def _origin(item: dict[str, Any], words: dict[str, Any]) -> str:
    source = item.get("from")
    if not source:
        return f" _({words['inferred']})_"
    label = f"{words['sources'].get(source['source'], source['source'])}{', ' + source['label'] if source.get('label') else ''}"
    return f" _({words['source']}: {label} — „{source['text'][:120]}”)_"


def report_markdown(context: dict[str, Any]) -> str:
    """Render the research report as Markdown."""
    project = context["project"]
    words = TEXT["pl" if project["language"] == "pl" else "en"]
    problem, persona = context.get("problem"), context.get("persona")
    lines = [f"# {words['title']} — {project['name']}", ""]
    lines += [f"## {words['problem']}", f"**{problem['title']}** — {problem['description']}" if problem else words["none"], ""]
    if persona:
        real = (persona.get("profile") or {}).get("quote_source")
        lines += [
            f"## {words['persona']}",
            f"**{persona['name']}**, {persona['age']}, {persona['role']}",
            "",
            f"> „{persona['quote']}” _({words['quote_real'] if real else words['quote_model']})_",
            "",
        ]
        lines += [f"- {key}: {value}" for key, value in (persona.get("profile") or {}).items() if key != "quote_source" and value]
        lines.append("")
    board = context.get("board") or {}
    lines.append(f"## {words['themes']}")
    themes = board.get("themes") or []
    for theme in themes:
        members = [n for n in board.get("notes", []) if n.get("theme") == theme["id"]]
        lines.append(f"### {theme['name']} ({len(members)} {words['notes']})")
        if theme.get("insight"):
            lines.append(theme["insight"])
        lines += [
            f"- ({words['sources'].get(n['source'], n['source'])}{', ' + n['label'] if n.get('label') else ''}) {n['text'][:200]}"
            for n in members[:5]
        ]
        lines.append("")
    if not themes:
        lines += [words["none"], ""]
    empathy = context.get("empathy")
    lines.append(f"## {words['empathy']}")
    if empathy:
        for key in ("says", "thinks", "does", "feels"):
            lines.append(f"### {words[key]}")
            lines += [f"- {item['text']}{_origin(item, words)}" for item in empathy.get(key, [])]
            lines.append("")
        lines.append(f"## {words['journey']}")
        for stage in empathy.get("journey", []):
            pain = f" **{words['pain']}:** {stage['pain']}." if stage.get("pain") else ""
            lines.append(
                f"- **{words['phase'][stage['phase']]} · {stage['name']}** ({stage['emotion']:+d}): {stage['action']}. „{stage['thought']}”.{pain}"
            )
        lines.append("")
        if empathy.get("hmw_chosen"):
            lines += [f"## {words['hmw']}", f"**{empathy['hmw_chosen']}**", ""]
    else:
        lines += [words["none"], ""]
    validation = context.get("validation") or {}
    lines.append(f"## {words['hypotheses']}")
    for hypothesis in validation.get("hypotheses", []):
        lines.append(f"- **{words['status'][hypothesis.get('status', 'open')]}** — {hypothesis['text']}")
        lines += [f"  - {q['person']}: „{q['quote']}”" for q in hypothesis.get("quotes", [])[:3]]
    if not validation.get("hypotheses"):
        lines.append(words["none"])
    lines += ["", f"## {words['backlog']}"]
    for feature in context.get("features", []):
        score = feature.get("rice") or {}
        lines.append(
            f"- **{feature['priority'].upper()}** {feature['title']} — {feature['description']} "
            f"({words['rice']} {score.get('score', 0)}: R {score.get('reach', 0)} · I {score.get('impact', 1)} · "
            f"C {round(100 * score.get('confidence', 0.5))}% · E {score.get('effort', 2)})"
        )
    flow = Flow.model_validate(context.get("flow") or {"screens": []})
    lines += ["", f"## {words['flow']}"]
    names = {s.id: s.name for s in flow.screens}
    for screen in flow.screens:
        targets = ", ".join(f"{e.label} → {names[e.target]}" for e in screen.elements if e.target in names)
        lines.append(f"- **{screen.name}**" + (f": {targets}" if targets else ""))
    tests = context.get("tests") or {}
    lines += ["", f"## {words['tests']}"]
    for task in tests.get("tasks", []):
        if not task["attempts"]:
            continue
        timing = f", {words['seconds']} {task['seconds']} s" if task["seconds"] is not None else ""
        predicted = f" ({words['predicted']} {task['predicted']} s)" if task["predicted"] else ""
        misses = f", {words['misclicks']}: {task['misclicks']}" if task.get("misclicks") else ""
        lines.append(f"- **{task['goal_name']}**: {words['success']} {task['successes']}/{task['attempts']}{timing}{predicted}{misses}")
        lines += [f"  - {q['participant']}: „{q['quote']}”" for q in task["quotes"][:3]]
    if not tests.get("participants"):
        lines.append(words["none"])
    lines += ["", "---", words["footer"], ""]
    return "\n".join(lines)


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)


def markdown_html(markdown: str, title: str) -> str:
    """Convert the report's small Markdown subset into a print-ready HTML page."""
    body = []
    stack: list[int] = []
    for line in markdown.splitlines():
        indent = (len(line) - len(line.lstrip())) // 2
        stripped = line.strip()
        if stripped.startswith("- "):
            while stack and stack[-1] > indent:
                body.append("</ul>")
                stack.pop()
            if not stack or stack[-1] < indent:
                body.append("<ul>")
                stack.append(indent)
            body.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        while stack:
            body.append("</ul>")
            stack.pop()
        if not stripped:
            continue
        if stripped == "---":
            body.append("<hr>")
        elif match := re.match(r"(#{1,3}) (.*)", stripped):
            level = len(match.group(1))
            body.append(f"<h{level}>{_inline(match.group(2))}</h{level}>")
        elif stripped.startswith("> "):
            body.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
        else:
            body.append(f"<p>{_inline(stripped)}</p>")
    while stack:
        body.append("</ul>")
        stack.pop()
    style = (
        "body{font-family:Montserrat,Helvetica,Arial,sans-serif;color:#101010;max-width:760px;margin:40px auto;"
        "padding:0 24px;line-height:1.55;font-size:13px}h1,h2,h3{font-family:'Crimson Text',Georgia,serif;font-weight:600}"
        "h1{font-size:30px;margin-bottom:8px}h2{font-size:21px;margin-top:28px;border-bottom:2px solid #f783e9;padding-bottom:4px}"
        "h3{font-size:16px;margin-bottom:4px}blockquote{margin:8px 0;padding:6px 14px;border-left:3px solid #f783e9;background:#fdf2fb}"
        "em{color:#5c5466}hr{border:none;border-top:1px solid #e6dcef;margin-top:32px}li{margin:3px 0}"
    )
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
        f"<style>{style}</style></head><body>{''.join(body)}</body></html>"
    )


async def write_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Print the HTML report to PDF with Playwright's Chromium when it is installed."""
    try:
        from playwright.async_api import Error, async_playwright
    except ImportError:
        return False
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(timeout=10_000)
            try:
                page = await browser.new_page()
                await page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=15_000)
                await page.pdf(path=str(pdf_path), format="A4", margin={"top": "16mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
            finally:
                await browser.close()
    except Error:
        return False
    return pdf_path.is_file()


SCREEN_W = 390
SCREEN_H = 844
GAP = 120
ELEMENT_H = {"S": 36, "M": 48, "L": 60}
ZONE_Y = {"top": 120, "center": 360, "bottom": 640}


def prototype_svg(flow: Flow, style: dict[str, Any] | None = None) -> str:
    """Lay the screens out side by side as 390×844 frames; Figma turns each group into editable layers."""
    style = style or {}
    primary = style.get("primary", "#f34cdf")
    background = style.get("background", "#ffffff")
    text_color = style.get("text", "#101010")
    on_primary = style.get("on_primary", "#ffffff")
    radius = {"sharp": 4, "soft": 12, "round": 24}.get(style.get("corners", "soft"), 12)
    width = max(1, len(flow.screens)) * (SCREEN_W + GAP) + GAP
    height = SCREEN_H + 2 * GAP
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'font-family="Montserrat, Helvetica, Arial, sans-serif">'
    ]
    for index, screen in enumerate(flow.screens):
        x = GAP + index * (SCREEN_W + GAP)
        y = GAP
        parts.append(f'<g id="{escape(screen.id)}"><title>{escape(screen.name)}</title>')
        parts.append(f'<rect x="{x}" y="{y}" width="{SCREEN_W}" height="{SCREEN_H}" rx="32" fill="{background}" stroke="#d9cfe3"/>')
        parts.append(f'<text x="{x + 24}" y="{y + 64}" font-size="24" font-weight="600" fill="{text_color}">{escape(screen.name)}</text>')
        used = {"top": 0, "center": 0, "bottom": 0}
        for element in screen.elements:
            h = ELEMENT_H[element.size]
            offset = used[element.zone]
            used[element.zone] += h + 14
            ey = y + ZONE_Y[element.zone] + offset
            filled = element.type == "button" and element.target
            fill = primary if filled else "#f4eff8"
            color = on_primary if filled else text_color
            parts.append(f'<g id="{escape(element.id)}">')
            if element.type == "link":
                parts.append(f'<text x="{x + 24}" y="{ey + h / 2 + 5}" font-size="15" fill="{primary}" text-decoration="underline">{escape(element.label)}</text>')
            else:
                parts.append(f'<rect x="{x + 24}" y="{ey}" width="{SCREEN_W - 48}" height="{h}" rx="{radius}" fill="{fill}"/>')
                parts.append(f'<text x="{x + 40}" y="{ey + h / 2 + 5}" font-size="15" fill="{color}">{escape(element.label)}</text>')
            parts.append("</g>")
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)
