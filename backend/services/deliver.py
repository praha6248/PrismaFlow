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
from ..models import Flow, FlowDraft, FlowElement, FlowScreen, StyleDraft, SuggestionSet
from ..ollama_client import OllamaError
from .discover import LANGUAGE_NAMES, StructuredLLM
from .jobs import ProgressFn, WarnFn
from .validate import validated_insights

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
- Keep 2-4 elements per screen. options is the number of alternatives inside that one control: 1 for buttons,
  links and inputs; the visible items, chips or filters for a list or select. Model each filter group as its own element.
- Back navigation is provided by the system, do not add "back" elements.
- Assign every Must-have feature to the screen where it lives using its exact title."""

OPTIMIZE_SYSTEM = """You are a UX auditor. Propose concrete, small changes that fix the audit findings of a mobile user flow.
Rules:
- Write title and reason in {language}.
- Use only these operations: resize (value S, M or L), move_zone (value top, center or bottom),
  group_options (show at most 5 choices of a long list, select or filter group named in element and move the rest behind
  a "more" control; without element it groups secondary actions), add_transition (connect a dead-end
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


CHOICE_TYPES = ("list", "select")
ACTION_TYPES = ("button", "link")


def choice_sets(screen: FlowScreen) -> list[dict[str, Any]]:
    """Return the separate decisions a screen asks for, each with its number of alternatives.

    Hick-Hyman applies to one decision among equally likely alternatives, so a screen is not
    one big choice: every list, select or filter group is its own decision with its own options,
    and choosing which button or link to tap is one more decision among those actions.
    """
    sets = []
    for element in screen.elements:
        if element.type in CHOICE_TYPES or element.options > 1:
            if element.options >= 2:
                sets.append({"element_id": element.id, "element": element.label, "options": element.options})
    actions = [e for e in screen.elements if e.type in ACTION_TYPES and e.options == 1]
    if len(actions) >= 2:
        sets.append({"element_id": None, "element": None, "options": len(actions)})
    return sets


def decision_options(screen: FlowScreen, element: FlowElement) -> int:
    """Number of alternatives the user weighs when choosing this element."""
    if element.options >= 2:
        return element.options
    if element.type in ACTION_TYPES:
        return max(1, sum(1 for e in screen.elements if e.type in ACTION_TYPES and e.options == 1))
    return 1


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

    Each step adds mental preparation (M), the Hick decision time of the choice the user makes
    (the list it belongs to, or the screen's set of actions) and the Fitts movement time of the
    element that leads to the next screen.
    """
    if len(path) < 2:
        return None
    by_id = {s.id: s for s in flow.screens}
    total = 0.0
    steps = []
    for current, following in zip(path, path[1:]):
        screen = by_id[current]
        candidates = [e for e in screen.elements if e.target == following]
        element = min(candidates, key=lambda e: movement_time(e.size, e.zone))
        seconds = KLM_MENTAL + hick_time(decision_options(screen, element)) + movement_time(element.size, element.zone)
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
        for choice in choice_sets(screen):
            options = choice["options"]
            hick.append(
                {
                    "screen_id": screen.id,
                    "screen": screen.name,
                    **choice,
                    "seconds": round(hick_time(options), 2),
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
                "reason": f"{item['screen']} · {item['element'] or 'akcje'}: {item['options']} opcji = {item['seconds']} s",
                "op": "group_options",
                "screen_id": item["screen_id"],
                "element_id": item["element_id"],
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
    elif op == "group_options" and element is not None and element.options > 5:
        element.options = 5
        screen.elements.append(FlowElement(id=_id("e"), label="Więcej", type="link", size="M", zone="center", options=1))
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
    return (path or data_dir()) / "PrismaFlow"


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
            "insights": validated_insights(self.db, project_id),
            "tests": self._tests(project_id, flow),
        }

    def _tests(self, project_id: int, flow: Flow) -> dict[str, Any]:
        from .usability import empty_tests, summarize

        data = self.db.get_document(project_id, "tests") or empty_tests()
        ids = {s.id for s in flow.screens}
        data["tasks"] = [t for t in data["tasks"] if t["goal"] in ids]
        return summarize(flow, data)

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
        draft = await self.llm.structured(FlowDraft, FLOW_SYSTEM.format(language=self._language(project_id)), prompt, temperature=0.4, task="deliver")
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
            *(
                f"Hick: {h['screen']} " + (f"\"{h['element']}\"" if h["element"] else "choice between actions") + f" {h['options']} options = {h['seconds']} s"
                for h in report["hick"]
                if h["warning"]
            ),
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
                SuggestionSet, OPTIMIZE_SYSTEM.format(language=self._language(project_id)), prompt, temperature=0.3, task="deliver"
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

    async def style(self, state: dict[str, Any]) -> dict[str, Any]:
        """Ask the local model for the product's own visual style, falling back to a curated one."""
        project, persona, problem = state["project"], state["persona"], state["problem"]
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                f"Problem: {problem['title'] if problem else '-'}",
                f"Persona: {persona['name']}, {persona['age']}, {persona['role']}; needs {persona['focus']}" if persona else "Persona: -",
                "Must-have features: " + ", ".join(f["title"] for f in state["features"] if f["priority"] == "must"),
            ]
        )
        try:
            draft: StyleDraft = await self.llm.structured(
                StyleDraft, STYLE_SYSTEM.format(language=self._language(project["id"])), prompt, temperature=0.6
            )
            style = StyleDraft.model_validate(draft.model_dump()).model_dump()
        except (OllamaError, ValueError, TypeError, AttributeError):
            return fallback_style(project["seed"])
        return style

    async def handoff(self, project_id: int) -> dict[str, Any]:
        """Write the Figma prompt and CLAUDE.md for the project and return their contents."""
        state = self.state(project_id)
        style = finish_style(await self.style(state))
        figma, claude = handoff_documents(state, style)
        directory = self.export_dir(state["project"])
        (directory / "figma-prompt.md").write_text(figma, encoding="utf-8")
        (directory / "CLAUDE.md").write_text(claude, encoding="utf-8")
        report = await self.report(project_id, state, style, directory)
        self.db.update_project(project_id, phase="deliver", stage="done")
        return {"figma_prompt": figma, "claude_md": claude, "report": report["markdown"], "files": report["files"], "directory": str(directory)}

    def export_dir(self, project: dict[str, Any]) -> Path:
        """Folder where the project's exports are written."""
        directory = (self.export_root or _documents_dir()) / slug(project["name"])
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def report_context(self, project_id: int, state: dict[str, Any]) -> dict[str, Any]:
        """Deliver state plus the RICE backlog, board, empathy map and interview validation."""
        from .develop import develop_state
        from .validate import summarize as summarize_validation

        validation = self.db.get_validation(project_id)
        return {
            **state,
            "features": [f for f in develop_state(self.db, project_id)["features"] if f["priority"] != "wont"],
            "board": self.db.get_document(project_id, "board"),
            "empathy": self.db.get_document(project_id, "empathy"),
            "validation": summarize_validation(validation) if validation else None,
        }

    async def report(self, project_id: int, state: dict[str, Any], style: dict[str, Any], directory: Path) -> dict[str, Any]:
        """Write the research report (Markdown, HTML and PDF when Chromium is available) and the prototype SVG."""
        from .report import markdown_html, prototype_svg, report_markdown, write_pdf

        context = self.report_context(project_id, state)
        markdown = report_markdown(context)
        (directory / "raport.md").write_text(markdown, encoding="utf-8")
        html_path = directory / "raport.html"
        html_path.write_text(markdown_html(markdown, state["project"]["name"]), encoding="utf-8")
        (directory / "prototyp-figma.svg").write_text(prototype_svg(Flow.model_validate(state["flow"]), style), encoding="utf-8")
        files = ["figma-prompt.md", "CLAUDE.md", "raport.md", "raport.html", "prototyp-figma.svg"]
        if await write_pdf(html_path, directory / "raport.pdf"):
            files.append("raport.pdf")
        return {"markdown": markdown, "files": files}


