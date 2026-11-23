"""Pydantic models for LLM structured outputs and the HTTP API."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class NodeKind(str, Enum):
    """Semantic category of a mind-map node proposed by the model."""

    idea = "idea"
    target_group = "target_group"
    pain_point = "pain_point"
    competitor = "competitor"


def _clean_label(value: str) -> str:
    text = " ".join(value.replace("_", " ").replace("#", " ").split()).strip(" .,:;-\"'")
    return text[:48]


class ClassifiedNode(BaseModel):
    """Model verdict for a node that the user typed in without a category."""

    label: str
    kind: NodeKind
    search_query: str = Field(default="", description="2-5 word web search phrase joining the node with the niche")

    @field_validator("label")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _clean_label(value)


class ProposedNode(BaseModel):
    """A new node suggested by the model."""

    label: str = Field(description="1-3 word label in the niche's language")
    kind: NodeKind
    connects_to: list[str] = Field(description="Exact labels of nodes this one relates to")
    search_query: str = Field(description="2-5 word web search phrase joining the node with the niche")

    @field_validator("label")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _clean_label(value)

    @field_validator("search_query")
    @classmethod
    def _query(cls, value: str) -> str:
        return " ".join(value.replace("_", " ").split())[:80]


class CompetitorVerdict(BaseModel):
    """Plain facts about one competitor name, judged by the model."""

    number: int
    name: str = ""
    proper_name: bool = Field(
        description="true only for the proper name of one specific company, app or website (Spotify, OLX, Duolingo); "
        "false for common nouns such as libraries, physiotherapist, rehabilitation program, coffee shops"
    )
    serves_niche: bool = Field(description="true when people use it for the same need as the niche")
    people: bool = Field(description="true when the name describes people (a profession or a group)")


class CompetitorCheck(BaseModel):
    """Verdicts for the competitor nodes of one expansion."""

    items: list[CompetitorVerdict] = Field(default_factory=list)


class RelevantItems(BaseModel):
    """Numbers of the search results that are real evidence for the niche."""

    relevant: list[int] = Field(default_factory=list)


class ExpansionPlan(BaseModel):
    """Structured answer returned by the model when expanding the mind map."""

    language: str = Field(default="", description="ISO 639-1 code of the language the user's labels are written in")
    classified: list[ClassifiedNode] = Field(default_factory=list)
    new_nodes: list[ProposedNode] = Field(default_factory=list, json_schema_extra={"minItems": 1, "maxItems": 8})


class ProjectCreate(BaseModel):
    """Request body for starting a new project from a seed niche."""

    seed: str = Field(min_length=1, max_length=80)

    @field_validator("seed")
    @classmethod
    def _seed(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("seed must not be blank")
        return cleaned


class ProjectUpdate(BaseModel):
    """Request body for updating project metadata."""

    name: str | None = None
    stage: Literal["compose", "expanding", "select", "problems", "personas", "validate", "done", "board", "flow"] | None = None
    phase: Literal["discover", "define", "develop", "deliver"] | None = None


class NodeCreate(BaseModel):
    """Request body for manually adding a node."""

    label: str = Field(min_length=1, max_length=48)
    connect_to: int | None = None
    x: float | None = None
    y: float | None = None

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("label must not be blank")
        return cleaned


class NodeUpdate(BaseModel):
    """Request body for editing a node."""

    label: str | None = None
    starred: bool | None = None
    x: float | None = None
    y: float | None = None


class PositionUpdate(BaseModel):
    """One node coordinate pair."""

    id: int
    x: float
    y: float


class PositionsUpdate(BaseModel):
    """Batch of node coordinates."""

    positions: list[PositionUpdate]


class ExpandRequest(BaseModel):
    """Request body for AI expansion of the mind map."""

    project_id: int
    node_id: int | None = None
    count: int = Field(default=3, ge=1, le=8)


class Job(BaseModel):
    """Progress snapshot of a long-running background task."""

    id: str
    kind: str
    status: Literal["running", "done", "error"] = "running"
    progress: float = 0.0
    stage: str = "queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


def _sentence(value: str, limit: int | None = None) -> str:
    text = " ".join(value.replace("_", " ").split()).strip().strip('"\u201e\u201d')
    return text if limit is None or len(text) <= limit else text[: limit - 1].rstrip(" ,.;") + "…"


class ProblemDraft(BaseModel):
    """One problem statement synthesised from Discover evidence."""

    title: str = Field(description="Problem stated from the user's perspective, 4-7 words, sentence case")
    description: str = Field(description="One short sentence (max 12 words) explaining why it happens")
    trend_keyword: str = Field(description="1-3 word everyday Google query people type when they have this problem")
    quote_id: int = Field(description="Id of the evidence line that best illustrates the problem, 0 if none fits")
    evidence_ids: list[int] = Field(default_factory=list, description="Ids of 2-5 evidence lines showing that people really have this problem")
    node_labels: list[str] = Field(description="Exact labels of the map nodes this problem is grounded in")

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        text = _sentence(value).rstrip(".")
        return text[:1].upper() + text[1:]

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _sentence(value)

    @field_validator("trend_keyword")
    @classmethod
    def _keyword(cls, value: str) -> str:
        return " ".join(value.lower().replace("_", " ").split()[:4])[:60]


class ProblemSet(BaseModel):
    """Structured answer with exactly three competing problem statements."""

    problems: list[ProblemDraft] = Field(json_schema_extra={"minItems": 3, "maxItems": 3})


class PersonaProfile(BaseModel):
    """Research hypotheses to validate in interviews or observation."""

    situation: str = Field(min_length=1, description="Where and when usage starts, and what triggers it")
    device: str = Field(min_length=1, description="Device and environmental or accessibility constraints")
    goal: str = Field(min_length=1, description="The practical outcome sought in this situation")
    workaround: str = Field(min_length=1, description="How the person handles the task today")
    barrier: str = Field(min_length=1, description="A concrete obstacle or concern")
    success: str = Field(min_length=1, description="Observable sign that the task was completed successfully")
    question: str = Field(min_length=1, description="One open interview question about the last real occurrence")


class PersonaDraft(BaseModel):
    """A conceptual persona affected by the chosen problem."""

    profile: PersonaProfile
    name: str = Field(description="Typical first name in the project's language")
    age: int = Field(description="Age in years between 16 and 75")
    role: str = Field(description="Life situation or job in 2-4 words, sentence case, no names or parentheses")
    quote: str = Field(description="What the persona would say about the problem, first person, 1-2 short sentences")
    problems: list[str] = Field(
        description="Two concrete sub-problems this persona faces, each 3-7 words",
        json_schema_extra={"minItems": 2, "maxItems": 2},
    )
    evidence_ids: list[int] = Field(default_factory=list, description="Ids of 1-4 evidence lines this persona's situation and quote are based on")

    @field_validator("name", "role")
    @classmethod
    def _short(cls, value: str) -> str:
        text = _sentence(value, 48)
        return text[:1].upper() + text[1:]

    @field_validator("quote")
    @classmethod
    def _quote(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("age")
    @classmethod
    def _age(cls, value: int) -> int:
        return max(16, min(75, value))

    @field_validator("problems")
    @classmethod
    def _problems(cls, value: list[str]) -> list[str]:
        items = [_sentence(v, 60).rstrip(".") for v in value if v.strip()]
        return [i[:1].upper() + i[1:] for i in items][:2]


class PersonaSet(BaseModel):
    """Structured answer with exactly three personas."""

    personas: list[PersonaDraft] = Field(json_schema_extra={"minItems": 3, "maxItems": 3})


class DefineRequest(BaseModel):
    """Request body for generating problem statements or personas."""

    project_id: int


class PersonaChoice(BaseModel):
    """Request body for picking a persona's main problem."""

    option: int = Field(ge=0, le=1)


