"""Shared helpers: synthetic flows, the app's exact prompts and gold answers from the deterministic audit."""

from __future__ import annotations

import asyncio
import copy
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from backend.models import Flow, FlowDraft, FlowElement, FlowScreen, SuggestionSet
from backend.services.deliver import (
    DeliverService,
    apply_suggestion,
    audit,
    from_draft,
)

from niches import EXTRAS, NEXT_LABEL

LANG_CODE = {"pl": "pl", "en": "en"}
PRIMARY_LOOKS = [("L", "bottom")] * 5 + [("M", "center"), ("S", "top"), ("M", "top"), ("S", "center"), ("L", "top"), ("M", "bottom"), ("S", "bottom")]
EXTRA_LOOKS = [("S", "bottom"), ("M", "center"), ("S", "top"), ("M", "top"), ("S", "center"), ("L", "center"), ("M", "bottom")]


class Captured(Exception):
    """Raised by the stub model once the prompt has been captured."""

    def __init__(self, system: str, prompt: str) -> None:
        super().__init__("captured")
        self.system = system
        self.prompt = prompt


class CaptureLLM:
    """Stand-in for OllamaClient that records the request instead of calling a model."""

    async def structured(self, schema: Any, system: str, prompt: str, **kwargs: Any) -> Any:
        raise Captured(system, prompt)


class StubDB:
    """Just enough of Database for DeliverService.generate and optimize."""

    def __init__(self, niche: dict[str, Any], flow: Flow | None, features: list[dict[str, Any]]) -> None:
        self.niche = niche
        self.flow = flow
        self.features = features

    def get_project(self, project_id: int) -> dict[str, Any]:
        return {"id": 1, "name": self.niche["seed"], "seed": self.niche["seed"], "language": LANG_CODE[self.niche["lang"]]}

    def get_flow(self, project_id: int) -> dict[str, Any] | None:
        return {"flow": self.flow.model_dump(), "suggestions": []} if self.flow else None

    def list_problems(self, project_id: int) -> list[dict[str, Any]]:
        return [{"title": self.niche["problem"], "description": "", "chosen": True}]

    def chosen_persona(self, project_id: int) -> dict[str, Any]:
        name, role, focus = self.niche["persona"]
        return {"name": name, "role": role, "focus": focus}

    def list_features(self, project_id: int) -> list[dict[str, Any]]:
        return self.features


def _capture(coro_factory: Any) -> tuple[str, str]:
    try:
        asyncio.run(coro_factory())
    except Captured as captured:
        return captured.system, captured.prompt
    raise RuntimeError("the service did not call the model")


def optimize_prompt(niche: dict[str, Any], flow: Flow) -> tuple[str, str]:
    """Return the exact system and user prompt DeliverService.optimize sends for this flow."""
    service = DeliverService(StubDB(niche, flow, []), CaptureLLM())
    return _capture(lambda: service.optimize(1, lambda *a: None, lambda *a: None))


def flow_prompt(niche: dict[str, Any], features: list[dict[str, Any]]) -> tuple[str, str]:
    """Return the exact system and user prompt DeliverService.generate sends."""
    service = DeliverService(StubDB(niche, None, features), CaptureLLM())
    return _capture(lambda: service.generate(1, lambda *a: None, lambda *a: None))


def resolve(flow: Flow, answer: SuggestionSet) -> list[dict[str, Any]]:
    """Resolve a model answer to app suggestions exactly like DeliverService.optimize."""
    return DeliverService._resolve(None, flow, answer)


def apply_all(flow: Flow, suggestions: list[dict[str, Any]]) -> Flow:
    """Apply suggestions one after another to a copy of the flow, skipping ones that fail."""
    result = Flow.model_validate(copy.deepcopy(flow.model_dump()))
    for item in suggestions:
        try:
            result = apply_suggestion(result, item)
        except LookupError:
            continue
    return result


