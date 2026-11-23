"""Define phase: problem statements grounded in Discover evidence, compared on Google Trends, and personas."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from statistics import mean
import re
from typing import Any

from ..collectors import CollectorUnavailable, community, trends
from ..ollama_client import OllamaError
from ..database import Database
from ..models import PersonaSet, ProblemSet, RelevantItems
from ..retrieval import Retriever, graph_boost
from .discover import LANGUAGE_NAMES, StructuredLLM, normalize_label
from .translate import trend_queries
from .jobs import ProgressFn, WarnFn
from .research import board_lines, quote_from_notes, real_notes

PROBLEM_SYSTEM = """You are a product strategist running the Define phase of the Double Diamond.
From a mind map, research notes and community discussions you synthesise exactly three
distinct, competing problem statements a product could solve.
Rules:
- Write in {language}.
- Each title states one concrete frustration from the user's point of view in 4-7 words, no solution inside.
- Each description is one short sentence of at most 12 words explaining why it happens.
- The three problems must not overlap; each should be grounded in different nodes or evidence.
- trend_keyword is a short, popular everyday query (1-3 words) that people really type into Google when they have
  the problem; prefer common head terms that Google Trends can measure; the three keywords must all be different.
- quote_id must be the id of an evidence line that illustrates the problem, or 0 when none fits.
- evidence_ids lists 2-5 ids of evidence lines that show real people have this problem. Every problem must be
  supported by evidence where available. For hypotheses based on notes or the map alone, leave the ids empty."""

PERSONA_SYSTEM = """You are a UX researcher creating proto-personas for the Define phase of the Double Diamond.
They are conceptual hypotheses to validate later, not interview results.
Rules:
- Write every field, including role and life situation, in {language}; use typical first names for that language.
- Create three clearly different people (age, life situation, motivation) who all experience the chosen problem.
- Spread their ages at least 8 years apart and keep every age realistic for the role (a parent of a teenager or student is at least 36); include the person who pays for or decides about a solution (for example a parent, carer or teacher) when the problem concerns someone else.
- Ground every persona in the evidence: their situation, wording and sub-problems must follow from real lines,
  and evidence_ids lists 1-4 ids of the lines each persona is based on. Use only ids from the list.
- Avoid generic personas: give each a specific context (where, when, with what tools) visible in the evidence.
- The quote sounds natural and personal, as if said in an interview, 1-2 short sentences.
- Write each profile field in the project language in one concise sentence. Anchor the scenario in the chosen task.
  Treat inferred device, setting and behaviour as hypotheses. Do not invent interview findings or statistics.
  Ask about a recent real event in the interview question.
- Each persona has two concrete sub-problems (3-7 words each) that a product could address; avoid repeating them across personas."""


@dataclass
class DefineCollectors:
    """Injectable collector callables, replaceable in tests."""

    interest: Any = trends.interest


PARENT = re.compile(r"rodzic|matk|mama|ojc|tata|tat\b|opiekun|parent|mother|father|mom\b|dad\b|carer|guardian", re.IGNORECASE)
YOUNG = re.compile(r"uczeń|uczen|uczenni|licealist|nastolat|maturzyst|student|pupil|teen|high school|pierwszoklasist", re.IGNORECASE)
AGE_RULES: tuple[tuple[re.Pattern[str], int, int], ...] = (
    (re.compile(r"emeryt|senior|retire", re.IGNORECASE), 58, 95),
    (re.compile(r"dziadek|babci|grandparent|grandmother|grandfather", re.IGNORECASE), 45, 95),
    (re.compile(r"dyrektor|kierownik|manager|właściciel|wlasciciel|owner|prezes", re.IGNORECASE), 25, 75),
    (re.compile(r"nauczyciel|doradc|doradzk|lekarz|terapeut|psycholog|counsel|teacher|doctor|therapist|pedagog|wykładowc|lecturer", re.IGNORECASE), 24, 75),
    (re.compile(r"uczeń|uczen|uczenni|pupil|pierwszoklasist", re.IGNORECASE), 7, 19),
    (re.compile(r"licealist|maturzyst|high school|nastolat|teen", re.IGNORECASE), 14, 20),
    (re.compile(r"student", re.IGNORECASE), 18, 35),
)


def age_range(persona: dict[str, Any], others: list[dict[str, Any]]) -> tuple[int, int]:
    """Return the plausible age range for a persona from its role and the other personas.

    A parent or carer must be at least 25, and at least 18 years older than the oldest
    pupil or student among the other personas, since that is whose problem they share.
    """
    role = persona["role"]
    low, high = 16, 85
    if PARENT.search(role):
        young = [o["age"] for o in others if YOUNG.search(o["role"]) and not PARENT.search(o["role"])]
        low = max(25, max(young, default=0) + 18)
        return low, 85
    for pattern, minimum, maximum in AGE_RULES:
        if pattern.search(role):
            return minimum, maximum
    return low, high


def age_issues(personas: list[dict[str, Any]]) -> list[str]:
    """List the personas whose age does not fit their role."""
    issues = []
    for index, persona in enumerate(personas):
        others = personas[:index] + personas[index + 1 :]
        low, high = age_range(persona, others)
        if not low <= persona["age"] <= high:
            issues.append(f'{persona["name"]} ({persona["role"]}) is {persona["age"]}, but should be {low}-{high}')
    return issues


def fix_ages(personas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Move every implausible age into its role's range, a few years above the minimum."""
    fixed = [dict(p) for p in personas]
    for index, persona in enumerate(fixed):
        low, high = age_range(persona, fixed[:index] + fixed[index + 1 :])
        if persona["age"] < low:
            persona["age"] = min(high, low + 4)
        elif persona["age"] > high:
            persona["age"] = high
    return fixed


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


