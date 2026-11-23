"""Discover phase: mind-map management and AI expansion grounded in market data."""

from __future__ import annotations

import asyncio
import math
import re
import time
from dataclasses import dataclass
from statistics import mean
from typing import Any, Protocol

import httpx

from ..collectors import CollectorUnavailable, autocomplete, community, trends
from ..config import COUNTRY_FOR_LANGUAGE, settings
from ..database import Database
from ..models import CompetitorCheck, ExpansionPlan, NodeKind, ProposedNode, RelevantItems
from ..ollama_client import OllamaError
from .jobs import ProgressFn, WarnFn
from .translate import translate, trend_queries

LANGUAGE_NAMES = {
    "pl": "Polish",
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "uk": "Ukrainian",
    "cs": "Czech",
}

SYSTEM_PROMPT = """You are a product discovery researcher helping a founder map a product niche (Double Diamond, Discover phase).
You grow a mind map whose nodes have one of these kinds:
- idea: a product direction, feature, activity or sub-topic worth building around (e.g. for the niche "cooking": "meal prep", "batch cooking app").
- target_group: a concrete group of PEOPLE who would use the product, always a plural noun for people (e.g. "busy parents",
  "students"). Never an activity, place, job, benefit or object.
- pain_point: a real frustration those people experience, phrased as a problem (e.g. "no time to cook", "food waste").
  Never a neutral or positive word such as "peace" or "relationships".
- competitor: an existing named product, brand or service (e.g. "HelloFresh"). A profession, a place or a product
  category ("physiotherapist", "libraries", "budgeting apps") is never a competitor.
Rules:
- Propose a competitor only when its name appears in the search suggestions or you are certain it exists and serves
  this exact niche. Never invent brand names or domains; when unsure, propose another kind instead.
- Labels are 1-3 words, lowercase unless a brand name, without underscores or hashtags, written in {language}.
- Never repeat or paraphrase an existing label.
- Ground proposals in the real search suggestions when they reveal audiences, problems or products.
- Stay inside the niche: every node must matter for this exact product, not for its audience's life in general.
- Never propose the product format or a platform as a node ("mobile app", "website", "platform", "iPhone", "Android",
  "free"); when the focus node is such a format, expand the needs and problems it would serve instead.
- search_query is a 2-5 word phrase in {language} that joins the node with the niche so the search stays on topic
  (for the niche "training plan after a knee injury" and the node "rehabilitation": "knee rehabilitation exercises").
  Give one for every classified node too.
- connects_to lists 1-2 exact labels from the map (existing or newly proposed) that the node is meaningfully related to."""


RELEVANCE_SYSTEM = """You screen web search results collected as evidence for product research.
A result is relevant when it is about the people, problems, needs, habits or products of the given niche.
Results that only share a word with the topic are irrelevant: pets, films, games, politics, memes, other products.
Return the numbers of the relevant results only."""

COMPETITOR_SYSTEM = "You label names from a product research mind map. Answer each field literally for every numbered name."

RELEVANCE_LOW = 0.36
RELEVANCE_HIGH = 0.58
FORMATS = {
    "aplikacja", "aplikacja mobilna", "aplikacja webowa", "aplikacja internetowa", "strona internetowa", "strona www",
    "platforma", "platforma online", "darmowa", "darmowa aplikacja", "app", "mobile app", "web app", "website",
    "platform", "online platform", "free", "free app", "iphone", "android", "ios",
}
POLISH_LETTERS = set("ąćęłńóśźż")
POLISH_WORDS = {"i", "w", "z", "na", "do", "dla", "po", "jak", "się", "nie", "oraz", "który", "aplikacja", "dla"}
ENGLISH_WORDS = {"the", "a", "an", "to", "for", "in", "of", "that", "and", "with", "app", "my", "your", "find", "finds", "how"}