def random_flow(niche: dict[str, Any], rng: random.Random) -> Flow:
    """Build a random flow for the niche with typical UX defects injected."""
    lang = niche["lang"]
    pool = niche["screens"]
    count = rng.randint(3, len(pool))
    middle = sorted(rng.sample(range(1, len(pool) - 1), count - 2))
    chosen = [pool[0]] + [pool[i] for i in middle] + [pool[-1]]
    screens = []
    for index, (name, _, _, action) in enumerate(chosen):
        kind = "start" if index == 0 else "goal" if index == len(chosen) - 1 else "step"
        screens.append(FlowScreen(id=f"s{index + 1}", name=name, kind=kind))
    counter = 0

    def element(label: str, kind: str, size: str, zone: str, options: int = 1, target: str | None = None) -> FlowElement:
        nonlocal counter
        counter += 1
        return FlowElement(id=f"e{counter}", label=label, type=kind, size=size, zone=zone, options=options, target=target)

    for index, screen in enumerate(screens):
        action = chosen[index][3]
        size, zone = rng.choice(PRIMARY_LOOKS)
        target = screens[index + 1].id if index + 1 < len(screens) else None
        screen.elements.append(element(action, "button", size, zone, 1, target))
        used = {action.casefold()}
        for label, kind, options in rng.sample(EXTRAS[lang], rng.randint(0, 3)):
            if label.casefold() in used:
                continue
            used.add(label.casefold())
            size, zone = rng.choice(EXTRA_LOOKS)
            if kind == "list" and rng.random() < 0.5:
                options = rng.randint(3, 6)
            screen.elements.append(element(label, kind, size, zone, options))
        if index + 2 < len(screens) and rng.random() < 0.15:
            size, zone = rng.choice(EXTRA_LOOKS)
            screen.elements.append(element(rng.choice(["Pomiń", "Na skróty"] if lang == "pl" else ["Skip", "Shortcut"]), "link", size, zone, 1, screens[index + 2].id))
        rng.shuffle(screen.elements)
    middles = [s for s in screens if s.kind == "step"]
    if middles and rng.random() < 0.4:
        victim = rng.choice(middles)
        victim.elements = [e for e in victim.elements if not e.target]
        if not victim.elements:
            victim.elements.append(element(rng.choice(EXTRAS[lang])[0], "link", "S", "top", 1))
    if rng.random() < 0.15 and len(screens) >= 3:
        orphan = rng.choice(screens[1:-1] or screens[1:])
        for screen in screens:
            screen.elements = [e for e in screen.elements if e.target != orphan.id or screen.id == orphan.id]
    for screen in screens:
        if not screen.elements:
            screen.elements.append(element(NEXT_LABEL[lang][0], "button", "M", "center", 1, None))
    return Flow(screens=screens)


def _title(lang: str, rng: random.Random, kind: str, **kw: Any) -> tuple[str, str]:
    pl = {
        "dead": [
            (f"Dodaj przejście z „{kw.get('screen')}” dalej", "Ślepa uliczka zatrzymuje użytkownika"),
            (f"Połącz „{kw.get('screen')}” z kolejnym ekranem", "Ekran bez wyjścia, brak kontroli użytkownika"),
        ],
        "orphan": [
            (f"Dodaj wejście na „{kw.get('target')}” w ścieżce", "Ekran nieosiągalny ze startu"),
            (f"Podlinkuj „{kw.get('target')}” z poprzedniego ekranu", "Nikt nie dotrze do tego ekranu"),
        ],
        "fitts": [
            (f"Przenieś „{kw.get('element')}” do strefy kciuka", f"Indeks Fittsa {kw.get('index')} powyżej 4,5"),
            (f"Przesuń „{kw.get('element')}” na dół ekranu", f"Trudny cel, ID Fittsa {kw.get('index')}"),
        ],
        "small": [
            (f"Powiększ „{kw.get('element')}” do 56 px", "Cel dotykowy poniżej 44 px, WCAG 2.5.5"),
            (f"Zwiększ przycisk „{kw.get('element')}” do L", "Za mały cel, poniżej WCAG 2.5.5"),
        ],
        "hick": [
            (f"Schowaj nadmiar opcji w „Więcej”", f"{kw.get('options')} opcji wydłuża decyzję (Hick)"),
            (f"Ogranicz liczbę wyborów na ekranie", f"Prawo Hicka: {kw.get('seconds')} s decyzji"),
        ],
    }
    en = {
        "dead": [
            (f"Add a way forward from {kw.get('screen')}", "Dead end stops the user"),
            (f"Link {kw.get('screen')} to {kw.get('target')}", "Screen has no exit"),
        ],
        "orphan": [
            (f"Add an entry to {kw.get('target')}", "Screen unreachable from start"),
            (f"Link {kw.get('target')} from {kw.get('screen')}", "Nobody can reach this screen"),
        ],
        "fitts": [
            (f"Move {kw.get('element')} into the thumb zone", f"Fitts index {kw.get('index')} above 4.5"),
            (f"Move {kw.get('element')} to the bottom", f"Hard target, Fitts ID {kw.get('index')}"),
        ],
        "small": [
            (f"Enlarge {kw.get('element')} to 56 px", "Touch target below 44 px, WCAG 2.5.5"),
            (f"Make {kw.get('element')} larger", "Target under WCAG 2.5.5 minimum"),
        ],
        "hick": [
            ("Hide extra options behind More", f"{kw.get('options')} options slow decisions (Hick)"),
            (f"Cut choices on {kw.get('screen')}", f"Hick's law: {kw.get('seconds')} s to decide"),
        ],
    }
    return rng.choice((pl if lang == "pl" else en)[kind])


