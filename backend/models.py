"""Pydantic models for LLM structured outputs and the HTTP API."""

from __future__ import annotations

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
    stage: Literal["compose", "expanding", "select", "problems", "personas", "done"] | None = None
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