Priority = Literal["must", "should", "could", "wont"]


class FeatureDraft(BaseModel):
    """A product feature proposed for the chosen persona and problem."""

    title: str = Field(description="Feature name in 2-4 words, sentence case")
    description: str = Field(description="Benefit for the persona as a phrase of 3-8 words")
    priority: Priority = Field(description="MoSCoW priority for the first version")
    keywords: list[str] = Field(
        description="1-4 single words, in the project's language, that people use when they need this feature",
        json_schema_extra={"minItems": 1, "maxItems": 4},
    )
    evidence_ids: list[int] = Field(description="Ids of evidence lines that support the feature; empty when none")
    impact: float = Field(default=1, description="RICE impact on the persona: 0.25 minimal, 0.5 low, 1 medium, 2 high, 3 massive")
    effort: float = Field(default=2, description="RICE effort in person-weeks for the first version, 0.5 to 8")

    @field_validator("impact")
    @classmethod
    def _impact(cls, value: float) -> float:
        return min((0.25, 0.5, 1.0, 2.0, 3.0), key=lambda level: abs(level - value))

    @field_validator("effort")
    @classmethod
    def _effort(cls, value: float) -> float:
        return round(max(0.5, min(8.0, value)) * 2) / 2

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        text = _sentence(value, 48).rstrip(".")
        return text[:1].upper() + text[1:]

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        first = re.split(r"(?<=[.!?])\s", value.strip(), maxsplit=1)[0]
        text = _sentence(first, 90).rstrip(".")
        return text[:1].upper() + text[1:]

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, value: list[str]) -> list[str]:
        words = [" ".join(v.lower().split())[:30] for v in value if v.strip()]
        return list(dict.fromkeys(words))[:4]


