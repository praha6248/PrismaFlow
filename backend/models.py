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
    new_nodes: list[ProposedNode] = Field(default_factory=list)


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
    stage: Literal["compose", "expanding", "select"] | None = None


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
