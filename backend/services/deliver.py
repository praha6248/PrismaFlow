"""Deliver phase: user flow graph, live UX audit, AI optimisation and the handoff pack."""

from __future__ import annotations

import math
import os
import re
import subprocess
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import networkx as nx

from ..config import data_dir
from ..database import Database
from ..models import Flow, FlowDraft, FlowElement, FlowScreen, SuggestionSet
from ..ollama_client import OllamaError
from .discover import LANGUAGE_NAMES, StructuredLLM
from .jobs import ProgressFn, WarnFn

HICK_A = 0.25
HICK_B = 0.15
HICK_LIMIT = 7
FITTS_LIMIT = 4.5
KLM_MENTAL = 1.35
FITTS_A = 0.1
FITTS_B = 0.15
WCAG_AA = 24
WCAG_AAA = 44
TARGET_WIDTH = {"S": 24, "M": 40, "L": 56}
THUMB_DISTANCE = {"bottom": 120, "center": 320, "top": 560}
ZONE_NAMES = {"bottom": "Dół", "center": "Centrum", "top": "Górny róg"}
SIZE_NAMES = {"S": "mały", "M": "średni", "L": "duży"}
COLUMN_GAP = 250
ROW_GAP = 190

FLOW_SYSTEM = """You are a senior UX designer running the Deliver phase of the Double Diamond.
Design the shortest user flow of a mobile app that lets the persona reach value with the Must-have features.
Rules:
- Write screen names and labels in {language}.
- 3 to 5 screens: exactly one "start" screen and exactly one "goal" screen where the persona gets the main value.
- Every screen except the goal has at least one element whose target is another screen; targets use exact screen names.
- Put each primary action as a large (L) button in the bottom zone; secondary actions medium; minor links small.
- Elements are only interactive controls a user taps: buttons, links, selects, inputs, toggles (on/off settings)
  or lists of choices. Never use elements for headings, greetings or messages.
- Labels are short verbs or nouns in 1-3 words, without exclamation marks or colons.
- Keep 2-4 elements per screen; options is 1 for buttons and links and the number of visible items for lists.
- Back navigation is provided by the system, do not add "back" elements.
- Assign every Must-have feature to the screen where it lives using its exact title."""

OPTIMIZE_SYSTEM = """You are a UX auditor. Propose concrete, small changes that fix the audit findings of a mobile user flow.
Rules:
- Write title and reason in {language}.
- Use only these operations: resize (value S, M or L), move_zone (value top, center or bottom),
  group_options (hide extra choices on a crowded screen behind a "more" control), add_transition (connect a dead-end
  screen; element is the new button label and value the exact target screen name), remove_element.
- Reference screens and elements by their exact names and labels from the flow.
- Prioritise: dead ends, Fitts problems on frequent actions, touch targets below 44 px, Hick overload, then path length.
- Never propose a change that keeps an element as it is; each suggestion must change a different element.
- title is at most 8 words, reason at most 10 words."""


def _id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6]}"


def graph(flow: Flow) -> nx.DiGraph:
    """Build the directed screen graph; parallel transitions keep their labels."""
    g = nx.DiGraph()
    ids = {s.id for s in flow.screens}
    for screen in flow.screens:
        g.add_node(screen.id, name=screen.name, kind=screen.kind)
    for screen in flow.screens:
        for element in screen.elements:
            if element.target in ids and element.target != screen.id:
                if g.has_edge(screen.id, element.target):
                    g.edges[screen.id, element.target]["labels"].append(element.label)
                else:
                    g.add_edge(screen.id, element.target, labels=[element.label])
    return g


def hick_time(options: int) -> float:
    """Hick-Hyman decision time in seconds for n equally likely choices."""
    return HICK_A + HICK_B * math.log2(options + 1)


def fitts_index(size: str, zone: str) -> float:
    """Fitts index of difficulty from target width and distance from the thumb rest position."""
    return math.log2(2 * THUMB_DISTANCE[zone] / TARGET_WIDTH[size])


def movement_time(size: str, zone: str) -> float:
    """Fitts movement time in seconds, MT = a + b * ID."""
    return FITTS_A + FITTS_B * fitts_index(size, zone)