class FeatureSet(BaseModel):
    """Structured answer with the proposed feature backlog."""

    features: list[FeatureDraft] = Field(json_schema_extra={"minItems": 6, "maxItems": 9})


class FeatureCreate(BaseModel):
    """Request body for a feature written by the user."""

    title: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=140)
    priority: Priority = "should"

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, value: str) -> str:
        return " ".join(value.split())


class FeatureUpdate(BaseModel):
    """Partial update of a feature card."""

    title: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=140)
    priority: Priority | None = None
    impact: Literal[0.25, 0.5, 1, 2, 3] | None = None
    effort: float | None = Field(default=None, ge=0.5, le=8)


class FeatureOrderItem(BaseModel):
    """One card's place on the MoSCoW board."""

    id: int
    priority: Priority
    position: int = Field(ge=0)


class FeatureOrder(BaseModel):
    """Board state sent after a drag and drop."""

    items: list[FeatureOrderItem]


ElementType = Literal["button", "link", "select", "input", "toggle", "list"]
ElementSize = Literal["S", "M", "L"]
ElementZone = Literal["top", "center", "bottom"]
ScreenKind = Literal["start", "step", "goal"]


class FlowElement(BaseModel):
    """An interactive element placed on a screen; a target turns it into a transition."""

    id: str = Field(min_length=1, max_length=24)
    label: str = Field(min_length=1, max_length=60)
    type: ElementType = "button"
    size: ElementSize = "M"
    zone: ElementZone = "center"
    options: int = Field(default=1, ge=1, le=50)
    target: str | None = None


class FlowScreen(BaseModel):
    """A screen node of the user flow."""

    id: str = Field(min_length=1, max_length=24)
    name: str = Field(min_length=1, max_length=60)
    kind: ScreenKind = "step"
    x: float = 0
    y: float = 0
    feature_ids: list[int] = Field(default_factory=list)
    elements: list[FlowElement] = Field(default_factory=list)


class Flow(BaseModel):
    """The whole user flow document edited in the Deliver studio."""

    screens: list[FlowScreen] = Field(default_factory=list)


class FlowUpdate(BaseModel):
    """Request body carrying the edited flow."""

    flow: Flow


class ElementDraft(BaseModel):
    """An element proposed by the model."""

    label: str = Field(description="Short visible label in 1-3 words")
    type: ElementType = Field(description="UI control type")
    size: ElementSize = Field(description="L for the primary action, M for secondary, S for minor links")
    zone: ElementZone = Field(description="Where on a phone screen: bottom (thumb zone), center or top")
    options: int = Field(description="Alternatives inside this one control: 1 for buttons, links and inputs; the visible items or filters for a list or select")
    target: str = Field(description="Exact name of the screen this element opens, or an empty string")

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        text = _sentence(value, 40).rstrip(".!:?…").strip()
        return text[:1].upper() + text[1:]

    @field_validator("options")
    @classmethod
    def _options(cls, value: int) -> int:
        return max(1, min(20, value))


class ScreenDraft(BaseModel):
    """A screen proposed by the model."""

    name: str = Field(description="Screen name in 1-3 words")
    kind: ScreenKind = Field(description="start for the entry screen, goal for the screen where the persona reaches value")
    features: list[str] = Field(description="Titles of the backlog features shown on this screen")
    elements: list[ElementDraft] = Field(json_schema_extra={"minItems": 1, "maxItems": 6})

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        text = _sentence(value, 40).rstrip(".")
        return text[:1].upper() + text[1:]


