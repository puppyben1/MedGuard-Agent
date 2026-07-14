"""LangGraph state for the MedGuard-Agent prescription review workflow."""

from __future__ import annotations

from typing import TypedDict

from pharmagent.core.schemas import GradedDoc, RetrievedDoc
from pharmagent.prescription.schemas import (
    PatientCase,
    PrescriptionFinding,
    PrescriptionReport,
    VerificationResult,
)


class PrescriptionState(TypedDict, total=False):
    """State flowing through the prescription review graph.

    Lifecycle:
      case_text ──► patient_case ──► sub_queries ──► retrieved_docs
        ──► graded_docs ──► findings ──► verifications ──► report
    """

    # Input
    case_text: str
    collections: list[str]   # default: all three knowledge bases

    # Parse
    patient_case: PatientCase

    # Query planning
    sub_queries: list[str]

    # Retrieval + grading
    retrieved_docs: list[RetrievedDoc]
    graded_docs: list[GradedDoc]

    # Risk findings + verification
    findings: list[PrescriptionFinding]
    verifications: list[VerificationResult]

    # Output
    report: PrescriptionReport

    # Error tracking
    error: str | None
