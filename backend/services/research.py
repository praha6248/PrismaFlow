"""Research artefacts between the phases: affinity board, empathy map, user journey and How Might We.

Every observation keeps a link to the note it came from, so a reader can tell what was heard from
real people and what the model inferred.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from ..database import Database
from ..models import AffinityDraft, EmpathyDraft
from .discover import LANGUAGE_NAMES, StructuredLLM
from .jobs import ProgressFn, WarnFn
from .validate import quote_in_notes, validated_insights

MAX_NOTES = 60
SEED_NOTES = 36
QUADRANTS = ("says", "thinks", "does", "feels")
PHASE_ORDER = {"before": 0, "during": 1, "after": 2}
REAL_SOURCES = ("note", "interview", "test")

AFFINITY_SYSTEM = """You are a UX researcher running an affinity mapping session.
You group research notes (forum threads, interview fragments, usability test observations) into themes.
Rules:
- Write theme names and insights in {language}.
- Create 3-6 themes. A theme groups notes that describe the same need, behaviour or frustration,
  not the same topic word.
- Every note belongs to at most one theme; leave out notes that fit no theme.
- The insight states what the notes reveal about people, in one sentence, without inventing numbers."""

EMPATHY_SYSTEM = """You are a UX researcher building an empathy map and a user journey for one persona.
Rules:
- Write in {language}.
- Every item is short: 4-14 words, one phrase, never two sentences.
- says: things the persona says out loud; thinks: what they think but may not say; does: observable actions;
  feels: emotions and worries.
- Base each item on a numbered note when one fits and give its number in note; use 0 only when the item is
  an inference from the persona profile. Prefer notes from real people (interviews, own notes, tests).
- journey: 5-7 stages in time order covering before (trigger, preparation), during (doing the task) and after
  (result, follow-up). emotion goes from -2 (frustrated) to 2 (delighted); pain names the frustration of a
  stage, empty when there is none.