def supports_persona(item: dict[str, Any], problem: dict[str, Any]) -> bool:
    """Require a discussion related to the selected problem before citing it for a persona."""
    if item["source"] not in ("community", "reddit"):
        return False
    text = " ".join((item["title"], item.get("body") or "", (item.get("meta") or {}).get("original") or ""))
    title_terms = community.terms(problem["title"])
    keyword_terms = community.terms(problem.get("keyword") or "")
    qualifiers = [term for term in title_terms if term in community.SHORT_TERMS]
    if qualifiers and not community.relevant(text, qualifiers, 1):
        return False
    return community.relevant(text, title_terms, 0.4) or community.relevant(text, keyword_terms, 0.5)


def define_state(db: Database, project_id: int) -> dict[str, Any]:
    """Return everything the Define screens need."""
    project = db.get_project(project_id)
    if project is None:
        raise LookupError(f"project {project_id} not found")
    problems = db.list_problems(project_id)
    chosen = next((p for p in problems if p["chosen"]), None)
    personas = db.list_personas(chosen["id"]) if chosen else []
    for item in [*problems, *personas]:
        seen: set[str] = set()
        item["evidence"] = []
        for e in db.evidence_by_ids(item["evidence_ids"]):
            if "role" in item and chosen and not supports_persona(e, chosen):
                continue
            key = e["title"].casefold()
            if key not in seen:
                seen.add(key)
                item["evidence"].append(
                    {"id": e["id"], "source": e["source"], "title": e["title"], "url": e["url"] or e["meta"].get("url"), "place": e["meta"].get("place")}
                )
        item["evidence_ids"] = [e["id"] for e in item["evidence"]]
    return {"project": project, "problems": problems, "personas": personas, "chosen_problem_id": chosen["id"] if chosen else None}