def guess_language(texts: list[str]) -> str | None:
    """Detect Polish or English from letters and function words, or None when unsure."""
    joined = " ".join(texts).casefold()
    if any(c in POLISH_LETTERS for c in joined):
        return "pl"
    words = set(re.findall(r"[a-z]+", joined))
    english, polish = len(words & ENGLISH_WORDS), len(words & POLISH_WORDS)
    if english >= 1 and english > polish:
        return "en"
    if polish >= 2:
        return "pl"
    return None


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two raw vectors."""
    norm = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / norm


class StructuredLLM(Protocol):
    """Subset of the Ollama client used by this service."""

    async def structured(self, schema: Any, system: str, prompt: str, **kwargs: Any) -> Any: ...


@dataclass
class Collectors:
    """Injectable bundle of collector callables, replaceable in tests."""

    suggestions: Any = autocomplete.expanded_suggestions
    simple_suggestions: Any = autocomplete.suggestions
    community_search: Any = community.search
    trend_growth: Any = trends.calibrated_growth


def normalize_label(label: str) -> str:
    """Collapse whitespace and casing for duplicate detection."""
    return " ".join(label.replace("_", " ").split()).casefold()


def mentions(text: str, name: str) -> bool:
    """Whether a brand name occurs in text as a whole word or phrase."""
    needle = " ".join(name.casefold().split())
    if len(needle) < 3:
        return False
    return re.search(rf"(?<![\w.]){re.escape(needle)}(?![\w])", " ".join(text.casefold().split())) is not None


def graph(db: Database, project_id: int) -> dict[str, Any]:
    """Return the full serialisable state of a project's mind map."""
    project = db.get_project(project_id)
    if project is None:
        raise LookupError(f"project {project_id} not found")
    return {"project": project, "nodes": db.list_nodes(project_id), "edges": db.list_edges(project_id)}


def create_project(db: Database, seed: str) -> dict[str, Any]:
    """Start a new project around a seed niche."""
    language = guess_language([seed]) or settings.language
    geo = settings.country if settings.country and language == settings.language else COUNTRY_FOR_LANGUAGE.get(language, "")
    project = db.create_project(seed, language, geo)
    return graph(db, project["id"])


def add_node(
    db: Database,
    project_id: int,
    label: str,
    connect_to: int | None = None,
    x: float | None = None,
    y: float | None = None,
) -> dict[str, Any]:
    """Add a user-typed association and link it to the chosen node or the root."""
    anchor = db.get_node(connect_to) if connect_to else None
    if anchor is None or anchor["project_id"] != project_id:
        anchor = db.root_node(project_id)
    node = db.insert_node(project_id, label, origin="user", x=x, y=y)
    if node["id"] != anchor["id"]:
        db.insert_edge(project_id, anchor["id"], node["id"], origin="user")
    return graph(db, project_id)


def node_evidence(db: Database, node_id: int) -> dict[str, Any]:
    """Return a node with its grouped evidence for the details drawer."""
    node = db.get_node(node_id)
    if node is None:
        raise LookupError(f"node {node_id} not found")
    items = db.list_evidence(node_id)
    return {
        "node": node,
        "suggestions": [i for i in items if i["source"] == "autocomplete"],
        "quotes": [i for i in items if i["source"] in ("community", "reddit")],
        "trend": {
            "markets": (node["trend_series"] or {}).get("markets", {}),
            "primary": (node["trend_series"] or {}).get("primary"),
            "growth": node["trend_growth"],
            "series": (node["trend_series"] or {}).get("series", []),
            "dates": (node["trend_series"] or {}).get("dates", []),
            "anchor": (node["trend_series"] or {}).get("anchor"),
            "anchor_ratio": (node["trend_series"] or {}).get("anchor_ratio"),
        },
    }


async def english_discussions(db: Database, llm: Any, evidence: dict[str, Any]) -> None:
    """Localize display titles without modifying the source records."""
    from ..collectors.base import cache_key

    project = db.get_project(evidence["node"]["project_id"])
    pending = []
    for quote in evidence["quotes"][:5]:
        meta = quote["meta"]
        if meta.get("lang") == "en" and meta.get("original"):
            quote["title"] = meta["original"]
        elif project and project["language"] != "en":
            key = cache_key("english-discussion", quote["title"])
            hit = db.cache_get(key, settings.cache_ttl_seconds, settings.negative_cache_ttl_seconds)
            if hit:
                quote["title"] = hit[1]
            else:
                pending.append((quote, key))
    if pending:
        titles = [quote["title"] for quote, _ in pending]
        translated = await translate(llm, titles, "English", fallback=False)
        for (quote, key), title in zip(pending, translated):
            if title:
                db.cache_put(key, "english-discussion", quote["title"], "ok", title)
                quote["title"] = title
            else:
                quote["meta"]["translation_unavailable"] = True