def klm_time(flow: Flow, path: list[str]) -> dict[str, Any] | None:
    """Keystroke-Level Model estimate of the time to walk a screen path.

    Each step adds mental preparation (M), the Hick decision time of the screen and the Fitts
    movement time of the element that leads to the next screen.
    """
    if len(path) < 2:
        return None
    by_id = {s.id: s for s in flow.screens}
    total = 0.0
    steps = []
    for current, following in zip(path, path[1:]):
        screen = by_id[current]
        options = max(1, sum(e.options for e in screen.elements))
        candidates = [e for e in screen.elements if e.target == following]
        element = min(candidates, key=lambda e: movement_time(e.size, e.zone))
        seconds = KLM_MENTAL + hick_time(options) + movement_time(element.size, element.zone)
        total += seconds
        steps.append({"screen": screen.name, "element": element.label, "seconds": round(seconds, 2)})
    return {"seconds": round(total, 1), "steps": steps}


def target_sizes(flow: Flow) -> dict[str, Any]:
    """Check touch target sizes against WCAG 2.2 (2.5.8 AA: 24 px, 2.5.5 AAA: 44 px)."""
    elements = [(s, e) for s in flow.screens for e in s.elements]
    small = [
        {
            "screen_id": s.id,
            "screen": s.name,
            "element_id": e.id,
            "element": e.label,
            "size": e.size,
            "pixels": TARGET_WIDTH[e.size],
            "primary": bool(e.target),
        }
        for s, e in elements
        if TARGET_WIDTH[e.size] < WCAG_AAA
    ]
    return {
        "total": len(elements),
        "aaa": len(elements) - len(small),
        "aa": sum(1 for _, e in elements if TARGET_WIDTH[e.size] >= WCAG_AA),
        "below_aaa": small,
    }


def audit(flow: Flow) -> dict[str, Any]:
    """Analyse the flow: steps and KLM time to goal, Hick, Fitts, WCAG target sizes, dead ends and unreachable screens."""
    g = graph(flow)
    by_id = {s.id: s for s in flow.screens}
    start = next((s for s in flow.screens if s.kind == "start"), flow.screens[0] if flow.screens else None)
    goal = next((s for s in flow.screens if s.kind == "goal"), None)

    steps: dict[str, Any] = {"value": None, "path": [], "status": "missing"}
    klm = None
    if start and goal:
        try:
            path = nx.shortest_path(g, start.id, goal.id)
            steps = {"value": len(path) - 1, "path": [by_id[i].name for i in path], "status": "ok"}
            klm = klm_time(flow, path)
        except nx.NetworkXNoPath:
            steps = {"value": None, "path": [], "status": "no_path"}

    hick = []
    for screen in flow.screens:
        options = sum(e.options for e in screen.elements)
        if not options:
            continue
        seconds = hick_time(options)
        hick.append(
            {
                "screen_id": screen.id,
                "screen": screen.name,
                "options": options,
                "seconds": round(seconds, 2),
                "warning": options > HICK_LIMIT,
                "hide": max(0, options - 5) if options > HICK_LIMIT else 0,
            }
        )
    hick.sort(key=lambda h: h["options"], reverse=True)

    fitts = []
    for screen in flow.screens:
        for element in screen.elements:
            index = fitts_index(element.size, element.zone)
            if index > FITTS_LIMIT:
                fitts.append(
                    {
                        "screen_id": screen.id,
                        "screen": screen.name,
                        "element_id": element.id,
                        "element": element.label,
                        "size": element.size,
                        "zone": element.zone,
                        "index": round(index, 2),
                    }
                )
    fitts.sort(key=lambda f: f["index"], reverse=True)

    dead_ends = [
        {"screen_id": s.id, "screen": s.name}
        for s in flow.screens
        if s.kind != "goal" and g.out_degree(s.id) == 0
    ]
    reachable = nx.descendants(g, start.id) | {start.id} if start else set()
    unreachable = [{"screen_id": s.id, "screen": s.name} for s in flow.screens if s.id not in reachable]

    targets = target_sizes(flow)
    return {
        "screens": len(flow.screens),
        "transitions": g.number_of_edges(),
        "steps": steps,
        "klm": klm,
        "targets": targets,
        "hick": hick,
        "fitts": fitts,
        "dead_ends": dead_ends,
        "unreachable": unreachable,
        "constants": {
            "hick_a": HICK_A,
            "hick_b": HICK_B,
            "hick_limit": HICK_LIMIT,
            "fitts_limit": FITTS_LIMIT,
            "fitts_a": FITTS_A,
            "fitts_b": FITTS_B,
            "klm_mental": KLM_MENTAL,
            "wcag_aa": WCAG_AA,
            "wcag_aaa": WCAG_AAA,
        },
        "issues": len(fitts)
        + len(dead_ends)
        + len(unreachable)
        + sum(1 for h in hick if h["warning"])
        + sum(1 for t in targets["below_aaa"] if t["primary"]),
    }