class FlowDraft(BaseModel):
    """Structured answer with a first user flow."""

    screens: list[ScreenDraft] = Field(json_schema_extra={"minItems": 3, "maxItems": 6})


SuggestionOp = Literal["resize", "move_zone", "group_options", "add_transition", "remove_element"]


class SuggestionDraft(BaseModel):
    """An optimisation the model proposes for the flow."""

    title: str = Field(description="Imperative advice in at most 8 words")
    reason: str = Field(description="Which audit finding it fixes, at most 12 words")
    op: SuggestionOp
    screen: str = Field(description="Exact name of the screen to change")
    element: str = Field(description="Exact label of the element to change, or the new element label for add_transition")
    value: str = Field(description="New size S/M/L for resize, zone top/center/bottom for move_zone, target screen name for add_transition, otherwise empty")

    @field_validator("title", "reason")
    @classmethod
    def _text(cls, value: str) -> str:
        text = _sentence(value, 110).rstrip(".")
        return text[:1].upper() + text[1:]


class SuggestionSet(BaseModel):
    """Structured answer with flow optimisations."""

    suggestions: list[SuggestionDraft] = Field(json_schema_extra={"minItems": 1, "maxItems": 4})


HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
StyleFont = Literal[
    "Inter",
    "Manrope",
    "DM Sans",
    "Nunito",
    "Poppins",
    "Work Sans",
    "Source Sans 3",
    "IBM Plex Sans",
    "Rubik",
    "Lora",
    "Merriweather",
    "Playfair Display",
    "Fraunces",
    "Space Grotesk",
    "Outfit",
]


class StyleDraft(BaseModel):
    """A visual direction for the product being designed, chosen for its persona and niche."""

    mood: list[str] = Field(description="Three adjectives describing the product's look and feel", json_schema_extra={"minItems": 3, "maxItems": 3})
    rationale: str = Field(description="Why this style fits the persona, at most 20 words")
    background: str = Field(description="Page background colour as #RRGGBB")
    surface: str = Field(description="Card and sheet colour as #RRGGBB")
    primary: str = Field(description="Primary action colour as #RRGGBB")
    text: str = Field(description="Body text colour as #RRGGBB")
    heading_font: StyleFont
    body_font: StyleFont
    corners: Literal["sharp", "soft", "round"] = Field(description="Corner style: sharp 4 px, soft 12 px, round 24 px")

    @field_validator("mood")
    @classmethod
    def _mood(cls, value: list[str]) -> list[str]:
        words = [" ".join(re.sub(r"[^\w\s-]", "", item).split()[:2]).casefold() for item in value]
        return [w for w in words if w][:3]

    @field_validator("rationale")
    @classmethod
    def _rationale(cls, value: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(value.replace("*", "").replace("_", " ").split()))
        text = sentences[0]
        if len(sentences) > 1 and len(text) + len(sentences[1]) < 200:
            text += " " + sentences[1]
        return text if len(text) <= 220 else text[:219].rsplit(" ", 1)[0] + "…"

    @field_validator("background", "surface", "primary", "text")
    @classmethod
    def _hex(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("#"):
            value = "#" + value
        if not HEX_COLOR.match(value):
            raise ValueError("expected a #RRGGBB colour")
        return value.upper()


class QualityUpdate(BaseModel):
    """Select a generation provider or update its private key."""

    provider: Literal["local", "claude", "gemini"] | None = None

    enabled: bool | None = None
    key: str | None = Field(default=None, max_length=2048)


HypothesisKind = Literal["problem", "frequency", "workaround", "willingness"]


class HypothesisDraft(BaseModel):
    """A falsifiable assumption behind the chosen problem and persona."""

    kind: HypothesisKind = Field(description="problem: the pain exists; frequency: it happens often; workaround: what people do today; willingness: they would pay or switch")
    text: str = Field(description="The assumption about the segment as a short, falsifiable statement, at most 15 words")
    signal: str = Field(description="A past fact the interviewee reports that confirms it, at most 15 words")

    @field_validator("text", "signal")
    @classmethod
    def _short(cls, value: str) -> str:
        return _sentence(value, 180)


class ValidationPlanDraft(BaseModel):
    """Hypotheses plus a Mom Test interview script for the chosen problem."""

    hypotheses: list[HypothesisDraft] = Field(json_schema_extra={"minItems": 3, "maxItems": 5})
    screener: list[str] = Field(description="3 short questions to check that a candidate really belongs to the persona", json_schema_extra={"minItems": 3, "maxItems": 3})
    questions: list[str] = Field(
        description="6-8 Mom Test interview questions about past behaviour and real situations; no hypothetical, leading or future questions, never pitch the idea",
        json_schema_extra={"minItems": 6, "maxItems": 8},
    )

    @field_validator("screener", "questions")
    @classmethod
    def _questions(cls, value: list[str]) -> list[str]:
        return [_sentence(v, 200) for v in value if v.strip()]


Verdict = Literal["supports", "contradicts", "no_data"]


class HypothesisVerdict(BaseModel):
    """How one interview bears on one hypothesis."""

    hypothesis: int = Field(description="Number of the hypothesis, starting at 1")
    verdict: Verdict
    quote: str = Field(description="Exact words copied from the notes that justify the verdict; empty when no_data")


class InterviewAnalysis(BaseModel):
    """Verdicts of one interview for every hypothesis."""

    verdicts: list[HypothesisVerdict]
    summary: str = Field(description="One sentence with the most important thing learnt, at most 25 words")

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str) -> str:
        first = re.split(r"(?<=[.!?])\s+", " ".join(value.split()))[0]
        return _sentence(first, 220)


