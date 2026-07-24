"""Schemas for the ADR end-to-end analysis workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "moderate", "high", "critical"]
SignalLevel = Literal["none", "weak", "moderate", "strong"]
SourceMode = Literal["local_demo", "realtime_openfda", "offline_faers", "mixed", "fallback_demo"]


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
    source: str = "local demo FAERS-like signal"
    source_type: str = "local_demo"
    deduplicated: bool = False
    report_count: int = 0
    serious_count: int = 0
    death_count: int = 0
    hospitalization_count: int = 0
    ror: float | None = None
    prr: float | None = None
    contingency_table: dict[str, int] = Field(default_factory=dict)
    serious_ratio: float = 0.0
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
    role: str = ""
    data_source: str = ""


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


class Neo4jNode(BaseModel):
    id: str
    labels: list[str]
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class Neo4jRelationship(BaseModel):
    source: str
    target: str
    type: str
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class Neo4jGraphPreview(BaseModel):
    nodes: list[Neo4jNode] = Field(default_factory=list)
    relationships: list[Neo4jRelationship] = Field(default_factory=list)
    cypher_examples: list[str] = Field(default_factory=list)


class SideEffectDatasetSummary(BaseModel):
    dataset_name: str
    available: bool
    source_path: str
    files: list[str] = Field(default_factory=list)
    row_counts: dict[str, int] = Field(default_factory=dict)
    index_available: bool = False
    index_manifest: dict[str, str | int | bool | dict[str, str] | None] = Field(default_factory=dict)
    rag_strategy: list[str] = Field(default_factory=list)
    neo4j_schema: list[str] = Field(default_factory=list)
    graph_preview: Neo4jGraphPreview = Field(default_factory=Neo4jGraphPreview)
    notes: list[str] = Field(default_factory=list)


class ResearchFinding(BaseModel):
    pmid: str
    drug: str
    adverse_event: str
    confidence: float
    evidence_span: str
    source: str = "demo_batch"
    document_id: str = ""


class ResearchMiningReport(BaseModel):
    summary: str
    agent_steps: list[AgentStep] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    top_drugs: list[DistributionPoint] = Field(default_factory=list)
    adr_categories: list[DistributionPoint] = Field(default_factory=list)
    confidence_distribution: list[DistributionPoint] = Field(default_factory=list)
    graph_preview: Neo4jGraphPreview = Field(default_factory=Neo4jGraphPreview)


class ResearchBatchExtractRequest(BaseModel):
    input_text: str
    input_format: Literal["auto", "plain", "jsonl", "csv"] = "auto"
    source_label: str = "user_provided_batch"


class PubMedSearchRequest(BaseModel):
    query: str
    max_results: int = 20
    api_key: str = ""


class PubMedDocument(BaseModel):
    pmid: str
    title: str = ""
    abstract: str = ""
    source_type: str = "pubmed_eutils"


class PubMedSearchResponse(BaseModel):
    source_type: str = "pubmed_eutils"
    query: str
    documents: list[PubMedDocument] = Field(default_factory=list)
    input_text: str = ""
    limitations: list[str] = Field(default_factory=list)


class BioDEXImportRequest(BaseModel):
    input_text: str
    input_format: Literal["auto", "jsonl", "csv"] = "auto"
    source_label: str = "biodex_user_import"


class ResearchBatchJob(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    source_label: str = "user_provided_batch"
    total_documents: int = 0
    processed_documents: int = 0
    finding_count: int = 0
    error: str = ""
    report: ResearchMiningReport | None = None


class PageChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatCitation(BaseModel):
    source: str
    source_type: str = "context"
    summary: str = ""


class ADRChatRequest(BaseModel):
    question: str
    mode: Literal["adr", "research"] = "adr"
    report: ADRAnalysisReport | None = None
    research_report: ResearchMiningReport | None = None
    history: list[PageChatMessage] = Field(default_factory=list)


class ADRChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    confidence: float = 0.0
    used_agents: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Neo4jStatus(BaseModel):
    configured: bool
    connected: bool = False
    uri: str = ""
    database: str = ""
    node_count: int | None = None
    relationship_count: int | None = None
    error: str = ""


class Neo4jQueryRequest(BaseModel):
    cypher: str
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    limit: int = 50


class Neo4jQueryResponse(BaseModel):
    source_type: str = "neo4j_live"
    cypher: str
    rows: list[dict[str, object]] = Field(default_factory=list)
    nodes: list[Neo4jNode] = Field(default_factory=list)
    relationships: list[Neo4jRelationship] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GraphExpandRequest(BaseModel):
    node_id: str
    depth: int = 1
    relationship_types: list[str] = Field(default_factory=list)
    limit: int = 50


class DrugSideEffectsRequest(BaseModel):
    drug: str
    limit: int = 25


class PolypharmacyPatient(BaseModel):
    age: int | None = None
    diagnoses: list[str] = Field(default_factory=list)
    eGFR: float | None = None
    labs: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SingleDrugRisk(BaseModel):
    drug: str
    risk: str
    severity: Severity
    evidence_source: str
    rationale: str


class PairwiseInteraction(BaseModel):
    drugs: list[str]
    risk: str
    severity: Severity
    mechanism: str
    evidence_source: str
    recommendation: str


class HigherOrderRisk(BaseModel):
    drugs: list[str]
    risk: str
    severity: Severity
    mechanism: str
    evidence_level: Literal["rule_supported", "graph_supported", "faers_supported", "hypothesis"]
    rationale: str


class PolypharmacyRecommendation(BaseModel):
    priority: Literal["immediate", "soon", "monitor", "inform"]
    text: str
    rationale: str


class PolypharmacyAnalyzeRequest(BaseModel):
    drugs: list[str]
    patient: PolypharmacyPatient = Field(default_factory=PolypharmacyPatient)
    external_evidence_path: str = ""


class InteractionEvidenceRecord(BaseModel):
    drugs: list[str]
    risk: str
    severity: Severity = "moderate"
    mechanism: str = ""
    evidence_source: str = "external_interaction_file"
    recommendation: str = ""
    source_type: str = "user_provided_external_evidence"


class InteractionEvidenceStatus(BaseModel):
    available: bool
    source_path: str = ""
    record_count: int = 0
    source_type: str = "user_provided_external_evidence"
    error: str = ""


class PolypharmacyReport(BaseModel):
    source_type: str = "rules_rag_faers_graph"
    overall_risk_level: Severity
    drugs: list[str]
    patient: PolypharmacyPatient
    single_drug_risks: list[SingleDrugRisk] = Field(default_factory=list)
    pairwise_interactions: list[PairwiseInteraction] = Field(default_factory=list)
    higher_order_risks: list[HigherOrderRisk] = Field(default_factory=list)
    mechanism_graph: Neo4jGraphPreview = Field(default_factory=Neo4jGraphPreview)
    recommendations: list[PolypharmacyRecommendation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