STYLE_SYSTEM = """You are a brand and UI designer. Propose the visual style of a new mobile app for the persona and problem given.
Rules:
- Write mood and rationale in {language}.
- Fit the style to the audience and the job: calm and trustworthy for health or money, energetic for sport,
  friendly and clear for education, warm for family and care. Avoid generic purple gradients.
- Use a light background, a surface close to white, one saturated primary colour and a dark text colour.
- Pick a heading and a body font from the allowed list; they may be the same family.
- Colours are #RRGGBB."""

CORNER_PIXELS = {"sharp": 4, "soft": 12, "round": 24}
FALLBACK_STYLES = (
    {"mood": ["spokojny", "rzeczowy", "zaufany"], "background": "#F4F7FB", "surface": "#FFFFFF", "primary": "#1F6FEB", "text": "#16202C", "heading_font": "Manrope", "body_font": "Inter", "corners": "soft"},
    {"mood": ["energiczny", "odważny", "motywujący"], "background": "#FFF7F0", "surface": "#FFFFFF", "primary": "#E4572E", "text": "#231A15", "heading_font": "Space Grotesk", "body_font": "DM Sans", "corners": "round"},
    {"mood": ["ciepły", "przyjazny", "opiekuńczy"], "background": "#FBF8F3", "surface": "#FFFFFF", "primary": "#2E7D5B", "text": "#1E2420", "heading_font": "Fraunces", "body_font": "Nunito", "corners": "round"},
    {"mood": ["jasny", "uporządkowany", "nowoczesny"], "background": "#F6F6F8", "surface": "#FFFFFF", "primary": "#5B4FE0", "text": "#18181F", "heading_font": "Outfit", "body_font": "Work Sans", "corners": "soft"},
    {"mood": ["stonowany", "profesjonalny", "precyzyjny"], "background": "#F5F5F2", "surface": "#FFFFFF", "primary": "#0F766E", "text": "#1B1D1C", "heading_font": "IBM Plex Sans", "body_font": "IBM Plex Sans", "corners": "sharp"},
)