def build_prompt(
    project: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    focus: dict[str, Any],
    suggestions: list[str],
    count: int,
) -> str:
    """Compose the user prompt describing the current map to the model."""
    by_id = {n["id"]: n for n in nodes}
    lines = []
    for node in nodes:
        kind = "niche" if node["is_root"] else (node["kind"] or "unclassified")
        neighbours = [
            by_id[e["target_id"] if e["source_id"] == node["id"] else e["source_id"]]["label"]
            for e in edges
            if node["id"] in (e["source_id"], e["target_id"])
        ]
        suffix = f" — linked to: {', '.join(neighbours)}" if neighbours else ""
        lines.append(f"- {node['label']} [{kind}]{suffix}")
    unclassified = [n["label"] for n in nodes if not n["is_root"] and not n["kind"]]
    kinds_present = {n["kind"] for n in nodes if n["kind"]}
    missing = [k.value for k in NodeKind if k.value not in kinds_present]
    parts = [
        f'Niche: "{project["seed"]}"',
        "Current map:",
        *lines,
        "",
        f'Focus node to expand: "{focus["label"]}"',
    ]
    if suggestions:
        parts += ["", f'Real Google search suggestions around "{focus["label"]}":', *[f"- {s}" for s in suggestions[:20]]]
    parts += ["", "Tasks:", "0. Report the ISO 639-1 language code the niche and user labels are written in."]
    if unclassified:
        parts.append(f"1. Classify each of these nodes: {', '.join(unclassified)}.")
    else:
        parts.append("1. All nodes are already classified, so leave the classified list empty.")
    hint = f" Prefer kinds still missing from the map: {', '.join(missing)}." if missing else ""
    parts.append(
        f"2. Always propose exactly {count} new nodes in new_nodes that deepen the focus node, with at least one target_group or "
        f"pain_point among them.{hint} Each new node connects to the focus node or another relevant label."
    )
    return "\n".join(parts)


def fallback_plan(focus: dict[str, Any], suggestions: list[str], existing: set[str], count: int) -> ExpansionPlan:
    """Derive new idea nodes from raw search suggestions when the model is unavailable."""
    base = normalize_label(focus["label"])
    proposals: list[ProposedNode] = []
    for suggestion in suggestions:
        words = [w for w in suggestion.split() if normalize_label(w) not in base.split()]
        label = " ".join(words[:3]).strip()
        if not label or normalize_label(label) in existing or len(label) < 3:
            continue
        existing.add(normalize_label(label))
        proposals.append(
            ProposedNode(label=label, kind=NodeKind.idea, connects_to=[focus["label"]], search_query=suggestion)
        )
        if len(proposals) >= count:
            break
    return ExpansionPlan(classified=[], new_nodes=proposals)


def score_node(suggestion_count: int, posts: list[dict] | None, trend: dict[str, Any] | None) -> float:
    """Blend search breadth, discussion volume and trend strength into a 0..1 demand score."""
    parts: list[float] = [min(1.0, suggestion_count / 10)]
    if posts is not None:
        engagement = sum(p.get("score", 0) + p.get("comments", 0) for p in posts)
        parts.append(min(1.0, math.log1p(engagement) / math.log1p(5000)))
    if trend and trend.get("series"):
        ratio = trend.get("anchor_ratio") or 0.0
        level = 1 - math.exp(-ratio / 2)
        growth = trend.get("growth") or 0.0
        momentum = (max(-0.5, min(1.0, growth)) + 0.5) / 1.5
        parts.append(0.7 * level + 0.3 * momentum)
    return round(mean(parts), 4)


