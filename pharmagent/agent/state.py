"""LangGraph agent state definition."""

from __future__ import annotations

from typing import TypedDict

from pharmagent.core.schemas import GradedDoc, RetrievedDoc, SafetyAssessment


class AgentState(TypedDict, total=False):
    """State flowing through the PharmAgent LangGraph."""

    # Input
    query: str

    # Router output
    query_type: str  # "single_drug", "multi_drug_interaction", "patient_specific"
    target_collections: list[str]

    # Drug coverage
    detected_drugs: list[str]  # drugs found in the index
    missing_drugs: list[str]   # drugs mentioned but NOT in the index

    # Retrieval
    retrieved_docs: list[RetrievedDoc]

    # Grading
    graded_docs: list[GradedDoc]

    # Rewriting
    rewrite_count: int
    current_query: str  # may differ from original after rewrites

    # Generation
    assessment: SafetyAssessment | None
    generation_count: int

    # Hallucination checking
    hallucination_passed: bool
    faithfulness_score: float
    hallucination_feedback: str

    # Error tracking
    error: str | None
