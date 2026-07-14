"""Shared Pydantic models used across all PharmAgent modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievedDoc(BaseModel):
    """A single document chunk retrieved from a knowledge source."""

    content: str
    metadata: dict = Field(default_factory=dict)
    score: float = 0.0
    source_collection: str = ""


class GradedDoc(BaseModel):
    """A retrieved document with a relevance grade."""

    doc: RetrievedDoc
    is_relevant: bool = False
    reasoning: str = ""


class SafetyAssessment(BaseModel):
    """Structured safety assessment produced by the synthesis generator."""

    risk_level: str = Field(
        default="unknown",
        description="One of: low, moderate, high, critical, unknown",
    )
    summary: str = ""
    evidence: list[dict] = Field(default_factory=list)
    contraindications: list[str] = Field(default_factory=list)
    monitoring: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: float = 0.0
