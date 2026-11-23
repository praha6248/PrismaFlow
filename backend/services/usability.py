"""Usability tests on the clickable prototype: tasks, recorded sessions and observed issues."""

from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from statistics import mean
from typing import Any

import networkx as nx

from ..database import Database
from ..models import Flow, TaskSet
from .deliver import graph, klm_time
from .discover import LANGUAGE_NAMES, StructuredLLM
from .jobs import ProgressFn, WarnFn

SUCCESS_TARGET = 0.8
SLOW_RATIO = 2.0

TASK_SYSTEM = """You write usability test tasks (scenarios) for a mobile prototype.
Rules:
- Write in {language}, addressing the participant directly in the second person ("you"; in Polish the "ty" form,
  for example "Masz wolny wieczór i chcesz..."). Never write about the persona in the third person.
- One task per goal screen given; goal is that screen's id.
- Describe a realistic situation and what the participant wants to achieve, based on the persona's context.
- Never name screens, buttons or other interface elements and never give hints about the path."""


SECOND_PERSON = {
    "pl": re.compile(
        r"\b(ty|ci|cię|ciebie|tobie|twój|twoja|twoje|twojego|twojej|twoim|twoją|twoich|jesteś|wyobraź)\b|\b\w+(?:esz|asz|isz|ysz|łeś|łaś)\b",
        re.IGNORECASE,
    ),
    "en": re.compile(r"\b(you|your|yours|yourself)\b", re.IGNORECASE),
}


def addresses_participant(text: str, language: str, persona_name: str = "") -> bool:
    """Tell whether a task speaks to the participant rather than about the persona."""
    if persona_name and re.search(rf"\b{re.escape(persona_name)}\b", text, re.IGNORECASE):
        return False
    pattern = SECOND_PERSON.get(language)
    return bool(pattern.search(text)) if pattern else True


def empty_tests() -> dict[str, Any]:
    """Return a test plan with no tasks or sessions."""
    return {"tasks": [], "sessions": []}


def start_screen(flow: Flow) -> str | None:
    """Id of the screen where every task starts."""
    start = next((s for s in flow.screens if s.kind == "start"), None)
    return (start or (flow.screens[0] if flow.screens else None)).id if flow.screens else None


def optimal_path(flow: Flow, goal: str) -> list[str]:
    """Shortest screen path from the start screen to the goal, or an empty list when unreachable."""
    start = start_screen(flow)
    if start is None:
        return []
    try:
        return nx.shortest_path(graph(flow), start, goal)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def deviation(path: list[str], optimal: list[str]) -> str | None:
    """The screen where a participant first left the shortest path."""
    for index in range(len(path) - 1):
        if index + 1 >= len(optimal) or path[index + 1] != optimal[index + 1]:
            return path[index]
    return None


def summarize(flow: Flow, data: dict[str, Any]) -> dict[str, Any]:
    """Per-task success, time against the KLM prediction, detours and the issues they reveal."""
    names = {s.id: s.name for s in flow.screens}
    tasks = []
    issues = []
    for task in data["tasks"]:
        optimal = optimal_path(flow, task["goal"])
        predicted = klm_time(flow, optimal) if optimal else None
        results = [r | {"participant": s["participant"]} for s in data["sessions"] for r in s["results"] if r["task"] == task["id"]]
        done = [r for r in results if r["success"]]
        dead = Counter(
            (miss["screen"], miss["element"])
            for r in results
            for miss in {(m["screen"], m["element"]): m for m in r.get("misclicks", [])}.values()
        )
        detours = Counter(
            point
            for r in results
            if (point := deviation(r["path"], optimal)) is not None and (not r["success"] or len(r["path"]) > len(optimal))
        )
        summary = {
            **task,
            "goal_name": names.get(task["goal"], task["goal"]),
            "optimal": optimal,
            "attempts": len(results),
            "successes": len(done),
            "seconds": round(mean(r["seconds"] for r in done), 1) if done else None,
            "predicted": predicted["seconds"] if predicted else None,
            "extra_steps": round(mean(max(0, len(r["path"]) - len(optimal)) for r in done), 1) if done and optimal else 0,
            "detours": [{"screen": names.get(k, k), "count": v} for k, v in detours.most_common(3)],
            "misclicks": round(mean(len(r.get("misclicks", [])) for r in results), 1) if results else 0,
            "quotes": [{"participant": r["participant"], "quote": r["quote"], "success": r["success"]} for r in results if r["quote"]][:6],
        }
        tasks.append(summary)
        if not results:
            continue
        rate = len(done) / len(results)
        if rate < SUCCESS_TARGET:
            issues.append({"kind": "success", "task": summary["goal_name"], "successes": len(done), "attempts": len(results)})
        if summary["seconds"] and summary["predicted"] and summary["seconds"] > SLOW_RATIO * summary["predicted"]:
            issues.append({"kind": "slow", "task": summary["goal_name"], "ratio": round(summary["seconds"] / summary["predicted"], 1)})
        for item in summary["detours"]:
            issues.append({"kind": "detour", "task": summary["goal_name"], "screen": item["screen"], "count": item["count"]})
        for (screen, element), count in dead.most_common(2):
            issues.append({"kind": "misclick", "task": summary["goal_name"], "screen": names.get(screen, screen), "element": element, "count": count})
    return {
        "tasks": tasks,
        "sessions": data["sessions"],
        "issues": issues,
        "participants": len(data["sessions"]),
        "start": start_screen(flow),
    }


