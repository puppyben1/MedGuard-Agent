"""Pydantic schemas for the prescription review workflow.

These models extend the original SafetyAssessment with structured patient
case information and granular prescription findings, so the agent can
produce a clinically usable prescription-review report instead of a free
text safety summary.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── Enumerations (kept as Literal strings for JSON-friendliness) ────

FindingType = Literal[
    "drug_interaction",       # drug-drug interaction
    "contraindication",       # absolute contraindication
    "dose_risk",              # dose too high / too low for the patient
    "renal_risk",             # nephrotoxicity / needs renal dose adjust
    "hepatic_risk",           # hepatotoxicity / needs hepatic dose adjust
    "pregnancy_risk",         # teratogenicity / lactation risk
    "allergy_risk",           # known allergy cross-reactivity
    "monitoring_required",    # requires lab / INR / vitals monitoring
    "missing_evidence",       # could not verify — flag for pharmacist
]

Severity = Literal["low", "moderate", "high", "critical"]

HepaticFunction = Literal["normal", "mild", "moderate", "severe", "unknown"]


# ── Patient case ────────────────────────────────────────────────────

class DrugOrder(BaseModel):
    """A single drug as it appears on the prescription."""

    name: str = Field(description="Generic drug name, e.g. 'metformin'")
    dose: str = Field(default="", description="Dose string, e.g. '500 mg'")
    route: str = Field(default="oral", description="Route, e.g. 'oral', 'IV'")
    frequency: str = Field(default="", description="Frequency, e.g. 'BID', 'twice daily'")
    notes: str = Field(default="", description="Free-text notes / PRN instructions")


class PatientCase(BaseModel):
    """Structured representation of a clinical case under review."""

    age: int | None = Field(default=None, description="Patient age in years")
    sex: Literal["male", "female", "unknown"] = "unknown"
    weight_kg: float | None = None
    height_cm: float | None = None

    # Clinical context
    diagnoses: list[str] = Field(default_factory=list, description="Active diagnoses, e.g. ['T2DM', 'CKD stage 3']")
    allergies: list[str] = Field(default_factory=list, description="Known drug allergies")
    pregnancy: bool | None = Field(default=None, description="True if pregnant; None if not applicable / unknown")
    lactating: bool | None = Field(default=None)

    # Organ function — critical for dosing
    egfr: float | None = Field(default=None, description="Estimated GFR in mL/min/1.73m^2")
    liver_function: HepaticFunction = "unknown"
    inr: float | None = Field(default=None, description="Latest INR if on anticoagulation")

    # Prescription
    drugs: list[DrugOrder] = Field(default_factory=list)

    # Parser metadata
    raw_text: str = Field(default="", description="Original case text, kept for traceability")
    parse_confidence: float = Field(default=0.0, description="0-1 confidence in the parse")


# ── Prescription finding ────────────────────────────────────────────

class PrescriptionFinding(BaseModel):
    """A single risk finding produced by the prescription checker."""

    finding_type: FindingType
    severity: Severity
    drugs_involved: list[str] = Field(default_factory=list)
    description: str = Field(description="What the risk is, in 1-2 sentences")
    recommendation: str = Field(default="", description="Suggested clinical action")
    evidence_doc_ids: list[str] = Field(
        default_factory=list,
        description="IDs of retrieved docs that support this finding",
    )
    verified: bool = Field(
        default=False,
        description="True once the evidence_verifier confirms a supporting source",
    )
    verification_reason: str = Field(default="", description="Why verified / not verified")


# ── Evidence verification ───────────────────────────────────────────

class VerificationResult(BaseModel):
    """Result of verifying a single finding against retrieved evidence."""

    finding_index: int
    verified: bool
    supporting_doc_ids: list[str] = Field(default_factory=list)
    reason: str = ""


# ── Final report ────────────────────────────────────────────────────

class PrescriptionReport(BaseModel):
    """Final structured prescription-review report."""

    patient_case: PatientCase
    findings: list[PrescriptionFinding] = Field(default_factory=list)

    overall_risk_level: Severity = "low"
    summary: str = ""

    # Evidence quality metrics
    evidence_coverage: float = Field(
        default=0.0,
        description="Fraction of findings with at least one supporting doc",
    )
    unverified_findings_count: int = 0
    hallucination_flagged: bool = Field(
        default=False,
        description="True if any high/critical finding lacks evidence",
    )

    # Traceability
    citations: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    # Performance
    elapsed_seconds: float = 0.0