def gold_suggestions(niche: dict[str, Any], flow: Flow, rng: random.Random) -> SuggestionSet | None:
    """Greedy best fixes: each candidate is kept only when it lowers the audit issue count."""
    lang = niche["lang"]
    by_id = {s.id: s for s in flow.screens}
    goal = next((s for s in flow.screens if s.kind == "goal"), None)
    order = [s.id for s in flow.screens]
    candidates: list[dict[str, Any]] = []
    report = audit(flow)
    for dead in report["dead_ends"]:
        position = order.index(dead["screen_id"])
        following = next((by_id[i] for i in order[position + 1:]), goal)
        target = following if following and following.id != dead["screen_id"] else goal
        if target is None:
            continue
        label = rng.choice(NEXT_LABEL[lang])
        title, reason = _title(lang, rng, "dead", screen=dead["screen"], target=target.name)
        candidates.append({"op": "add_transition", "screen": dead["screen"], "element": label, "value": target.name, "title": title, "reason": reason})
    unreachable = {u["screen_id"] for u in report["unreachable"]}
    for orphan in report["unreachable"]:
        position = order.index(orphan["screen_id"])
        source = next((by_id[i] for i in reversed(order[:position]) if i not in unreachable and by_id[i].kind != "goal"), None)
        if source is None:
            continue
        label = orphan["screen"] if len(orphan["screen"].split()) <= 3 else rng.choice(NEXT_LABEL[lang])
        title, reason = _title(lang, rng, "orphan", screen=source.name, target=orphan["screen"])
        candidates.append({"op": "add_transition", "screen": source.name, "element": label, "value": orphan["screen"], "title": title, "reason": reason})
    for item in report["fitts"]:
        title, reason = _title(lang, rng, "fitts", element=item["element"], index=str(item["index"]).replace(".", "," if lang == "pl" else "."))
        candidates.append({"op": "move_zone", "screen": item["screen"], "element": item["element"], "value": "bottom", "title": title, "reason": reason})
    for item in [t for t in report["targets"]["below_aaa"] if t["primary"]]:
        title, reason = _title(lang, rng, "small", element=item["element"])
        candidates.append({"op": "resize", "screen": item["screen"], "element": item["element"], "value": "L", "title": title, "reason": reason})
    for item in [h for h in report["hick"] if h["warning"]]:
        screen = by_id[item["screen_id"]]
        biggest = max(screen.elements, key=lambda e: e.options)
        title, reason = _title(lang, rng, "hick", screen=item["screen"], options=item["options"], seconds=str(item["seconds"]).replace(".", "," if lang == "pl" else "."))
        candidates.append({"op": "group_options", "screen": item["screen"], "element": biggest.label, "value": "", "title": title, "reason": reason})

    chosen: list[dict[str, Any]] = []
    touched: set[tuple[str, str]] = set()
    current = flow
    issues = report["issues"]
    for candidate in candidates:
        if len(chosen) == 4:
            break
        key = (candidate["screen"], candidate["element"]) if candidate["op"] != "add_transition" else (candidate["screen"], "+" + candidate["value"])
        if key in touched:
            continue
        answer = SuggestionSet.model_validate({"suggestions": [candidate]})
        resolved = resolve(current, answer)
        if len(resolved) != 1:
            continue
        trial = apply_all(current, resolved)
        after = audit(trial)["issues"]
        if after >= issues:
            continue
        chosen.append(candidate)
        touched.add(key)
        current, issues = trial, after
    if not chosen:
        return None
    return SuggestionSet.model_validate({"suggestions": [{k: c[k] for k in ("title", "reason", "op", "screen", "element", "value")} for c in chosen]})


