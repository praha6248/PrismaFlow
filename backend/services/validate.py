"""Validate step: falsifiable hypotheses, a Mom Test interview script and verdicts from real interviews.

The model drafts the plan and reads interview notes, but a verdict counts only when its quote is
found verbatim in the notes, and a hypothesis is confirmed only by repeated, unopposed support.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from ..database import Database
from ..models import InterviewAnalysis, ValidationPlanDraft
from .discover import LANGUAGE_NAMES, StructuredLLM
from .jobs import ProgressFn, WarnFn

TARGET_INTERVIEWS = 5
CONFIRM_AT = 3
REJECT_AT = 2

PLAN_SYSTEM = """You are a customer-discovery coach who follows The Mom Test (Rob Fitzpatrick).
From a problem statement, a proto-persona and evidence you write a validation plan.
Rules:
- Write in {language}.
- 3-5 hypotheses covering: the problem exists, it happens often enough to matter, what people do about it today
  (workaround) and whether they already spend money or time on it. Each must be falsifiable.
- Hypotheses describe the segment the persona represents (for example "Computer science students..."), never the
  persona by name; at most 15 words each.
- signal names a past fact the interviewee reports, at most 15 words: a recent occurrence, how often, what they tried,
  what they paid. Willingness is shown by money or time already spent, never by what they say they would do.
- Screener questions check facts about the candidate (role, recent situation), not opinions.
- Interview questions ask about specific past events, frequency, costs and current workarounds.
  Never ask "would you", "do you like", "would you pay" or describe the product idea."""

ANALYSIS_SYSTEM = """You analyse notes from one customer interview against numbered hypotheses.
Rules:
- For every hypothesis give a verdict: supports, contradicts or no_data.
- supports or contradicts only when the notes describe the interviewee's own past behaviour or facts;
  compliments, opinions and promises about the future are no_data.
- quote copies the exact words from the notes (5-30 words) that justify the verdict; never paraphrase.
- Write the summary in {language}."""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[„”\"'«»]", "", text)).strip().casefold()


def quote_in_notes(quote: str, notes: str) -> bool:
    """Tell whether a quote really appears in the notes, ignoring quotes marks, case and spacing."""
    q = _norm(quote)
    return len(q) >= 8 and q in _norm(notes)


def hypothesis_status(supports: int, contradicts: int) -> str:
    """Classify a hypothesis from its verdict counts."""
    if contradicts >= REJECT_AT and contradicts > supports:
        return "rejected"
    if supports >= CONFIRM_AT and supports >= 2 * max(1, contradicts):
        return "confirmed"
    return "open"


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Recompute per-hypothesis counts and statuses from the interviews."""
    for index, hypothesis in enumerate(data["hypotheses"]):
        verdicts = [v for i in data["interviews"] for v in i["verdicts"] if v["hypothesis"] == index]
        hypothesis["supports"] = sum(1 for v in verdicts if v["verdict"] == "supports")
        hypothesis["contradicts"] = sum(1 for v in verdicts if v["verdict"] == "contradicts")
        hypothesis["status"] = hypothesis_status(hypothesis["supports"], hypothesis["contradicts"])
        hypothesis["quotes"] = [
            {"person": i["person"], "verdict": v["verdict"], "quote": v["quote"]}
            for i in data["interviews"]
            for v in i["verdicts"]
            if v["hypothesis"] == index and v["verdict"] != "no_data"
        ][:6]
    data["target"] = TARGET_INTERVIEWS
    data["progress"] = {
        "interviews": len(data["interviews"]),
        "confirmed": sum(1 for h in data["hypotheses"] if h["status"] == "confirmed"),
        "rejected": sum(1 for h in data["hypotheses"] if h["status"] == "rejected"),
    }
    return data


