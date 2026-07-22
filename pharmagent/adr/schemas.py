"""Schemas for the ADR end-to-end analysis workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "moderate", "high", "critical"]
SignalLevel = Literal["none", "weak", "moderate", "strong"]
SourceMode = Literal["local_demo", "realtime_openfda", "mixed", "fallback_demo"]


class ADRExample(BaseModel):
    id: str
    label: str
    drug: str
    adr: str
    case_text: str


class SuspectedDrug(BaseModel):
    name: str
    role: Literal["primary_suspect", "concomitant", "interacting"] = "primary_suspect"
    evidence_text: str = ""


class AdverseEvent(BaseModel):
    name: str
    original_text: str = ""
    severity: Severity = "moderate"
    evidence_text: str = ""


class TimelineEvent(BaseModel):
    event_type: Literal[
        "drug_start",
        "concomitant_drug_start",
        "adr_onset",
        "lab_abnormality",
        "dechallenge",
        "outcome",
    ]
    label: str
    time_text: str = ""
    description: str = ""
    risk_relevance: str = ""


class ChallengeInfo(BaseModel):
    available: bool = False
    result: Literal["improved", "worsened", "unchanged", "positive", "negative", "unknown"] = "unknown"
    evidence_text: str = ""


class ADRExtractionResult(BaseModel):
    suspected_drugs: list[SuspectedDrug] = Field(default_factory=list)
    adverse_events: list[AdverseEvent] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    dechallenge: ChallengeInfo = Field(default_factory=ChallengeInfo)
    rechallenge: ChallengeInfo = Field(default_factory=ChallengeInfo)
    concomitant_drugs: list[str] = Field(default_factory=list)
    objective_evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    extraction_confidence: float = 0.0


class TrendPoint(BaseModel):
    year: int
    reports: int


class DistributionPoint(BaseModel):
    label: str
    count: int


class OpenFDASignal(BaseModel):
    drug: str
    adr: str
    source_mode: SourceMode = "local_demo"
    report_count: int = 0
    serious_count: int = 0
    death_count: int = 0
    hospitalization_count: int = 0
    ror: float | None = None
    prr: float | None = None
    signal_level: SignalLevel = "none"
    yearly_trend: list[TrendPoint] = Field(default_factory=list)
    sex_distribution: list[DistributionPoint] = Field(default_factory=list)
    age_distribution: list[DistributionPoint] = Field(default_factory=list)
    clinical_interpretation: str = ""
    limitations: list[str] = Field(default_factory=list)


class PrescriptionRisk(BaseModel):
    title: str
    severity: Severity
    drugs_involved: list[str] = Field(default_factory=list)
    description: str
    recommendation: str = ""
    evidence: str = ""


class CausalityCriterion(BaseModel):
    criterion: str
    score: int
    rationale: str


class CausalityAssessment(BaseModel):
    naranjo_score: int
    naranjo_category: Literal["doubtful", "possible", "probable", "definite"]
    who_umc_category: str
    criteria: list[CausalityCriterion] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    opposing_evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    source: str
    source_type: Literal["label", "literature", "faers", "case", "rule", "lab"]
    stance: Literal["supports", "opposes", "uncertain"] = "supports"
    summary: str
    strength: Literal["low", "moderate", "high"] = "moderate"


class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal[
        "drug",
        "adr",
        "patient_factor",
        "lab",
        "evidence",
        "signal",
        "recommendation",
        "agent",
    ]
    risk: Severity | None = None
    detail: str = ""


class GraphLink(BaseModel):
    source: str
    target: str
    label: str
    type: Literal[
        "suspected_cause",
        "increases_risk",
        "supported_by",
        "detected_signal",
        "monitored_by",
        "evaluated_by",
        "recommended_action",
    ]
    risk: Severity | None = None
    evidence: str = ""


class ADRKnowledgeGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)
    highlighted_path: list[str] = Field(default_factory=list)


class AgentStep(BaseModel):
    name: str
    status: Literal["pending", "running", "completed", "skipped", "failed"] = "completed"
    summary: str = ""


class ADRSummary(BaseModel):
    overall_risk_level: Severity
    suspected_drug: str
    suspected_adr: str
    causality_level: str
    signal_level: SignalLevel
    recommendation: str
    source_mode: SourceMode


class ADRAnalysisReport(BaseModel):
    case_id: str
    source_mode: SourceMode
    summary: ADRSummary
    extraction: ADRExtractionResult
    timeline: list[TimelineEvent] = Field(default_factory=list)
    faers_signal: OpenFDASignal
    prescription_risks: list[PrescriptionRisk] = Field(default_factory=list)
    causality: CausalityAssessment
    evidence_chain: list[EvidenceItem] = Field(default_factory=list)
    graph: ADRKnowledgeGraph
    agent_steps: list[AgentStep] = Field(default_factory=list)
    final_report: str
    limitations: list[str] = Field(default_factory=list)