def layout(flow: Flow) -> Flow:
    """Place screens in columns by their distance from the start screen."""
    if not flow.screens:
        return flow
    g = graph(flow)
    start = next((s for s in flow.screens if s.kind == "start"), flow.screens[0])
    depth = nx.single_source_shortest_path_length(g, start.id)
    last = max(depth.values(), default=0)
    rows: dict[int, int] = {}
    for screen in flow.screens:
        column = depth.get(screen.id, last + 1)
        row = rows.get(column, 0)
        rows[column] = row + 1
        screen.x = column * COLUMN_GAP
        screen.y = row * ROW_GAP + (column % 2) * 40
    return flow


def _key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in normalized if c.isalnum())


def from_draft(draft: FlowDraft, features: list[dict[str, Any]]) -> Flow:
    """Turn the model's draft into a flow with ids, resolved targets and feature links."""
    screens: list[FlowScreen] = []
    names: dict[str, str] = {}
    for item in draft.screens:
        key = _key(item.name)
        if key in names:
            continue
        screen_id = _id("s")
        names[key] = screen_id
        screens.append(FlowScreen(id=screen_id, name=item.name, kind=item.kind))
    titles = {_key(f["title"]): f["id"] for f in features}
    for screen, item in zip(screens, [d for d in draft.screens if names.get(_key(d.name))]):
        screen.feature_ids = list(dict.fromkeys(titles[k] for k in map(_key, item.features) if k in titles))
        for element in item.elements:
            target = names.get(_key(element.target)) if element.target else None
            screen.elements.append(
                FlowElement(
                    id=_id("e"),
                    label=element.label,
                    type=element.type,
                    size=element.size,
                    zone=element.zone,
                    options=element.options,
                    target=target if target != screen.id else None,
                )
            )
    kinds = [s.kind for s in screens]
    if "start" not in kinds and screens:
        screens[0].kind = "start"
    if kinds.count("start") > 1:
        for screen in [s for s in screens if s.kind == "start"][1:]:
            screen.kind = "step"
    if "goal" not in [s.kind for s in screens] and len(screens) > 1:
        screens[-1].kind = "goal"
    return layout(Flow(screens=screens))


def fallback_suggestions(report: dict[str, Any], flow: Flow) -> list[dict[str, Any]]:
    """Deterministic suggestions derived straight from the audit."""
    suggestions = []
    goal = next((s for s in flow.screens if s.kind == "goal"), None)
    for dead in report["dead_ends"][:1]:
        if goal:
            suggestions.append(
                {
                    "title": f"Połącz ekran „{dead['screen']}” z celem",
                    "reason": "Ślepa uliczka zatrzymuje użytkownika",
                    "op": "add_transition",
                    "screen_id": dead["screen_id"],
                    "element_id": None,
                    "value": goal.id,
                    "label": "Dalej",
                }
            )
    for item in report["fitts"][:2]:
        suggestions.append(
            {
                "title": f"Powiększ „{item['element']}” i przenieś na dół",
                "reason": f"Trudny cel: indeks Fittsa {item['index']}",
                "op": "move_zone",
                "screen_id": item["screen_id"],
                "element_id": item["element_id"],
                "value": "bottom",
                "label": None,
            }
        )
    flagged = {s.get("element_id") for s in suggestions}
    for item in [t for t in report["targets"]["below_aaa"] if t["primary"] and t["element_id"] not in flagged][:1]:
        suggestions.append(
            {
                "title": f"Powiększ „{item['element']}” do min. 44 px",
                "reason": "Cel dotykowy poniżej WCAG 2.5.5 (AAA)",
                "op": "resize",
                "screen_id": item["screen_id"],
                "element_id": item["element_id"],
                "value": "L",
                "label": None,
            }
        )
    for item in [h for h in report["hick"] if h["warning"]][:1]:
        suggestions.append(
            {
                "title": f"Ukryj {item['hide']} opcji w sekcji „Więcej”",
                "reason": f"{item['screen']}: {item['options']} opcji = {item['seconds']} s decyzji",
                "op": "group_options",
                "screen_id": item["screen_id"],
                "element_id": None,
                "value": "",
                "label": None,
            }
        )
    for item in suggestions:
        item["id"] = _id("g")
    return suggestions