class InterviewCreate(BaseModel):
    """Request body for logging an interview."""

    person: str = Field(min_length=1, max_length=80)
    notes: str = Field(min_length=20, max_length=20000)


class ThemeDraft(BaseModel):
    """A theme on the affinity board grouping related notes."""

    name: str = Field(description="Theme name in 2-5 words, sentence case")
    insight: str = Field(description="One-sentence insight the notes in this theme reveal")
    notes: list[int] = Field(description="Numbers of the notes that belong to this theme")

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _sentence(value, 60).rstrip(".")


class AffinityDraft(BaseModel):
    """Themes proposed by the model for the affinity board."""

    themes: list[ThemeDraft] = Field(json_schema_extra={"minItems": 2, "maxItems": 6})
    off_topic: list[int] = Field(
        default_factory=list, description="Numbers of web notes that have nothing to do with the niche"
    )


class BoardNoteCreate(BaseModel):
    """Notes pasted by the user; blank lines separate notes."""

    text: str = Field(min_length=1, max_length=20_000)
    source: Literal["note", "interview", "test"] = "note"
    label: str = Field(default="", max_length=80)
    theme: str | None = None


class BoardNoteUpdate(BaseModel):
    """Move a note to a theme, or out of all themes with an empty value."""

    theme: str | None = None


