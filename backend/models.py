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

    @field_validator("label")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _clean_label(value)


class ProposedNode(BaseModel):
    """A new node suggested by the model."""

    label: str = Field(description="1-3 word label in the niche's language")
    kind: NodeKind
    connects_to: list[str] = Field(description="Exact labels of nodes this one relates to")
    search_query: str = Field(description="2-5 word web search phrase that surfaces real user discussions")

    @field_validator("label")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _clean_label(value)

    @field_validator("search_query")
    @classmethod
    def _query(cls, value: str) -> str:
        return " ".join(value.replace("_", " ").split())[:80]


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
    stage: Literal["compose", "expanding", "select", "problems", "personas", "done", "board", "flow"] | None = None
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


def _sentence(value: str, limit: int) -> str:
    text = " ".join(value.replace("_", " ").split()).strip().strip('"\u201e\u201d')
    return text if len(text) <= limit else text[: limit - 1].rstrip(" ,.;") + "…"


class ProblemDraft(BaseModel):
    """One problem statement synthesised from Discover evidence."""

    title: str = Field(description="Problem stated from the user's perspective, 4-7 words, sentence case")
    description: str = Field(description="One short sentence (max 12 words) explaining why it happens")
    trend_keyword: str = Field(description="1-3 word everyday Google query people type when they have this problem")
    quote_id: int = Field(description="Id of the evidence line that best illustrates the problem, 0 if none fits")
    node_labels: list[str] = Field(description="Exact labels of the map nodes this problem is grounded in")

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        text = _sentence(value, 70).rstrip(".")
        return text[:1].upper() + text[1:]

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _sentence(value, 140)

    @field_validator("trend_keyword")
    @classmethod
    def _keyword(cls, value: str) -> str:
        return " ".join(value.lower().replace("_", " ").split()[:4])[:60]


class ProblemSet(BaseModel):
    """Structured answer with exactly three competing problem statements."""

    problems: list[ProblemDraft] = Field(json_schema_extra={"minItems": 3, "maxItems": 3})


class PersonaDraft(BaseModel):
    """A conceptual persona affected by the chosen problem."""

    name: str = Field(description="Typical first name in the project's language")
    age: int = Field(description="Age in years between 16 and 75")
    role: str = Field(description="Life situation or job in 2-4 words, sentence case, no names or parentheses")
    quote: str = Field(description="What the persona would say about the problem, first person, 1-2 short sentences")
    problems: list[str] = Field(
        description="Two concrete sub-problems this persona faces, each 3-7 words",
        json_schema_extra={"minItems": 2, "maxItems": 2},
    )

    @field_validator("name", "role")
    @classmethod
    def _short(cls, value: str) -> str:
        text = _sentence(value, 48)
        return text[:1].upper() + text[1:]

    @field_validator("quote")
    @classmethod
    def _quote(cls, value: str) -> str:
        return _sentence(value, 160)

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