def fallback_task(goal: str, language: str) -> str:
    """A neutral task used when the model could not write one in the second person."""
    if language == "pl":
        return f"Masz chwilę i chcesz skorzystać z aplikacji. Twoim celem jest dojść do: {goal}. Zrób to tak, jak zrobiłbyś to sam."
    return f"You have a moment and want to use the app. Your goal is to reach: {goal}. Do it the way you normally would."


class UsabilityService:
    """Plans usability tasks for the flow and stores the observed sessions."""

    def __init__(self, db: Database, llm: StructuredLLM) -> None:
        self.db = db
        self.llm = llm

    def _flow(self, project_id: int) -> Flow:
        if self.db.get_project(project_id) is None:
            raise LookupError(f"project {project_id} not found")
        stored = self.db.get_flow(project_id)
        return Flow.model_validate(stored["flow"]) if stored else Flow()

    def _data(self, project_id: int, flow: Flow) -> dict[str, Any]:
        data = self.db.get_document(project_id, "tests") or empty_tests()
        ids = {s.id for s in flow.screens}
        data["tasks"] = [t for t in data["tasks"] if t["goal"] in ids]
        return data

    def state(self, project_id: int) -> dict[str, Any]:
        """Return tasks, sessions and the observed issues."""
        flow = self._flow(project_id)
        return summarize(flow, self._data(project_id, flow))

    async def plan(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Write one task per goal screen; keeps sessions for goals that still exist."""
        flow = self._flow(project_id)
        goals = [s for s in flow.screens if s.kind == "goal"] or flow.screens[-1:]
        if not goals:
            raise ValueError("generate the user flow first")
        project = self.db.get_project(project_id)
        persona = self.db.chosen_persona(project_id)
        problem = next((p for p in self.db.list_problems(project_id) if p["chosen"]), None)
        scenarios: dict[str, str] = {}
        progress(0.2, "tasks")
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                f"Problem: {problem['title'] if problem else '-'}",
                f"Persona: {persona['name']}, {persona['age']}, {persona['role']}; needs: {persona['focus']}" if persona else "Persona: -",
                "Goal screens (id: name, features):",
                *[f"- {s.id}: {s.name}" for s in goals],
            ]
        )
        system = TASK_SYSTEM.format(language=LANGUAGE_NAMES.get(project["language"], "English"))
        name = persona["name"].split()[0] if persona else ""
        request = prompt
        for attempt in range(2):
            try:
                answer: TaskSet = await self.llm.structured(TaskSet, system, request, temperature=0.4 - 0.2 * attempt)
            except (ValueError, TypeError, AttributeError) as exc:
                warn(f"tests: task scenarios fell back to templates ({type(exc).__name__})")
                break
            drafts = {t.goal: " ".join(t.scenario.split()) for t in answer.tasks if t.scenario.strip()}
            good = {goal: text for goal, text in drafts.items() if addresses_participant(text, project["language"], name)}
            scenarios.update(good)
            bad = [text for goal, text in drafts.items() if goal not in good]
            if not bad or len(scenarios) >= len(goals):
                break
            request = (
                prompt
                + "\n\nThese tasks talk about the persona instead of to the participant: "
                + " | ".join(bad)
                + f'\nRewrite them in the second person, as if you were speaking to the participant, without the name "{name}".'
            )
        old = self._data(project_id, flow)
        kept = {t["goal"]: t for t in old["tasks"]}
        tasks = []
        for screen in goals:
            previous = kept.get(screen.id)
            text = scenarios.get(screen.id) or (previous or {}).get("scenario") or fallback_task(screen.name, project["language"])
            tasks.append({"id": (previous or {}).get("id") or uuid.uuid4().hex[:8], "goal": screen.id, "scenario": text})
        valid = {t["id"] for t in tasks}
        sessions = [
            s | {"results": [r for r in s["results"] if r["task"] in valid]} for s in old["sessions"]
        ]
        self.db.save_document(project_id, "tests", {"tasks": tasks, "sessions": [s for s in sessions if s["results"]]})
        return self.state(project_id)

    def update_task(self, project_id: int, task_id: str, scenario: str) -> dict[str, Any]:
        """Rewrite a task's scenario."""
        flow = self._flow(project_id)
        data = self._data(project_id, flow)
        for task in data["tasks"]:
            if task["id"] == task_id:
                task["scenario"] = " ".join(scenario.split())
        self.db.save_document(project_id, "tests", data)
        return self.state(project_id)

    def add_session(self, project_id: int, participant: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Store one participant's results."""
        flow = self._flow(project_id)
        data = self._data(project_id, flow)
        tasks = {t["id"] for t in data["tasks"]}
        ids = {s.id for s in flow.screens}
        kept = [
            r
            | {
                "path": [p for p in r["path"] if p in ids],
                "misclicks": [m for m in r.get("misclicks", []) if m["screen"] in ids],
                "quote": r["quote"].strip(),
            }
            for r in results
            if r["task"] in tasks
        ]
        if not kept:
            raise ValueError("the session has no results for the current tasks")
        data["sessions"].append({"id": uuid.uuid4().hex[:8], "participant": participant.strip(), "results": kept, "created_at": time.time()})
        self.db.save_document(project_id, "tests", data)
        return self.state(project_id)

    def remove_session(self, project_id: int, session_id: str) -> dict[str, Any]:
        """Delete a recorded session."""
        flow = self._flow(project_id)
        data = self._data(project_id, flow)
        data["sessions"] = [s for s in data["sessions"] if s["id"] != session_id]
        self.db.save_document(project_id, "tests", data)
        return self.state(project_id)