class ValidateService:
    """Builds the validation plan and turns interview notes into hypothesis verdicts."""

    def __init__(self, db: Database, llm: StructuredLLM) -> None:
        self.db = db
        self.llm = llm

    def _context(self, project_id: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        project = self.db.get_project(project_id)
        if project is None:
            raise LookupError(f"project {project_id} not found")
        problem = next((p for p in self.db.list_problems(project_id) if p["chosen"]), None)
        persona = self.db.chosen_persona(project_id)
        if problem is None or persona is None:
            raise ValueError("choose a problem and a persona in Define first")
        return project, problem, persona

    def state(self, project_id: int) -> dict[str, Any]:
        """Return the validation document, or an empty one before the plan exists."""
        project, problem, persona = self._context(project_id)
        data = self.db.get_validation(project_id) or {"hypotheses": [], "screener": [], "questions": [], "interviews": []}
        return {"project": project, "problem": problem, "persona": persona, **summarize(data)}

    async def plan(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Draft hypotheses and the interview script; keeps interviews already logged."""
        project, problem, persona = self._context(project_id)
        evidence = self.db.evidence_by_ids([*problem["evidence_ids"], *persona.get("evidence_ids", [])])
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                f"Problem: {problem['title']} — {problem['description']}",
                f"Persona: {persona['name']}, {persona['age']}, {persona['role']}. Quote: {persona['quote']}",
                f"Main sub-problem: {persona['focus']}",
                "Evidence:",
                *([f"- ({e['source']}) {e['title']}" for e in evidence] or ["(none)"]),
            ]
        )
        progress(0.2, "plan")
        draft: ValidationPlanDraft = await self.llm.structured(
            ValidationPlanDraft, PLAN_SYSTEM.format(language=LANGUAGE_NAMES.get(project["language"], "English")), prompt, temperature=0.4
        )
        old = self.db.get_validation(project_id) or {}
        data = {
            "hypotheses": [{"kind": h.kind, "text": h.text, "signal": h.signal} for h in draft.hypotheses[:5]],
            "screener": draft.screener[:3],
            "questions": draft.questions[:8],
            "interviews": [],
        }
        if old.get("interviews"):
            warn("validate: the plan changed, so earlier interviews were cleared; log them again against the new hypotheses")
        self.db.save_validation(project_id, data)
        self.db.update_project(project_id, phase="define", stage="validate")
        return self.state(project_id)

    async def add_interview(self, project_id: int, person: str, notes: str) -> dict[str, Any]:
        """Analyse one interview's notes and store only verdicts backed by verbatim quotes."""
        project, _, _ = self._context(project_id)
        data = self.db.get_validation(project_id)
        if not data or not data["hypotheses"]:
            raise ValueError("generate the validation plan first")
        numbered = [f"{i + 1}. {h['text']} (confirmed when: {h['signal']})" for i, h in enumerate(data["hypotheses"])]
        prompt = "Hypotheses:\n" + "\n".join(numbered) + "\n\nInterview notes:\n" + notes
        analysis: InterviewAnalysis = await self.llm.structured(
            InterviewAnalysis, ANALYSIS_SYSTEM.format(language=LANGUAGE_NAMES.get(project["language"], "English")), prompt, temperature=0.1
        )
        verdicts = []
        for index in range(len(data["hypotheses"])):
            found = next((v for v in analysis.verdicts if v.hypothesis == index + 1), None)
            if found and found.verdict != "no_data" and quote_in_notes(found.quote, notes):
                verdicts.append({"hypothesis": index, "verdict": found.verdict, "quote": found.quote.strip()})
            else:
                verdicts.append({"hypothesis": index, "verdict": "no_data", "quote": ""})
        data["interviews"].append(
            {"id": uuid.uuid4().hex[:10], "person": person.strip(), "notes": notes, "summary": analysis.summary, "verdicts": verdicts, "created_at": time.time()}
        )
        self.db.save_validation(project_id, data)
        return self.state(project_id)

    def remove_interview(self, project_id: int, interview_id: str) -> dict[str, Any]:
        """Delete one logged interview."""
        data = self.db.get_validation(project_id)
        if not data:
            raise LookupError("no validation plan for this project")
        data["interviews"] = [i for i in data["interviews"] if i["id"] != interview_id]
        self.db.save_validation(project_id, data)
        return self.state(project_id)


def validated_insights(db: Database, project_id: int) -> list[str]:
    """Lines describing confirmed and rejected hypotheses, for later phases and the handoff."""
    data = db.get_validation(project_id)
    if not data:
        return []
    summarize(data)
    lines = []
    for h in data["hypotheses"]:
        if h["status"] == "confirmed":
            lines.append(f"CONFIRMED ({h['supports']} interviews): {h['text']}")
        elif h["status"] == "rejected":
            lines.append(f"REJECTED ({h['contradicts']} interviews): {h['text']}")
    return lines