- hmw: three "How might we..." questions (in {language}, for Polish start with "Jak moglibyśmy"), each built on
  one of the strongest journey frustrations, open enough to allow several solutions and never naming a feature."""


def _id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def split_notes(text: str) -> list[str]:
    """Split pasted text into notes on blank lines, or on lines when there are no blank lines."""
    text = text.replace("\r\n", "\n").strip()
    parts = re.split(r"\n\s*\n", text) if re.search(r"\n\s*\n", text) else text.split("\n")
    notes = [" ".join(re.sub(r"^\s*[-*•]\s*", "", p).split()) for p in parts]
    return [n[:600] for n in notes if len(n) >= 3]


def _place(item: dict[str, Any]) -> str:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    return meta.get("place") or {"community": "Forum", "reddit": "Reddit", "autocomplete": "Google"}.get(item["source"], item["source"])


def empty_board() -> dict[str, Any]:
    """Return a board with no notes."""
    return {"notes": [], "themes": [], "clustered_at": None}


class ResearchService:
    """Keeps the affinity board and the empathy map of a project."""

    def __init__(self, db: Database, llm: StructuredLLM) -> None:
        self.db = db
        self.llm = llm

    def _project(self, project_id: int) -> dict[str, Any]:
        project = self.db.get_project(project_id)
        if project is None:
            raise LookupError(f"project {project_id} not found")
        return project

    def _language(self, project: dict[str, Any]) -> str:
        return LANGUAGE_NAMES.get(project["language"], "the niche's language")

    def _evidence_notes(self, project_id: int) -> list[dict[str, Any]]:
        nodes = [n for n in self.db.list_nodes(project_id) if not n["is_root"]]
        starred = [n for n in nodes if n["starred"]]
        focus = starred or sorted(nodes, key=lambda n: (n["kind"] == "pain_point", n["score"]), reverse=True)[:8]
        items = [e for e in self.db.evidence_for_nodes([n["id"] for n in focus], per_node=6) if e["source"] != "autocomplete"]
        ids = list(dict.fromkeys(e["id"] for e in items))[:SEED_NOTES]
        notes = []
        seen: set[str] = set()
        for item in self.db.evidence_by_ids(ids):
            body = " ".join((item.get("body") or "").split())
            text = item["title"] + (f" — {body[:220]}" if body else "")
            key = item["title"].casefold()
            if key in seen:
                continue
            seen.add(key)
            notes.append(
                {
                    "id": _id("n"),
                    "text": text,
                    "source": "evidence",
                    "label": _place(item),
                    "url": item.get("url") or item["meta"].get("url"),
                    "evidence_id": item["id"],
                    "theme": None,
                }
            )
        return notes

    def _interview_notes(self, project_id: int, known: set[str]) -> list[dict[str, Any]]:
        data = self.db.get_validation(project_id) or {}
        notes = []
        for interview in data.get("interviews", []):
            for text in split_notes(interview["notes"]):
                key = f"{interview['id']}:{text.casefold()}"
                if key in known:
                    continue
                known.add(key)
                notes.append(
                    {"id": _id("n"), "text": text, "source": "interview", "label": interview["person"], "interview": interview["id"], "theme": None}
                )
        return notes

    def board(self, project_id: int) -> dict[str, Any]:
        """Return the board, seeding it from Discover evidence and logged interviews."""
        project = self._project(project_id)
        data = self.db.get_document(project_id, "board") or empty_board()
        changed = False
        if not data["notes"]:
            data["notes"] = self._evidence_notes(project_id)
            changed = bool(data["notes"])
        known = {f"{n['interview']}:{n['text'].casefold()}" for n in data["notes"] if n.get("interview")}
        fresh = self._interview_notes(project_id, known)
        if fresh:
            data["notes"] = [*fresh, *data["notes"]][:MAX_NOTES]
            changed = True
        if changed:
            self.db.save_document(project_id, "board", data)
        return {"project": project, **data}

    def add_notes(self, project_id: int, text: str, source: str, label: str, theme: str | None = None) -> dict[str, Any]:
        """Add one or more pasted notes to the board."""
        state = self.board(project_id)
        data = {k: state[k] for k in ("notes", "themes", "clustered_at")}
        themes = {t["id"] for t in data["themes"]}
        new = [
            {"id": _id("n"), "text": note, "source": source, "label": label.strip(), "theme": theme if theme in themes else None}
            for note in split_notes(text)
        ]
        if not new:
            raise ValueError("the note is empty")
        data["notes"] = [*new, *data["notes"]][: MAX_NOTES + len(new)]
        self.db.save_document(project_id, "board", data)
        return self.board(project_id)

    def _mutate(self, project_id: int) -> dict[str, Any]:
        self._project(project_id)
        return self.db.get_document(project_id, "board") or empty_board()

    def move_note(self, project_id: int, note_id: str, theme: str | None) -> dict[str, Any]:
        """Put a note into a theme, or back among the ungrouped notes."""
        data = self._mutate(project_id)
        themes = {t["id"] for t in data["themes"]}
        for note in data["notes"]:
            if note["id"] == note_id:
                note["theme"] = theme if theme in themes else None
        self.db.save_document(project_id, "board", data)
        return self.board(project_id)

    def remove_note(self, project_id: int, note_id: str) -> dict[str, Any]:
        """Delete a note."""
        data = self._mutate(project_id)
        data["notes"] = [n for n in data["notes"] if n["id"] != note_id]
        self.db.save_document(project_id, "board", data)
        return self.board(project_id)

    def add_theme(self, project_id: int, name: str) -> dict[str, Any]:
        """Create an empty theme."""
        data = self._mutate(project_id)
        data["themes"].append({"id": _id("t"), "name": name.strip()[:60], "insight": ""})
        self.db.save_document(project_id, "board", data)
        return self.board(project_id)

    def update_theme(self, project_id: int, theme_id: str, name: str | None, insight: str | None) -> dict[str, Any]:
        """Rename a theme or edit its insight."""
        data = self._mutate(project_id)
        for theme in data["themes"]:
            if theme["id"] == theme_id:
                if name is not None:
                    theme["name"] = name.strip()
                if insight is not None:
                    theme["insight"] = insight.strip()
        self.db.save_document(project_id, "board", data)
        return self.board(project_id)

    def remove_theme(self, project_id: int, theme_id: str) -> dict[str, Any]:
        """Delete a theme; its notes go back to the ungrouped column."""
        data = self._mutate(project_id)
        data["themes"] = [t for t in data["themes"] if t["id"] != theme_id]
        for note in data["notes"]:
            if note["theme"] == theme_id:
                note["theme"] = None
        self.db.save_document(project_id, "board", data)
        return self.board(project_id)

    async def cluster(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Ask the model to group the notes into themes; replaces the previous themes."""
        state = self.board(project_id)
        project = state["project"]
        notes = state["notes"]
        if len(notes) < 4:
            raise ValueError("add at least four notes before grouping them")
        progress(0.2, "grouping")
        lines = [f"{i + 1}. ({n['source']}) {n['text'][:260]}" for i, n in enumerate(notes)]
        prompt = f'Niche: "{project["seed"]}"\n\nNotes:\n' + "\n".join(lines)
        draft: AffinityDraft = await self.llm.structured(
            AffinityDraft, AFFINITY_SYSTEM.format(language=self._language(project)), prompt, temperature=0.3
        )
        themes = []
        assigned: dict[int, str] = {}
        for item in draft.themes[:6]:
            members = [n - 1 for n in item.notes if 0 < n <= len(notes) and n - 1 not in assigned]
            if not members:
                continue
            theme = {"id": _id("t"), "name": item.name, "insight": item.insight.strip()}
            themes.append(theme)
            for index in members:
                assigned[index] = theme["id"]
        if not themes:
            raise ValueError("the model did not group any notes")
        for index, note in enumerate(notes):
            note["theme"] = assigned.get(index)
        progress(0.9, "saving")
        self.db.save_document(project_id, "board", {"notes": notes, "themes": themes, "clustered_at": time.time()})
        return self.board(project_id)

    def empathy(self, project_id: int) -> dict[str, Any]:
        """Return the empathy map, journey and How Might We questions, empty before generation."""
        project = self._project(project_id)
        problem = next((p for p in self.db.list_problems(project_id) if p["chosen"]), None)
        persona = self.db.chosen_persona(project_id)
        data = self.db.get_document(project_id, "empathy") or {}
        return {"project": project, "problem": problem, "persona": persona, "map": data or None}

    def _research_notes(self, project_id: int) -> list[dict[str, Any]]:
        board = self.db.get_document(project_id, "board") or empty_board()
        notes = [n for n in board["notes"] if n["source"] in REAL_SOURCES]
        notes += [n for n in board["notes"] if n["source"] not in REAL_SOURCES]
        known = {f"{n['interview']}:{n['text'].casefold()}" for n in notes if n.get("interview")}
        notes = self._interview_notes(project_id, known) + notes
        return notes[:40]

    async def generate_empathy(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Build the empathy map, journey and How Might We questions for the chosen persona."""
        state = self.empathy(project_id)
        project, problem, persona = state["project"], state["problem"], state["persona"]
        if problem is None or persona is None:
            raise ValueError("choose a problem and a persona in Define first")
        progress(0.1, "context")
        notes = self._research_notes(project_id)
        board = self.db.get_document(project_id, "board") or empty_board()
        profile = persona.get("profile") or {}
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                f"Problem: {problem['title']} — {problem['description']}",
                f"Persona: {persona['name']}, {persona['age']}, {persona['role']}. Quote: {persona['quote']}",
                f"Main sub-problem: {persona['focus']}",
                *[f"{key}: {value}" for key, value in profile.items() if isinstance(value, str)],
                "",
                "Themes from the affinity board:",
                *([f"- {t['name']}: {t['insight']}" for t in board["themes"]] or ["(none)"]),
                "",
                "Results of customer interviews:",
                *(validated_insights(self.db, project_id) or ["(none yet)"]),
                "",
                "Numbered notes (source, text):",
                *([f"{i + 1}. ({n['source']}) {n['text'][:240]}" for i, n in enumerate(notes)] or ["(none)"]),
            ]
        )
        progress(0.3, "thinking")
        draft: EmpathyDraft = await self.llm.structured(
            EmpathyDraft, EMPATHY_SYSTEM.format(language=self._language(project)), prompt, temperature=0.4
        )

        def source(number: int) -> dict[str, Any] | None:
            if 0 < number <= len(notes):
                note = notes[number - 1]
                return {"text": note["text"], "source": note["source"], "label": note.get("label", ""), "url": note.get("url")}
            return None

        progress(0.85, "saving")
        data: dict[str, Any] = {q: [{"text": i.text.strip(), "from": source(i.note)} for i in getattr(draft, q)[:4]] for q in QUADRANTS}
        stages = sorted(draft.journey[:7], key=lambda s: PHASE_ORDER[s.phase])
        data["journey"] = [
            {
                "phase": s.phase,
                "name": s.name.strip(),
                "action": s.action.strip(),
                "thought": s.thought.strip(),
                "emotion": s.emotion,
                "pain": s.pain.strip(),
                "from": source(s.note),
            }
            for s in stages
        ]
        options = [" ".join(q.split()) for q in draft.hmw[:3] if q.strip()]
        old = self.db.get_document(project_id, "empathy") or {}
        data["hmw"] = options
        data["hmw_chosen"] = old.get("hmw_chosen") if old.get("hmw_chosen") in options else (options[0] if options else "")
        data["generated_at"] = time.time()
        self.db.save_document(project_id, "empathy", data)
        return self.empathy(project_id)

    def choose_hmw(self, project_id: int, text: str) -> dict[str, Any]:
        """Pick or rewrite the How Might We question that frames Develop."""
        self._project(project_id)
        data = self.db.get_document(project_id, "empathy")
        if not data:
            raise ValueError("generate the empathy map first")
        data["hmw_chosen"] = " ".join(text.split())
        if data["hmw_chosen"] not in data["hmw"]:
            data["hmw"] = [*data["hmw"], data["hmw_chosen"]][-4:]
        self.db.save_document(project_id, "empathy", data)
        return self.empathy(project_id)


def board_lines(db: Database, project_id: int) -> list[str]:
    """Describe the board's themes with a few notes each, for problem generation."""
    board = db.get_document(project_id, "board")
    if not board or not board["themes"]:
        return []
    lines = []
    for theme in board["themes"]:
        members = [n for n in board["notes"] if n["theme"] == theme["id"]]
        if not members:
            continue
        lines.append(f"- {theme['name']} ({len(members)} notes): {theme['insight']}")
        lines += [f"    · ({n['source']}) {n['text'][:160]}" for n in members[:3]]
    return lines


def real_notes(db: Database, project_id: int) -> list[dict[str, Any]]:
    """Notes from real people: the user's own notes, interviews and usability tests."""
    board = db.get_document(project_id, "board") or empty_board()
    notes = [n for n in board["notes"] if n["source"] in REAL_SOURCES]
    data = db.get_validation(project_id) or {}
    known = {n["text"].casefold() for n in notes}
    for interview in data.get("interviews", []):
        for text in split_notes(interview["notes"]):
            if text.casefold() not in known:
                known.add(text.casefold())
                notes.append({"text": text, "source": "interview", "label": interview["person"]})
    return notes


def quote_from_notes(quote: str, notes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the note that contains the quote verbatim, if any."""
    return next((n for n in notes if quote_in_notes(quote, n["text"])), None)


def hmw_question(db: Database, project_id: int) -> str:
    """The How Might We question chosen for the project, or an empty string."""
    data = db.get_document(project_id, "empathy") or {}
    return data.get("hmw_chosen") or ""
