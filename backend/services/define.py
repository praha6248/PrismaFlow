"""Define phase: problem statements grounded in Discover evidence, compared on Google Trends, and personas."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from statistics import mean
from typing import Any

import httpx

from ..collectors import CollectorUnavailable, autocomplete, trends
from ..config import settings
from ..database import Database
from ..models import PersonaSet, ProblemSet
from ..retrieval import Retriever, graph_boost
from .discover import LANGUAGE_NAMES, StructuredLLM, normalize_label
from .jobs import ProgressFn, WarnFn

PROBLEM_SYSTEM = """You are a product strategist running the Define phase of the Double Diamond.
From a mind map and real evidence (search suggestions and community threads) you synthesise exactly three
distinct, competing problem statements a product could solve.
Rules:
- Write in {language}.
- Each title states one concrete frustration from the user's point of view in 4-7 words, no solution inside.
- Each description is one short sentence of at most 12 words explaining why it happens.
- The three problems must not overlap; each should be grounded in different nodes or evidence.
- trend_keyword is a short, popular everyday query (1-3 words) that people really type into Google when they have
  the problem; prefer common head terms that Google Trends can measure; the three keywords must all be different.
- quote_id must be the id of an evidence line that illustrates the problem, or 0 when none fits."""

PERSONA_SYSTEM = """You are a UX researcher creating proto-personas for the Define phase of the Double Diamond.
They are conceptual hypotheses to validate later, not interview results.
Rules:
- Write in {language}; use typical first names for that language.
- Create three clearly different people (age, life situation, motivation) who all experience the chosen problem.
- Spread their ages at least 8 years apart; include the person who pays for or decides about a solution (for example a parent, carer or teacher) when the problem concerns someone else.
- Base them on the target groups and evidence when available.
- The quote sounds natural and personal, as if said in an interview, 1-2 short sentences.
- Each persona has two concrete sub-problems (3-7 words each) that a product could address; avoid repeating them across personas."""


@dataclass
class DefineCollectors:
    """Injectable collector callables, replaceable in tests."""

    interest: Any = trends.interest
    suggestions: Any = autocomplete.suggestions


def monthly(dates: list[str], values: list[float], months: int = 12) -> list[dict[str, Any]]:
    """Average weekly Trends values per calendar month and keep the most recent months."""
    buckets: OrderedDict[str, list[float]] = OrderedDict()
    for date, value in zip(dates, values):
        buckets.setdefault(date[:7], []).append(value)
    rows = [{"month": key, "value": round(mean(vals), 1)} for key, vals in buckets.items()]
    return rows[-months:]


def summarize_trend(dates: list[str], series: list[float], anchor: str, anchor_ratio: float | None) -> dict[str, Any]:
    """Build the per-problem trend summary shown on Define cards."""
    if not series:
        return {"available": False, "anchor": anchor}
    return {
        "available": any(v > 0 for v in series),
        "index": round(mean(series)),
        "peak": max(series),
        "growth": trends.growth_3m_vs_9m(series),
        "anchor": anchor,
        "anchor_ratio": anchor_ratio,
        "months": monthly(dates, series),
    }


def define_state(db: Database, project_id: int) -> dict[str, Any]:
    """Return everything the Define screens need."""
    project = db.get_project(project_id)
    if project is None:
        raise LookupError(f"project {project_id} not found")
    problems = db.list_problems(project_id)
    chosen = next((p for p in problems if p["chosen"]), None)
    personas = db.list_personas(chosen["id"]) if chosen else []
    return {"project": project, "problems": problems, "personas": personas, "chosen_problem_id": chosen["id"] if chosen else None}


class DefineService:
    """Coordinates evidence retrieval, the local LLM and Google Trends for the Define phase."""

    def __init__(self, db: Database, llm: StructuredLLM, collectors: DefineCollectors | None = None) -> None:
        self.db = db
        self.llm = llm
        self.collectors = collectors or DefineCollectors()
        self.retriever = Retriever(db, llm)

    def _focus_nodes(self, project_id: int) -> list[dict[str, Any]]:
        nodes = [n for n in self.db.list_nodes(project_id) if not n["is_root"]]
        starred = [n for n in nodes if n["starred"]]
        if starred:
            return starred
        ranked = sorted(nodes, key=lambda n: (n["kind"] == "pain_point", n["score"]), reverse=True)
        return ranked[:6]

    @staticmethod
    def _query(focus: list[dict[str, Any]]) -> str:
        return " ".join(n["label"] for n in focus)

    async def _prepare(self, project_id: int, warn: WarnFn) -> None:
        await self.retriever.prepare(project_id, [self._query(self._focus_nodes(project_id))], warn)

    def _context(self, project_id: int) -> tuple[list[dict[str, Any]], str, dict[int, dict[str, Any]]]:
        nodes = {n["id"]: n for n in self.db.list_nodes(project_id)}
        edges = self.db.list_edges(project_id)
        focus = self._focus_nodes(project_id)
        focus_ids = {n["id"] for n in focus}
        neighbour_ids: set[int] = set()
        lines = []
        for node in focus:
            linked = [
                nodes[e["target_id"] if e["source_id"] == node["id"] else e["source_id"]]
                for e in edges
                if node["id"] in (e["source_id"], e["target_id"])
            ]
            neighbour_ids.update(n["id"] for n in linked if not n["is_root"])
            related = ", ".join(f"{n['label']} [{n['kind'] or 'niche'}]" for n in linked)
            lines.append(f"- {node['label']} [{node['kind'] or 'idea'}] — related: {related or 'none'}")

        evidence: OrderedDict[int, dict[str, Any]] = OrderedDict()
        for item in self.db.evidence_for_nodes([*focus_ids, *(neighbour_ids - focus_ids)], per_node=5):
            evidence.setdefault(item["id"], item)
        query = self._query(focus)
        for item in self.retriever.nearest(project_id, query, limit=12, boost=graph_boost(focus_ids, edges)):
            evidence.setdefault(item["id"], item)
        for item in self.db.search_evidence(project_id, query, limit=12):
            if item["source"] in ("community", "reddit", "autocomplete"):
                evidence.setdefault(item["id"], item)
        trimmed = dict(list(evidence.items())[:40])
        return focus, "\n".join(lines), trimmed

    async def generate_problems(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Synthesise three problem statements and compare them on one Google Trends scale."""
        project = self.db.get_project(project_id)
        if project is None:
            raise LookupError(f"project {project_id} not found")
        language, geo = project["language"], project["geo"]

        progress(0.05, "context")
        await self._prepare(project_id, warn)
        focus, map_lines, evidence = self._context(project_id)
        if not focus:
            raise ValueError("the map has no topics yet; add or expand nodes in Discover first")
        evidence_lines = [
            f"[{item['id']}] ({item['source']}) {item['title']}" + (f" — {item['body'][:160]}" if item.get("body") else "")
            for item in evidence.values()
        ]
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                "Topics the founder selected, with their neighbourhood in the map:",
                map_lines,
                "",
                "Evidence lines (id, source, text):",
                *(evidence_lines or ["(no evidence collected yet)"]),
                "",
                "Return exactly three problem statements.",
            ]
        )

        progress(0.15, "thinking")
        result: ProblemSet = await self.llm.structured(
            ProblemSet,
            PROBLEM_SYSTEM.format(language=LANGUAGE_NAMES.get(language, "the niche's language")),
            prompt,
            temperature=0.5,
        )
        drafts = result.problems[:3]
        if len(drafts) < 3:
            raise ValueError("the model returned fewer than three problems")

        progress(0.5, "trends")
        anchor = trends.anchor_for(language)
        keywords = list(dict.fromkeys(d.trend_keyword for d in drafts if d.trend_keyword))
        trend_data, ratios = await self._compare_trends(keywords, anchor, geo, warn)

        progress(0.75, "quotes")
        by_label = {normalize_label(n["label"]): n for n in self.db.list_nodes(project_id)}
        rows = []
        async with httpx.AsyncClient(timeout=settings.http_timeout, headers={"User-Agent": settings.user_agent}) as http:
            for draft in drafts:
                quote, source = None, None
                picked = evidence.get(draft.quote_id)
                if picked:
                    quote, source = picked["title"], picked["source"]
                else:
                    try:
                        hints = await self.collectors.suggestions(self.db, http, draft.trend_keyword, language, geo)
                    except CollectorUnavailable as exc:
                        warn(f"autocomplete: {exc}")
                        hints = []
                    if hints:
                        quote, source = hints[0], "autocomplete"
                node_ids = [by_label[k]["id"] for k in map(normalize_label, draft.node_labels) if k in by_label]
                rows.append(
                    {
                        "title": draft.title,
                        "description": draft.description,
                        "keyword": draft.trend_keyword,
                        "quote": quote,
                        "quote_source": source,
                        "node_ids": node_ids,
                        "evidence_ids": [draft.quote_id] if picked else [],
                        "trend": summarize_trend(
                            trend_data["dates"],
                            trend_data["series"].get(draft.trend_keyword) or [],
                            anchor,
                            ratios.get(draft.trend_keyword),
                        ),
                    }
                )

        progress(0.95, "saving")
        self.db.replace_problems(project_id, rows)
        self.db.update_project(project_id, phase="define", stage="problems")
        return define_state(self.db, project_id)

    async def _compare_trends(
        self, keywords: list[str], anchor: str, geo: str, warn: WarnFn
    ) -> tuple[dict[str, Any], dict[str, float]]:
        """Compare keywords on one shared scale, then calibrate the strongest against the anchor."""
        empty: dict[str, Any] = {"dates": [], "series": {}}
        try:
            data = await self.collectors.interest(self.db, keywords, geo)
        except CollectorUnavailable as exc:
            warn(f"trends: {exc}")
            return empty, {}
        means = {k: mean(v) for k, v in data["series"].items() if v}
        strongest = max(means, key=means.get, default=None)
        ratios: dict[str, float] = {}
        if strongest and means[strongest] > 0:
            try:
                calibration = await self.collectors.interest(self.db, [strongest, anchor], geo)
                own = calibration["series"].get(strongest) or []
                reference = calibration["series"].get(anchor) or []
                if own and reference and mean(reference) > 0:
                    top_ratio = mean(own) / mean(reference)
                    ratios = {k: round(top_ratio * m / means[strongest], 4) for k, m in means.items()}
            except CollectorUnavailable as exc:
                warn(f"trends: {exc}")
        return data, ratios

    async def generate_personas(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Create three conceptual personas for the chosen problem."""
        project = self.db.get_project(project_id)
        if project is None:
            raise LookupError(f"project {project_id} not found")
        problem = next((p for p in self.db.list_problems(project_id) if p["chosen"]), None)
        if problem is None:
            raise ValueError("choose a problem before generating personas")
        language = project["language"]

        progress(0.1, "context")
        nodes = self.db.list_nodes(project_id)
        groups = [n["label"] for n in nodes if n["kind"] == "target_group"]
        await self._prepare(project_id, warn)
        _, _, evidence = self._context(project_id)
        lines = [f"- ({item['source']}) {item['title']}" for item in list(evidence.values())[:20]]
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                f'Chosen problem: "{problem["title"]}" — {problem["description"]}',
                f"Target groups from the map: {', '.join(groups) if groups else 'not specified'}",
                "Evidence:",
                *(lines or ["(none)"]),
                "",
                "Create exactly three personas.",
            ]
        )

        progress(0.25, "personas")
        result: PersonaSet = await self.llm.structured(
            PersonaSet,
            PERSONA_SYSTEM.format(language=LANGUAGE_NAMES.get(language, "the niche's language")),
            prompt,
            temperature=0.7,
        )
        personas = [
            {"name": p.name, "age": p.age, "role": p.role, "quote": p.quote, "options": p.problems}
            for p in result.personas[:3]
            if len(p.problems) == 2
        ]
        if len(personas) < 3:
            raise ValueError("the model returned incomplete personas")

        progress(0.95, "saving")
        self.db.replace_personas(project_id, problem["id"], personas)
        self.db.update_project(project_id, phase="define", stage="personas")
        return define_state(self.db, project_id)