def niche_features(niche: dict[str, Any], rng: random.Random) -> tuple[list[dict[str, Any]], list[tuple]]:
    """Pick the screens of a draft flow and the MoSCoW backlog shown to the model."""
    pool = niche["screens"]
    count = rng.randint(3, min(5, len(pool)))
    middle = sorted(rng.sample(range(1, len(pool) - 1), count - 2))
    chosen = [pool[0]] + [pool[i] for i in middle] + [pool[-1]]
    features = []
    for position, (name, title, description, _) in enumerate(pool):
        if pool[position] in chosen:
            priority = "must" if position else rng.choice(["must", "should"])
        else:
            priority = rng.choice(["should", "could"])
        features.append({"id": position + 1, "title": title, "description": description, "priority": priority, "position": position})
    order = {"must": 0, "should": 1, "could": 2}
    features.sort(key=lambda f: (order[f["priority"]], f["position"]))
    return features, chosen


def gold_flow(niche: dict[str, Any], chosen: list[tuple], features: list[dict[str, Any]], rng: random.Random) -> FlowDraft:
    """A rule-following draft: primary L buttons in the thumb zone, few small choices, no dead ends."""
    lang = niche["lang"]
    must = {f["title"] for f in features if f["priority"] == "must"}
    screens = []
    extras = [e for e in EXTRAS[lang] if e[1] != "list" or e[2] <= 5]
    for index, (name, title, _, action) in enumerate(chosen):
        kind = "start" if index == 0 else "goal" if index == len(chosen) - 1 else "step"
        target = chosen[index + 1][0] if index + 1 < len(chosen) else ""
        elements = [{"label": action, "type": "button", "size": "L", "zone": "bottom", "options": 1, "target": target}]
        for label, etype, options in rng.sample(extras, rng.randint(1, 3)):
            if label.casefold() == action.casefold():
                continue
            if etype in ("link",):
                size, zone = "S", "bottom"
            else:
                size, zone = "M", "center"
            if etype in ("select", "list"):
                options = min(options, 4)
            elements.append({"label": label, "type": etype, "size": size, "zone": zone, "options": options, "target": ""})
        total = sum(e["options"] for e in elements)
        while total > 7 and len(elements) > 2:
            dropped = elements.pop()
            total -= dropped["options"]
        screens.append({"name": name, "kind": kind, "features": [title] if title in must else [], "elements": elements[:4]})
    return FlowDraft.model_validate({"screens": screens})


def draft_metrics(draft: FlowDraft, features: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a FlowDraft the way the app will use it."""
    flow = from_draft(draft, features)
    report = audit(flow)
    kinds = [s.kind for s in draft.screens]
    must = {f["title"].casefold() for f in features if f["priority"] == "must"}
    placed = {t.casefold() for s in draft.screens for t in s.features}
    names = {s.name.casefold() for s in draft.screens}
    targets = [e.target for s in draft.screens for e in s.elements if e.target]
    return {
        "screens_ok": 3 <= len(draft.screens) <= 5,
        "one_start_goal": kinds.count("start") == 1 and kinds.count("goal") == 1,
        "goal_reachable": report["steps"]["status"] == "ok",
        "targets_valid": all(t.casefold() in names for t in targets),
        "must_coverage": len(must & placed) / len(must) if must else 1.0,
        "issues": report["issues"],
        "dead_ends": len(report["dead_ends"]),
    }