def cited(ids: list[int], pool: dict[int, Any], limit: int = 5) -> list[int]:
    """Keep only evidence ids that exist in the pool, without duplicates."""
    return [i for i in dict.fromkeys(ids) if i in pool][:limit]


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
        evidence = {key: item for key, item in evidence.items() if item["source"] in ("community", "reddit")}
        evidence_lines = [
            f"[{item['id']}] ({item['source']}) {item['title']}" + (f" — {item['body'][:160]}" if item.get("body") else "")
            for item in evidence.values()
        ]
        themes = board_lines(self.db, project_id)
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                "Topics the founder selected, with their neighbourhood in the map:",
                map_lines,
                "",
                "Evidence lines (id, source, text):",
                *(evidence_lines or ["(no evidence collected yet)"]),
                *(["", "Themes the founder found on the affinity board (base the problems on these first):", *themes] if themes else []),
                "",
                "Return exactly three problem statements.",
            ]
        )

        progress(0.15, "thinking")
        system = PROBLEM_SYSTEM.format(language=LANGUAGE_NAMES.get(language, "the niche's language"))
        result: ProblemSet = await self.llm.structured(ProblemSet, system, prompt, temperature=0.5)
        drafts = result.problems[:3]
        if len(drafts) < 3:
            raise ValueError("the model returned fewer than three problems")
        progress(0.5, "trends")
        keywords = list(dict.fromkeys(d.trend_keyword for d in drafts if d.trend_keyword))
        summaries = {keyword: {} for keyword in keywords}
        for code, terms in (await trend_queries(self.llm, keywords, language)).items():
            region = "PL" if code == "pl" else ""
            anchor = trends.anchor_for(code)
            distinct = list(dict.fromkeys(term for term in terms if term))
            if not distinct:
                continue
            data, ratios = await self._compare_trends(distinct, anchor, region, warn)
            for keyword, term in zip(keywords, terms):
                if term:
                    summaries[keyword][code] = {
                        **summarize_trend(data["dates"], data["series"].get(term) or [], anchor, ratios.get(term)),
                        "query": term,
                    }

        progress(0.75, "quotes")
        by_label = {normalize_label(n["label"]): n for n in self.db.list_nodes(project_id)}
        rows = []
        # A valid id can still point to a discussion about a different problem.
        pairs = [
            (index, key)
            for index, draft in enumerate(drafts)
            for key in cited([draft.quote_id, *draft.evidence_ids], evidence)
        ]
        approved: list[list[int]] = [[] for _ in drafts]
        if pairs:
            lines = [
                f"{n}. Problem: {drafts[index].title} — {drafts[index].description} | "
                f"Source: {evidence[key]['title']} {(evidence[key].get('body') or '')[:300]}"
                for n, (index, key) in enumerate(pairs, 1)
            ]
            try:
                check = await self.llm.structured(
                    RelevantItems,
                    "Return the numbers of pairs where the source directly illustrates the stated problem "
                    "in the given niche. Reject mere keyword matches, general news and ambiguous cases.",
                    f"Niche: {project['seed']}\n" + "\n".join(lines), temperature=0,
                )
                for n in dict.fromkeys(check.relevant):
                    if 1 <= n <= len(pairs):
                        index, key = pairs[n - 1]
                        approved[index].append(key)
            except (OllamaError, ValueError) as exc:
                warn(f"screening: {exc}")
        for index, draft in enumerate(drafts):
            picked = evidence.get(draft.quote_id) if draft.quote_id in approved[index] else None
            quote = picked["title"] if picked else None
            source = picked["source"] if picked else None
            node_ids = [by_label[k]["id"] for k in map(normalize_label, draft.node_labels) if k in by_label]
            markets = summaries.get(draft.trend_keyword, {})
            primary = markets.get(language) or markets.get("pl") or markets.get("en") or {}
            if not primary.get("available"):
                primary = next((row for row in markets.values() if row["available"]), primary)
            primary = {"available": False, "anchor": trends.anchor_for(language), **primary}
            rows.append(
                {
                    "title": draft.title,
                    "description": draft.description,
                    "keyword": draft.trend_keyword,
                    "quote": quote,
                    "quote_source": source,
                    "node_ids": node_ids,
                    "evidence_ids": approved[index],
                    "trend": {**primary, "markets": markets},
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

    async def _draft_personas(self, system: str, prompt: str, pool: dict[int, Any]) -> list[dict[str, Any]]:
        result: PersonaSet = await self.llm.structured(PersonaSet, system, prompt, temperature=0.7)
        personas = [
            {"name": p.name, "age": p.age, "role": p.role, "quote": p.quote, "options": p.problems, "profile": p.profile.model_dump(), "evidence_ids": cited(p.evidence_ids, pool, 4)}
            for p in result.personas[:3]
            if len(p.problems) == 2
        ]
        if len(personas) < 3:
            raise ValueError("the model returned incomplete personas")
        return personas

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
        relevant = [(key, item) for key, item in evidence.items() if supports_persona(item, problem)]
        pool = dict(relevant[:24])
        lines = [f"[{item['id']}] ({item['source']}) {item['title']}" for item in pool.values()]
        notes = real_notes(self.db, project_id)
        prompt = "\n".join(
            [
                f'Niche: "{project["seed"]}"',
                f'Chosen problem: "{problem["title"]}" — {problem["description"]}',
                f"Target groups from the map: {', '.join(groups) if groups else 'not specified'}",
                "Evidence lines (id, source, text):",
                *(lines or ["(none)"]),
                *(
                    [
                        "",
                        "Notes from real people (interviews, the founder's notes, usability tests). When a persona matches",
                        "one of them, copy its quote word for word from these notes instead of writing a new one:",
                        *[f"- ({n['source']}{', ' + n['label'] if n.get('label') else ''}) {n['text'][:300]}" for n in notes[:20]],
                    ]
                    if notes
                    else []
                ),
                "",
                "Create exactly three personas.",
            ]
        )

        progress(0.25, "personas")
        system = PERSONA_SYSTEM.format(language=LANGUAGE_NAMES.get(language, "the niche's language"))
        personas = await self._draft_personas(system, prompt, pool)
        issues = age_issues(personas)
        if pool:
            issues += [f"{p['name']} cites no evidence" for p in personas if not p["evidence_ids"]]
        if issues:
            progress(0.6, "personas")
            retry = prompt + "\n\nFix these problems in your previous personas: " + "; ".join(issues) + ". A parent must be old enough to have the child described; every persona cites the evidence ids it is based on."
            try:
                personas = await self._draft_personas(system, retry, pool)
            except ValueError:
                pass
            personas = fix_ages(personas)

        for persona in personas:
            match = quote_from_notes(persona["quote"], notes)
            if match:
                persona["profile"]["quote_source"] = f"{match['source']}:{match.get('label', '')}"
        progress(0.95, "saving")
        self.db.replace_personas(project_id, problem["id"], personas)
        self.db.update_project(project_id, phase="define", stage="personas")
        return define_state(self.db, project_id)