def luminance(color: str) -> float:
    """WCAG relative luminance of a #RRGGBB colour."""
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two colours."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _darken(color: str, factor: float) -> str:
    return "#" + "".join(f"{int(int(color[i : i + 2], 16) * factor):02X}" for i in (1, 3, 5))


def fallback_style(seed: str) -> dict[str, Any]:
    """Pick a curated style deterministically from the niche when the model is unavailable."""
    index = sum(ord(c) for c in seed.casefold()) % len(FALLBACK_STYLES)
    return {**FALLBACK_STYLES[index], "rationale": "Styl dobrany automatycznie; zweryfikuj go z personą."}


def finish_style(style: dict[str, Any]) -> dict[str, Any]:
    """Make a style accessible: text reaches WCAG AA 4.5:1 on background and surface, and the primary
    button label reaches 4.5:1 with white or dark text; the contrast ratios are added to the style."""
    style = dict(style)
    for _ in range(12):
        if min(contrast(style["text"], style["background"]), contrast(style["text"], style["surface"])) >= 4.5:
            break
        style["text"] = _darken(style["text"], 0.8)
    for _ in range(12):
        if max(contrast("#FFFFFF", style["primary"]), contrast(style["text"], style["primary"])) >= 4.5:
            break
        style["primary"] = _darken(style["primary"], 0.88)
    white = contrast("#FFFFFF", style["primary"])
    dark = contrast(style["text"], style["primary"])
    style["on_primary"] = "#FFFFFF" if white >= dark else style["text"]
    style["contrast_text"] = round(contrast(style["text"], style["background"]), 1)
    style["contrast_primary"] = round(max(white, dark), 1)
    return style


def style_lines(style: dict[str, Any]) -> list[str]:
    """Describe a product style as Markdown lines."""
    return [
        f"Nastrój: {', '.join(style['mood'])}. {style['rationale']}",
        f"- Tło {style['background']}, powierzchnie {style['surface']}, tekst {style['text']} (kontrast {style['contrast_text']}:1)",
        f"- Kolor główny {style['primary']}, etykieta na nim {style['on_primary']} (kontrast {style['contrast_primary']}:1)",
        f"- Nagłówki {style['heading_font']}, tekst {style['body_font']}",
        f"- Zaokrąglenia {CORNER_PIXELS[style['corners']]} px",
    ]