class DiscoverService:
    """Coordinates the database, collectors and local LLM for the Discover phase."""

    def __init__(self, db: Database, llm: StructuredLLM, collectors: Collectors | None = None) -> None:
        self.db = db
        self.llm = llm
        self.collectors = collectors or Collectors()

    async def expand(
        self,
        project_id: int,
        node_id: int | None,
        count: int,
        progress: ProgressFn,
        warn: WarnFn,
    ) -> dict[str, Any]:
        """Grow the map around a node: classify, propose, enrich and score."""
        project = self.db.get_project(project_id)
        if project is None:
            raise LookupError(f"project {project_id} not found")
        focus = self.db.get_node(node_id) if node_id else None
        if focus is None or focus["project_id"] != project_id:
            focus = self.db.root_node(project_id)
        language, geo = project["language"], project["geo"]

        async with httpx.AsyncClient(timeout=settings.http_timeout, headers={"User-Agent": settings.user_agent}) as http:
            progress(0.05, "suggestions")
            try:
                suggestions = await self.collectors.suggestions(
                    self.db, http, focus["search_query"] or focus["label"], language, geo
                )
            except CollectorUnavailable as exc:
                suggestions = []
                warn(f"autocomplete: {exc}")

            progress(0.15, "thinking")
            nodes = self.db.list_nodes(project_id)
            edges = self.db.list_edges(project_id)
            existing = {normalize_label(n["label"]) for n in nodes}
            try:
                plan: ExpansionPlan = await self.llm.structured(
                    ExpansionPlan,
                    SYSTEM_PROMPT.format(language=LANGUAGE_NAMES.get(language, "the niche's language")),
                    build_prompt(project, nodes, edges, focus, suggestions, count),
                )
            except OllamaError as exc:
                warn(f"llm: {exc}")
                plan = fallback_plan(focus, suggestions, set(existing), count)

            progress(0.45, "placing")
            typed = [project["seed"], *(n["label"] for n in nodes if n["origin"] == "user" and not n["is_root"])]
            project = self._adopt_language(project, guess_language(typed) or plan.language)
            touched = self._apply_plan(project_id, focus, nodes, plan, count)

            progress(0.55, "evidence")
            await self._enrich(project, touched, http, progress, warn)

        current = [self.db.get_node(n["id"]) for n in touched]
        candidates = [n for n in current if n and n["kind"] == NodeKind.competitor.value]
        for label in await self._check_competitors(project, candidates, suggestions, warn):
            warn(f"competitor: {label}")
        self._reattach(project_id, focus)

        self.db.update_project(project_id, stage="select")
        return graph(self.db, project_id)

    async def _screen(
        self, seed: str, nodes: list[dict[str, Any]], gathered: dict[int, dict[str, Any]], warn: WarnFn
    ) -> None:
        """Keep only discussions that are about the niche, not just sharing a word with a node."""
        labels = {n["id"]: n["label"] for n in nodes}
        items = [
            (node_id, key, index, f"{post['title']} {(post.get('body') or '')[:200]}".strip())
            for node_id, entry in gathered.items()
            for key in ("posts", "en_posts")
            for index, post in enumerate(entry.get(key) or [])
        ]
        if not items:
            return
        sims: list[float] | None = None
        if callable(getattr(self.llm, "embed", None)):
            try:
                vectors = await self.llm.embed([seed, *(text for *_, text in items)])
                sims = [cosine(vectors[0], v) for v in vectors[1:]]
            except (OllamaError, httpx.HTTPError) as exc:
                warn(f"screening: {exc}")
        keep: set[int] = set()
        unsure: list[int] = []
        for position in range(len(items)):
            sim = sims[position] if sims else None
            if sim is None or sim >= RELEVANCE_LOW:
                unsure.append(position)
        for start in range(0, len(unsure), 30):
            chunk = unsure[start : start + 30]
            lines = [f"{n}. [{labels[items[p][0]]}] {items[p][3][:180]}" for n, p in enumerate(chunk, 1)]
            try:
                verdict: RelevantItems = await self.llm.structured(
                    RelevantItems, RELEVANCE_SYSTEM, f'Niche: "{seed}"\n\nResults:\n' + "\n".join(lines), temperature=0
                )
                keep.update(chunk[n - 1] for n in verdict.relevant if 1 <= n <= len(chunk))
            except OllamaError as exc:
                warn(f"screening: {exc}")
        for position, (node_id, key, index, _) in enumerate(items):
            if position not in keep:
                gathered[node_id][key][index] = None
        for entry in gathered.values():
            for key in ("posts", "en_posts"):
                if entry.get(key):
                    entry[key] = [post for post in entry[key] if post is not None]

    async def _check_competitors(
        self, project: dict[str, Any], candidates: list[dict[str, Any]], suggestions: list[str], warn: WarnFn
    ) -> list[str]:
        """Keep named products, turn categories into ideas or groups, delete invented AI competitors."""
        if not candidates:
            return []
        texts = [s.casefold() for s in suggestions]
        for node in self.db.list_nodes(project["id"]):
            for item in self.db.list_evidence(node["id"]):
                if item["source"] in ("community", "reddit"):
                    texts.append(f"{item['title']} {item.get('body') or ''}")
                    original = item["meta"].get("original")
                    if original:
                        texts.append(original)
        own = {
            node["id"]: [i["title"] for i in self.db.list_evidence(node["id"]) if i["source"] == "autocomplete"][:6]
            for node in candidates
        }
        mentioned = {n["id"]: any(mentions(text, n["label"]) for text in texts) for n in candidates}
        searched = {n["id"]: any(mentions(text, n["label"]) for text in own[n["id"]]) for n in candidates}
        lines = [f"{i}. {n['label']}" for i, n in enumerate(candidates, 1)]
        verdicts: dict[int, Any] = {}
        try:
            check: CompetitorCheck = await self.llm.structured(
                CompetitorCheck, COMPETITOR_SYSTEM, f'Niche: "{project["seed"]}"\n\n' + "\n".join(lines), temperature=0
            )
            verdicts = {v.number: v for v in check.items if 1 <= v.number <= len(candidates)}
        except OllamaError as exc:
            warn(f"competitors: {exc}")
        near = await self._near_niche(project["seed"], {n["id"]: [t for t in own[n["id"]] if mentions(t, n["label"])] for n in candidates})
        dropped = []
        for i, node in enumerate(candidates, 1):
            verdict = verdicts.get(i)
            ai = node["origin"] == "ai"
            grounded = mentioned[node["id"]] or near.get(node["id"], False)
            if verdict is not None and verdict.people:
                self.db.update_node(node["id"], kind=NodeKind.target_group.value)
            elif verdict is not None and not verdict.proper_name:
                self.db.update_node(node["id"], kind=NodeKind.idea.value)
            elif not ai or grounded or (verdict is not None and verdict.serves_niche and searched[node["id"]]):
                continue
            else:
                self.db.delete_node(node["id"])
                dropped.append(node["label"])
        return dropped

    async def _near_niche(self, seed: str, texts: dict[int, list[str]]) -> dict[int, bool]:
        """Whether any of a node's own search suggestions is close to the niche in meaning."""
        flat = [(node_id, text) for node_id, items in texts.items() for text in items]
        if not flat or not callable(getattr(self.llm, "embed", None)):
            return {}
        try:
            vectors = await self.llm.embed([seed, *(text for _, text in flat)])
        except (OllamaError, httpx.HTTPError):
            return {}
        near: dict[int, bool] = {}
        for (node_id, _), vector in zip(flat, vectors[1:]):
            near[node_id] = near.get(node_id, False) or cosine(vectors[0], vector) >= RELEVANCE_HIGH
        return near

    def _reattach(self, project_id: int, focus: dict[str, Any]) -> None:
        anchor = self.db.get_node(focus["id"]) or self.db.root_node(project_id)
        linked = {i for e in self.db.list_edges(project_id) for i in (e["source_id"], e["target_id"])}
        for node in self.db.list_nodes(project_id):
            if not node["is_root"] and node["id"] not in linked:
                self.db.insert_edge(project_id, anchor["id"], node["id"], origin="ai")

    def _adopt_language(self, project: dict[str, Any], detected: str) -> dict[str, Any]:
        code = (detected or "").strip().lower()[:2]
        if not code.isalpha() or len(code) != 2 or code == project["language"]:
            return project
        geo = COUNTRY_FOR_LANGUAGE.get(code, project["geo"])
        return self.db.update_project(project["id"], language=code, geo=geo) or project

    def _apply_plan(
        self,
        project_id: int,
        focus: dict[str, Any],
        nodes: list[dict[str, Any]],
        plan: ExpansionPlan,
        count: int,
    ) -> list[dict[str, Any]]:
        by_label = {normalize_label(n["label"]): n for n in nodes}
        touched: dict[int, dict[str, Any]] = {}
        for verdict in plan.classified:
            node = by_label.get(normalize_label(verdict.label))
            if node and not node["is_root"] and not node["kind"]:
                query = " ".join(verdict.search_query.split())[:80] or None
                touched[node["id"]] = self.db.update_node(node["id"], kind=verdict.kind.value, search_query=query)
        for node in nodes:
            if not node["is_root"] and not node["kind"] and node["id"] not in touched:
                touched[node["id"]] = self.db.update_node(node["id"], kind=NodeKind.idea.value)

        created: list[tuple[dict[str, Any], ProposedNode]] = []
        for proposal in plan.new_nodes:
            key = normalize_label(proposal.label)
            if not key or key in by_label or key in FORMATS or len(created) >= count:
                continue
            node = self.db.insert_node(
                project_id,
                proposal.label,
                kind=proposal.kind.value,
                origin="ai",
                search_query=proposal.search_query or proposal.label,
            )
            by_label[key] = node
            created.append((node, proposal))
            touched[node["id"]] = node

        for node, proposal in created:
            linked = False
            for target in proposal.connects_to:
                other = by_label.get(normalize_label(target))
                if other and other["id"] != node["id"]:
                    linked = bool(self.db.insert_edge(project_id, other["id"], node["id"], origin="ai")) or linked
            if not linked:
                self.db.insert_edge(project_id, focus["id"], node["id"], origin="ai")

        root = self.db.root_node(project_id)
        if not root["enriched_at"]:
            touched[root["id"]] = root
        return list(touched.values())

    async def _enrich(
        self,
        project: dict[str, Any],
        nodes: list[dict[str, Any]],
        http: httpx.AsyncClient,
        progress: ProgressFn,
        warn: WarnFn,
    ) -> None:
        if not nodes:
            return
        language, geo = project["language"], project["geo"]
        bilingual = language != "en"
        queries = [n["search_query"] or n["label"] for n in nodes]
        english: list[str] = []
        if bilingual:
            progress(0.56, "translating")
            english = await translate(self.llm, queries, "English")
        limiter = asyncio.Semaphore(4)
        gathered: dict[int, dict[str, Any]] = {}
        done = 0

        async def lookup(query: str, hl: str, gl: str) -> tuple[list[str], list[dict] | None]:
            suggestions: list[str] = []
            posts: list[dict] | None = None
            try:
                suggestions = await self.collectors.simple_suggestions(self.db, http, query, hl, gl)
            except CollectorUnavailable as exc:
                warn(f"autocomplete: {exc}")
            try:
                posts = await self.collectors.community_search(self.db, http, query, hl)
            except CollectorUnavailable as exc:
                warn(f"community: {exc}")
            return suggestions, posts

        async def collect(index: int, node: dict[str, Any]) -> None:
            nonlocal done
            async with limiter:
                suggestions, posts = await lookup(queries[index], language, geo)
                entry: dict[str, Any] = {"suggestions": suggestions, "posts": posts, "en_suggestions": [], "en_posts": []}
                foreign = english[index] if bilingual and index < len(english) else ""
                if foreign and normalize_label(foreign) != normalize_label(queries[index]):
                    en_suggestions, en_posts = await lookup(foreign, "en", "")
                    entry["en_suggestions"] = en_suggestions[:6]
                    entry["en_posts"] = (en_posts or [])[:6]
            gathered[node["id"]] = entry
            done += 1
            progress(0.58 + 0.2 * done / len(nodes), "evidence")

        await asyncio.gather(*(collect(i, n) for i, n in enumerate(nodes)))

        progress(0.785, "screening")
        await self._screen(project["seed"], nodes, gathered, warn)

        if bilingual:
            progress(0.79, "translating")
            originals = [
                text
                for entry in gathered.values()
                for text in [*entry["en_suggestions"], *(p["title"] for p in entry["en_posts"])]
            ]
            unique = list(dict.fromkeys(originals))
            translated = dict(zip(unique, await translate(self.llm, unique, LANGUAGE_NAMES.get(language, language))))
        else:
            translated = {}

        progress(0.82, "trends")
        labels = [n["label"] for n in nodes]
        market_queries = await trend_queries(self.llm, labels, language)
        by_label = {label: {} for label in labels}
        for code, terms in market_queries.items():
            region = "PL" if code == "pl" else ""
            keywords = list(dict.fromkeys(term for term in terms if term))
            if not keywords:
                continue
            try:
                results = await self.collectors.trend_growth(self.db, keywords, region, code)
            except CollectorUnavailable as exc:
                warn(f"trends: {code}: {exc}")
                continue
            for label, term in zip(labels, terms):
                result = results.get(term)
                if result and result.get("series"):
                    by_label[label][code] = {**result, "query": term, "anchor": trends.anchor_for(code)}

        progress(0.94, "scoring")
        now = time.time()
        for node in nodes:
            entry = gathered.get(node["id"], {"suggestions": [], "posts": None, "en_suggestions": [], "en_posts": []})
            markets = by_label[node["label"]]
            primary = language if language in markets else next(iter(markets), None)
            trend = markets.get(primary)
            for rank, text in enumerate(entry["suggestions"][:10]):
                self.db.add_evidence(project["id"], node["id"], "autocomplete", text, weight=1 - rank / 10)
            for rank, text in enumerate(entry.get("en_suggestions", [])):
                self.db.add_evidence(
                    project["id"],
                    node["id"],
                    "autocomplete",
                    translated.get(text, text),
                    weight=0.5 - rank / 20,
                    meta={"lang": "en", "original": text},
                )
            local_posts = [(post, None) for post in (entry["posts"] or [])[:8]]
            foreign_posts = [(post, "en") for post in entry.get("en_posts", [])]
            for post, lang in [*local_posts, *foreign_posts]:
                meta = {
                    "platform": post.get("platform", "reddit"),
                    "place": post.get("place") or post.get("subreddit"),
                    "comments": post.get("comments", 0),
                    "published_at": post.get("created"),
                }
                if lang:
                    meta.update({"lang": lang, "original": post["title"]})
                self.db.add_evidence(
                    project["id"],
                    node["id"],
                    "community",
                    translated.get(post["title"], post["title"]) if lang else post["title"],
                    body=post.get("body", ""),
                    url=post.get("url"),
                    weight=float(post.get("score", 0) + post.get("comments", 0)),
                    meta=meta,
                )
            all_posts = None if entry["posts"] is None and not entry.get("en_posts") else [
                *(entry["posts"] or []),
                *entry.get("en_posts", []),
            ]
            fields: dict[str, Any] = {
                "score": score_node(len(entry["suggestions"]), all_posts, trend),
                "enriched_at": now,
            }
            if trend and trend.get("series"):
                fields["trend_growth"] = trend.get("growth")
                fields["trend_series"] = {
                    "dates": trend.get("dates", []),
                    "series": trend["series"],
                    "anchor": trend["anchor"],
                    "primary": primary,
                    "markets": markets,
                    "anchor_ratio": trend.get("anchor_ratio"),
                }
            for code, result in markets.items():
                growth = result.get("growth")
                if growth is not None:
                    self.db.add_evidence(
                        project["id"],
                        node["id"],
                        "trends",
                        f"{code.upper()} · {result['query']}: {growth:+.0%} (3m vs 9m)",
                        weight=growth,
                        meta={"lang": code, "anchor": result["anchor"], "anchor_ratio": result.get("anchor_ratio")},
                    )
            self.db.update_node(node["id"], **fields)