def apply_suggestion(flow: Flow, suggestion: dict[str, Any]) -> Flow:
    """Apply one accepted suggestion to the flow."""
    screen = next((s for s in flow.screens if s.id == suggestion["screen_id"]), None)
    if screen is None:
        raise LookupError("the screen of this suggestion no longer exists")
    element = next((e for e in screen.elements if e.id == suggestion.get("element_id")), None)
    op, value = suggestion["op"], suggestion.get("value") or ""
    if op in ("resize", "move_zone", "remove_element") and element is None:
        raise LookupError("the element of this suggestion no longer exists")
    if op == "resize":
        element.size = value if value in TARGET_WIDTH else "L"
    elif op == "move_zone":
        element.zone = value if value in THUMB_DISTANCE else "bottom"
        if element.size == "S":
            element.size = "M"
        if element.type in ("button", "link") and element.size == "M" and element.zone == "bottom":
            element.size = "L"
    elif op == "remove_element":
        screen.elements = [e for e in screen.elements if e.id != element.id]
    elif op == "add_transition":
        if not any(s.id == value for s in flow.screens):
            raise LookupError("the target screen of this suggestion no longer exists")
        screen.elements.append(
            FlowElement(id=_id("e"), label=suggestion.get("label") or "Dalej", type="button", size="L", zone="bottom", target=value)
        )
    elif op == "group_options":
        keep = [e for e in screen.elements if e.target or e.size == "L"]
        rest = [e for e in screen.elements if e not in keep]
        if len(rest) > 1:
            screen.elements = keep + [rest[0].model_copy(update={"options": 1})] + [
                FlowElement(id=_id("e"), label="Więcej", type="select", size="M", zone="center", options=1)
            ]
        else:
            for e in screen.elements:
                if e.options > 3:
                    e.options = 3
    return flow


def _documents_dir() -> Path:
    try:
        out = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    path = Path(out) if out and Path(out).is_dir() and Path(out) != Path.home() else None
    return (path or data_dir()) / "PrismFlow"


def slug(text: str) -> str:
    """Return a filesystem-friendly slug."""
    normalized = unicodedata.normalize("NFKD", text.casefold().replace("ł", "l"))
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:40] or "projekt"