class ThemeUpdate(BaseModel):
    """Rename a theme or change its insight."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    insight: str | None = Field(default=None, max_length=240)


BREAKS = re.compile(r",|;|:|\s[–—-]\s|\s(?:i|a|ale|bo|więc|że|and|but|so|because)\s", re.IGNORECASE)


def short_phrase(value: str, limit: int = 14) -> str:
    """Keep one short phrase: the first sentence, cut at a natural break when it runs past the word limit."""
    text = " ".join(value.split()).strip()
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].rstrip(".")
    words = first.split()
    if len(words) <= limit:
        return first
    head = " ".join(words[:limit])
    cuts = [m.start() for m in BREAKS.finditer(head) if len(head[: m.start()].split()) >= max(3, limit // 2)]
    return head[: cuts[-1]].rstrip(" ,;:") if cuts else head.rstrip(" ,;:") + "…"


class EmpathyItem(BaseModel):
    """One observation in a quadrant of the empathy map."""

    text: str = Field(description="Short observation, 4-14 words")
    note: int = Field(default=0, description="Number of the note it comes from, or 0 when inferred")


class JourneyStageDraft(BaseModel):
    """A stage of the user journey."""

    phase: Literal["before", "during", "after"]
    name: str = Field(description="Stage name in 1-3 words")
    action: str = Field(description="What the persona does, 4-12 words")
    thought: str = Field(description="What the persona thinks, first person, 4-12 words")
    emotion: int = Field(description="Emotion from -2 (frustrated) to 2 (delighted)")
    pain: str = Field(default="", description="Frustration at this stage, 3-10 words, or empty")
    note: int = Field(default=0, description="Number of the note it comes from, or 0 when inferred")

    @field_validator("emotion")
    @classmethod
    def _emotion(cls, value: int) -> int:
        return max(-2, min(2, value))


class EmpathyDraft(BaseModel):
    """Empathy map, journey and How Might We questions for the chosen persona."""

    says: list[EmpathyItem] = Field(json_schema_extra={"minItems": 2, "maxItems": 4})
    thinks: list[EmpathyItem] = Field(json_schema_extra={"minItems": 2, "maxItems": 4})
    does: list[EmpathyItem] = Field(json_schema_extra={"minItems": 2, "maxItems": 4})
    feels: list[EmpathyItem] = Field(json_schema_extra={"minItems": 2, "maxItems": 4})
    journey: list[JourneyStageDraft] = Field(json_schema_extra={"minItems": 5, "maxItems": 7})
    hmw: list[str] = Field(
        description="Three 'How might we...' questions, each built on a journey frustration",
        json_schema_extra={"minItems": 3, "maxItems": 3},
    )


class ShortTexts(BaseModel):
    """Shortened versions of numbered texts, in the same order."""

    items: list[str]


class HmwUpdate(BaseModel):
    """Choose or rewrite the How Might We question."""

    text: str = Field(min_length=5, max_length=200)


class RiceDraft(BaseModel):
    """Impact and effort estimates for one feature."""

    feature: int = Field(description="Number of the feature")
    impact: float = Field(description="Impact on the persona: 0.25, 0.5, 1, 2 or 3")
    effort: float = Field(description="Effort in person-weeks, 0.5 to 8")


class RiceSet(BaseModel):
    """Impact and effort estimates for the backlog."""

    estimates: list[RiceDraft]


class TaskDraft(BaseModel):
    """A usability test task written for a participant."""

    goal: str = Field(description="Id of the goal screen")
    scenario: str = Field(description="Realistic scenario for the participant, second person, 10-30 words, no UI words")


class TaskSet(BaseModel):
    """Usability test tasks."""

    tasks: list[TaskDraft]


class TestTaskUpdate(BaseModel):
    """Edit a usability task's scenario."""

    scenario: str = Field(min_length=5, max_length=300)


class Misclick(BaseModel):
    """A tap on an element that leads nowhere."""

    screen: str
    element: str


class TestResult(BaseModel):
    """One participant's attempt at one task."""

    task: str
    success: bool
    seconds: float = Field(ge=0, le=3600)
    path: list[str] = Field(default_factory=list, max_length=200)
    misclicks: list[Misclick] = Field(default_factory=list, max_length=200)
    quote: str = Field(default="", max_length=600)


class TestSessionCreate(BaseModel):
    """A usability test session with one participant."""

    participant: str = Field(min_length=1, max_length=60)
    results: list[TestResult] = Field(min_length=1, max_length=20)


class Finding(BaseModel):
    """Send a test observation back to Define or Develop."""

    text: str = Field(min_length=3, max_length=600)
    target: Literal["board", "backlog"]


def _paragraph(value: str) -> str:
    text = " ".join(re.sub(r"[*#`>_]", " ", value).split()).strip()
    if len(text) <= 600:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = ""
    for sentence in sentences:
        if len(kept) + len(sentence) + 1 > 600:
            break
        kept = f"{kept} {sentence}".strip()
    return kept or text[:599].rsplit(" ", 1)[0].rstrip(" ,;") + "…"


class CaseStudyDraft(BaseModel):
    """Narrative paragraphs of a UX case study, written only from the project's fact sheet."""

    headline: str = Field(description="Case study title, at most 10 words, naming the product and the persona's job")
    summary: str = Field(description="2-3 sentences: the problem, what was designed and what the tests showed")
    context: str = Field(description="1-2 sentences on why the problem matters to the persona")
    research: str = Field(description="1-2 sentences on what the research methods revealed")
    synthesis: str = Field(description="1-2 sentences connecting the themes, persona and the chosen How might we")
    ideation: str = Field(description="1-2 sentences on how features were prioritised")
    design: str = Field(description="1-2 sentences on the flow and what the audit found")
    testing: str = Field(description="1-2 sentences on what the usability tests showed")
    reflection: str = Field(description="2-3 sentences: lessons and next steps that follow from the test issues and the gaps")

    @field_validator("headline")
    @classmethod
    def _headline(cls, value: str) -> str:
        return _sentence(_paragraph(value), 90).rstrip(".")

    @field_validator("summary", "context", "research", "synthesis", "ideation", "design", "testing", "reflection")
    @classmethod
    def _text(cls, value: str) -> str:
        return _paragraph(value)