def ux_guidance(flow: Flow, report: dict[str, Any], style: dict[str, Any]) -> list[str]:
    """Turn the flow, its audit and the product style into concrete UX/UI rules for the implementer."""
    names = {s.id: s.name for s in flow.screens}
    steps = report["steps"]
    lines = ["## Wytyczne UX/UI", "", "### Nawigacja i ścieżka krytyczna"]
    if steps["path"]:
        lines.append(f"- Ścieżka {' → '.join(steps['path'])} ma działać bez zbędnych kroków; nie dodawaj ekranów pośrednich ani modali na tej drodze.")
    path_ids = [s.id for name in steps["path"] for s in flow.screens if s.name == name]
    start_id = next((s.id for s in flow.screens if s.kind == "start"), None)
    for screen in flow.screens:
        following = path_ids[path_ids.index(screen.id) + 1] if screen.id in path_ids[:-1] else None
        forward = [e for e in screen.elements if e.target and e.target != start_id]
        primary = [e for e in forward if e.target == following] or [e for e in forward if e.size == "L"]
        if primary:
            lines.append(f"- {screen.name}: jedna akcja główna „{primary[0].label}” → {names.get(primary[0].target, '')}, pełnej szerokości w dolnej strefie kciuka.")
    for item in report["dead_ends"]:
        lines.append(f"- {item['screen']}: dodaj wyraźną akcję dalej (lub powrót do startu) — teraz to ślepa uliczka.")
    lines.append("- Systemowy gest i przycisk „wstecz” muszą działać na każdym ekranie; zachowuj stan formularzy przy powrocie.")
    lines += ["", "### Wybory i obciążenie poznawcze"]
    crowded = [h for h in report["hick"] if h["warning"]]
    for item in crowded:
        what = f"„{item['element']}”" if item["element"] else "akcje"
        lines.append(f"- {item['screen']} · {what}: {item['options']} opcji — pokaż do 5 najczęstszych, resztę pod „Więcej” lub z wyszukiwarką.")
    lines += [
        "- Jedna decyzja na raz: grupuj filtry tematycznie, domyślne wartości ustaw na najczęstszy wybór.",
        "- Długie listy sortuj w przewidywalny sposób (alfabetycznie lub wg popularności) i dodaj wyszukiwanie od ok. 10 pozycji.",
        "",
        "### Cele dotykowe i ergonomia",
        "- Każdy element klikalny ma co najmniej 44×44 px (WCAG 2.5.5) i min. 8 px odstępu od sąsiednich.",
    ]
    for item in report["fitts"]:
        lines.append(f"- {item['element']} ({item['screen']}): powiększ i przesuń bliżej dolnej krawędzi — trudno w niego trafić kciukiem.")
    lines += [
        "- Akcje destrukcyjne trzymaj z dala od głównych i potwierdzaj je albo dawaj „Cofnij”.",
        "",
        "### Stany i informacja zwrotna",
        "- Każdy ekran z danymi ma stan ładowania (szkielet), pusty (z podpowiedzią, co zrobić) i błędu (z przyciskiem ponowienia).",
        "- Reaguj na dotyk w < 100 ms (stan pressed); operacje > 1 s pokazują postęp.",
        "- Po zapisaniu lub wysłaniu pokaż krótkie potwierdzenie (toast) zamiast przenosić użytkownika bez komentarza.",
        "",
        "### Formularze",
        "- Etykieta nad polem (nie placeholder zamiast etykiety), właściwy typ klawiatury, autouzupełnianie.",
        "- Walidacja po opuszczeniu pola, komunikat błędu pod polem mówi, jak to naprawić.",
        "",
        "### Typografia, kolor i dostępność",
        f"- Tekst {style['text']} na tle {style['background']} ({style['contrast_text']}:1), etykiety przycisków {style['on_primary']} na {style['primary']} ({style['contrast_primary']}:1); nie schodź poniżej 4,5:1.",
        f"- Tekst podstawowy 16 px, interlinia 1,5; nagłówki {style['heading_font']}, treść {style['body_font']}; skaluj z ustawieniami systemu (Dynamic Type / sp).",
        f"- Siatka odstępów 8 px, zaokrąglenia {CORNER_PIXELS[style['corners']]} px; kolor główny tylko dla akcji, nie dla dekoracji.",
        "- Nie przekazuj informacji samym kolorem; ikony mają etykiety dostępności, kolejność fokusu = kolejność wizualna.",
        "- Szanuj „ogranicz ruch” (prefers-reduced-motion); animacje 150–300 ms.",
        "",
    ]
    return lines


def handoff_documents(state: dict[str, Any], style: dict[str, Any] | None = None) -> tuple[str, str]:
    """Render the Figma design prompt and the CLAUDE.md implementation brief."""
    style = finish_style(style or fallback_style(state["project"]["seed"]))
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
    guidance = ux_guidance(flow, report, style)
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
            "## Styl produktu",
            *style_lines(style),
            "",
        ]
    )
    claude = "\n".join(
        [
            f"# {project['name']} — brief implementacyjny",
            "",
            "Dokument wygenerowany przez PrismaFlow (Double Diamond: Discover → Define → Develop → Deliver).",
            "",
            "## Problem i persona",
            f"- Problem: {problem['title'] + ' — ' + problem['description'] if problem else '—'}",
            f"- Persona: {who}",
            "",
            "## Walidacja (wywiady z użytkownikami)",
            *([f"- {line}" for line in state.get("insights", [])] or ["- Brak potwierdzonych hipotez — zakres opiera się na dowodach z internetu, nie na rozmowach."]),
            "",
            "## Zakres (MoSCoW)",
            *backlog,
            "",
            "## User flow",
            *screen_lines,
            "## Styl produktu",
            *style_lines(style),
            "",
            *guidance,
            "## Uwagi",
            "- Popyt oznacza odsetek dowodów (podpowiedzi Google, dyskusje ze Stack Exchange i Lemmy) wspierających funkcję; to hipotezy do zweryfikowania w testach z użytkownikami.",
            "",
        ]
    )
    return figma, claude