class DeliverService:
    """Generates, audits and optimises the user flow and exports the handoff pack."""

    def __init__(self, db: Database, llm: StructuredLLM, export_root: Path | None = None) -> None:
        self.db = db
        self.llm = llm
        self.export_root = export_root

    def flow(self, project_id: int) -> Flow:
        """Return the stored flow, or an empty one."""
        stored = self.db.get_flow(project_id)
        return Flow.model_validate(stored["flow"]) if stored else Flow()

    def state(self, project_id: int) -> dict[str, Any]:
        """Return everything the Deliver studio needs."""
        project = self.db.get_project(project_id)
        if project is None:
            raise LookupError(f"project {project_id} not found")
        stored = self.db.get_flow(project_id)
        flow = Flow.model_validate(stored["flow"]) if stored else Flow()
        return {
            "project": project,
            "problem": next((p for p in self.db.list_problems(project_id) if p["chosen"]), None),
            "persona": self.db.chosen_persona(project_id),
            "features": [f for f in self.db.list_features(project_id) if f["priority"] != "wont"],
            "flow": flow.model_dump(),
            "audit": audit(flow),
            "suggestions": stored["suggestions"] if stored else [],
        }

    def save(self, project_id: int, flow: Flow) -> dict[str, Any]:
        """Store an edited flow and return it with a fresh audit."""
        if self.db.get_project(project_id) is None:
            raise LookupError(f"project {project_id} not found")
        ids = {s.id for s in flow.screens}
        for screen in flow.screens:
            for element in screen.elements:
                if element.target not in ids:
                    element.target = None
        self.db.save_flow(project_id, flow.model_dump())
        return {"flow": flow.model_dump(), "audit": audit(flow)}

    def _language(self, project_id: int) -> str:
        project = self.db.get_project(project_id)
        return LANGUAGE_NAMES.get(project["language"], "the project's language") if project else "English"

    async def generate(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Ask the local model for a first flow built around the Must-have features."""
        state = self.state(project_id)
        persona, problem = state["persona"], state["problem"]
        features = state["features"]
        if not features:
            raise ValueError("add features in Develop first")
        progress(0.1, "context")
        lines = [f"- [{f['priority']}] {f['title']}: {f['description']}" for f in features]
        prompt = "\n".join(
            [
                f'Niche: "{state["project"]["seed"]}"',
                f"Problem: {problem['title']}" if problem else "",
                f"Persona: {persona['name']}, {persona['role']}; main need: {persona['focus']}" if persona else "",
                "Backlog (MoSCoW):",
                *lines,
            ]
        )
        progress(0.3, "thinking")
        draft = await self.llm.structured(FlowDraft, FLOW_SYSTEM.format(language=self._language(project_id)), prompt, temperature=0.4)
        progress(0.8, "layout")
        flow = from_draft(draft, features)
        self.db.save_flow(project_id, flow.model_dump(), suggestions=[])
        self.db.update_project(project_id, phase="deliver", stage="flow")
        return self.state(project_id)

    async def optimize(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Ask the local model for fixes to the audit findings, falling back to rule-based ones."""
        flow = self.flow(project_id)
        if not flow.screens:
            raise ValueError("the flow is empty")
        report = audit(flow)
        progress(0.2, "audit")
        described = []
        for screen in flow.screens:
            described.append(f"Screen \"{screen.name}\" ({screen.kind}):")
            for e in screen.elements:
                target = next((s.name for s in flow.screens if s.id == e.target), "")
                described.append(
                    f"  - \"{e.label}\" {e.type}, size {e.size}, zone {e.zone}, options {e.options}"
                    + (f" -> \"{target}\"" if target else "")
                )
        findings = [
            f"Steps to goal: {report['steps']['value'] if report['steps']['value'] is not None else 'goal unreachable'}",
            *(f"Dead end: {d['screen']}" for d in report["dead_ends"]),
            *(f"Unreachable: {d['screen']}" for d in report["unreachable"]),
            *(f"Fitts: \"{f['element']}\" on {f['screen']} size {f['size']} zone {f['zone']} ID {f['index']}" for f in report["fitts"]),
            *(f"Hick: {h['screen']} {h['options']} options = {h['seconds']} s" for h in report["hick"] if h["warning"]),
            *(
                f"Touch target below 44 px (WCAG 2.5.5): \"{t['element']}\" on {t['screen']} size {t['size']}"
                for t in report["targets"]["below_aaa"]
                if t["primary"]
            ),
            f"KLM time to goal: {report['klm']['seconds']} s" if report["klm"] else "KLM time to goal: unknown",
        ]
        prompt = "\n".join(["Flow:", *described, "", "Audit findings:", *findings])
        progress(0.4, "thinking")
        try:
            answer = await self.llm.structured(
                SuggestionSet, OPTIMIZE_SYSTEM.format(language=self._language(project_id)), prompt, temperature=0.3
            )
            suggestions = self._resolve(flow, answer)
        except OllamaError as exc:
            warn(f"llm: {exc}")
            suggestions = []
        if len(suggestions) < 3:
            taken = {(s["op"], s["screen_id"], s["element_id"]) for s in suggestions}
            for extra in fallback_suggestions(report, flow):
                if (extra["op"], extra["screen_id"], extra["element_id"]) not in taken and len(suggestions) < 4:
                    suggestions.append(extra)
        progress(0.9, "saving")
        self.db.save_flow(project_id, flow.model_dump(), suggestions=suggestions)
        return self.state(project_id)

    def _resolve(self, flow: Flow, answer: SuggestionSet) -> list[dict[str, Any]]:
        screens = {_key(s.name): s for s in flow.screens}
        resolved = []
        for item in answer.suggestions:
            screen = screens.get(_key(item.screen))
            if screen is None:
                continue
            element = next((e for e in screen.elements if _key(e.label) == _key(item.element)), None)
            value = item.value.strip()
            if item.op in ("resize", "move_zone", "remove_element") and element is None:
                continue
            if item.op == "resize" and value.upper() not in TARGET_WIDTH:
                continue
            if item.op == "move_zone" and value.lower() not in THUMB_DISTANCE:
                continue
            if item.op == "resize" and element.size == value.upper():
                continue
            if item.op == "move_zone" and element.zone == value.lower():
                continue
            if any(r["op"] == item.op and r["element_id"] == (element.id if element else None) and r["screen_id"] == screen.id for r in resolved):
                continue
            if item.op == "add_transition":
                target = screens.get(_key(value))
                if target is None or target.id == screen.id:
                    continue
                value = target.id
            resolved.append(
                {
                    "id": _id("g"),
                    "title": item.title,
                    "reason": item.reason,
                    "op": item.op,
                    "screen_id": screen.id,
                    "element_id": element.id if element else None,
                    "value": value.upper() if item.op == "resize" else value.lower() if item.op == "move_zone" else value,
                    "label": item.element if item.op == "add_transition" else None,
                }
            )
        return resolved

    def accept(self, project_id: int, suggestion_id: str) -> dict[str, Any]:
        """Apply a stored suggestion and drop it from the list."""
        stored = self.db.get_flow(project_id)
        if stored is None:
            raise LookupError("no flow for this project")
        suggestion = next((s for s in stored["suggestions"] if s["id"] == suggestion_id), None)
        if suggestion is None:
            raise LookupError("suggestion not found")
        flow = apply_suggestion(Flow.model_validate(stored["flow"]), suggestion)
        rest = [s for s in stored["suggestions"] if s["id"] != suggestion_id]
        self.db.save_flow(project_id, flow.model_dump(), suggestions=rest)
        return self.state(project_id)

    def dismiss(self, project_id: int, suggestion_id: str) -> dict[str, Any]:
        """Drop a suggestion without applying it."""
        stored = self.db.get_flow(project_id)
        if stored is None:
            raise LookupError("no flow for this project")
        rest = [s for s in stored["suggestions"] if s["id"] != suggestion_id]
        self.db.save_flow(project_id, stored["flow"], suggestions=rest)
        return self.state(project_id)

    def handoff(self, project_id: int) -> dict[str, Any]:
        """Write the Figma prompt and CLAUDE.md for the project and return their contents."""
        state = self.state(project_id)
        figma, claude = handoff_documents(state)
        root = self.export_root or _documents_dir()
        directory = root / slug(state["project"]["name"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "figma-prompt.md").write_text(figma, encoding="utf-8")
        (directory / "CLAUDE.md").write_text(claude, encoding="utf-8")
        self.db.update_project(project_id, phase="deliver", stage="done")
        return {"figma_prompt": figma, "claude_md": claude, "directory": str(directory)}


def handoff_documents(state: dict[str, Any]) -> tuple[str, str]:
    """Render the Figma design prompt and the CLAUDE.md implementation brief."""
    project, persona, problem = state["project"], state["persona"], state["problem"]
    flow = Flow.model_validate(state["flow"])
    report = state["audit"]
    features = state["features"]
    names = {s.id: s.name for s in flow.screens}
    feature_titles = {f["id"]: f["title"] for f in features}
    order = {"must": 0, "should": 1, "could": 2}
    backlog = [
        f"- **{f['priority'].capitalize()}** — {f['title']}: {f['description']} (popyt {f['demand']}/100, {f['support']}/{f['pool']} dowodów)"
        for f in sorted(features, key=lambda f: (order.get(f["priority"], 3), f["position"]))
    ]
    screen_lines = []
    for screen in flow.screens:
        kind = {"start": " · ekran startowy", "goal": " · cel"}.get(screen.kind, "")
        screen_lines.append(f"### {screen.name}{kind}")
        linked = [feature_titles[i] for i in screen.feature_ids if i in feature_titles]
        if linked:
            screen_lines.append(f"Funkcje: {', '.join(linked)}")
        for e in screen.elements:
            target = f" → {names[e.target]}" if e.target in names else ""
            screen_lines.append(
                f"- {e.label} ({e.type}, rozmiar {e.size} / {SIZE_NAMES[e.size]}, strefa {ZONE_NAMES[e.zone]}){target}"
            )
        screen_lines.append("")
    steps = report["steps"]
    audit_lines = [
        f"- Kroki do celu: {steps['value'] if steps['value'] is not None else 'cel nieosiągalny'}"
        + (f" ({' → '.join(steps['path'])})" if steps["path"] else ""),
        f"- Szacowany czas do celu (KLM): {report['klm']['seconds']} s" if report["klm"] else "- Szacowany czas do celu (KLM): —",
        f"- Cele dotykowe ≥ 44 px (WCAG 2.5.5 AAA): {report['targets']['aaa']}/{report['targets']['total']}",
        *(f"- Hick: {h['screen']} — {h['options']} opcji = {h['seconds']} s" for h in report["hick"][:3]),
        *(f"- Fitts: {f['element']} na ekranie {f['screen']} — ID {f['index']}" for f in report["fitts"]),
        *(f"- Ślepa uliczka: {d['screen']}" for d in report["dead_ends"]),
    ]
    who = (
        f"{persona['name']}, {persona['age']} lat, {persona['role']}. Cytat: „{persona['quote']}”. Główna potrzeba: {persona['focus']}."
        if persona
        else "Persona nie została wybrana."
    )
    figma = "\n".join(
        [
            f"# Figma prompt — {project['name']}",
            "",
            "Zaprojektuj mobilny prototyp (390×844) w Figmie, z auto-layoutem i komponentami.",
            "",
            "## Kontekst",
            f"- Problem: {problem['title'] if problem else '—'}",
            f"- Persona: {who}",
            "",
            "## Ekrany i przejścia",
            *screen_lines,
            "## Zasady ergonomii",
            "- Główne akcje jako duże przyciski (min. 48 px wysokości) w dolnej strefie kciuka.",
            "- Maksymalnie 7 wyborów widocznych naraz; resztę schowaj w „Więcej”.",
            "- Każdy ekran poza celem ma wyraźne przejście dalej.",
            "",
            "## Styl",
            "Jasne, pastelowe tło (#F3EEFF → #FFF0FB), akcent #F783E9, nagłówki Crimson Text, tekst Montserrat,",
            "zaokrąglone karty z miękkim cieniem.",
            "",
        ]
    )
    claude = "\n".join(
        [
            f"# {project['name']} — brief implementacyjny",
            "",
            "Dokument wygenerowany przez PrismFlow (Double Diamond: Discover → Define → Develop → Deliver).",
            "",
            "## Problem i persona",
            f"- Problem: {problem['title'] + ' — ' + problem['description'] if problem else '—'}",
            f"- Persona: {who}",
            "",
            "## Zakres (MoSCoW)",
            *backlog,
            "",
            "## User flow",
            *screen_lines,
            "## Audyt UX",
            *audit_lines,
            "",
            "## Wskazówki dla implementacji",
            "- Zacznij od ścieżki krytycznej start → cel; funkcje Must muszą działać end-to-end.",
            "- Komponenty: przycisk główny (L, dół ekranu), przycisk drugorzędny (M), link (S).",
            "- Dostępność: kontrast WCAG AA, cele dotykowe ≥ 44×44 px, etykiety dla czytników ekranu.",
            "- Popyt oznacza odsetek dowodów (podpowiedzi Google, dyskusje ze Stack Exchange i Lemmy) wspierających funkcję; to hipotezy do zweryfikowania w testach z użytkownikami.",
            "",
        ]
    )
    return figma, claude
