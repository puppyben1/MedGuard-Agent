// Type definitions mirroring the backend Pydantic schemas.

export type Severity = "low" | "moderate" | "high" | "critical";

export type FindingType =
  | "drug_interaction"
  | "contraindication"
  | "dose_risk"
  | "renal_risk"
  | "hepatic_risk"
  | "pregnancy_risk"
  | "allergy_risk"
  | "monitoring_required"
  | "missing_evidence";

export type HepaticFunction = "normal" | "mild" | "moderate" | "severe" | "unknown";

export interface DrugOrder {
  name: string;
  dose: string;
  route: string;
  frequency: string;
  notes: string;
}

export interface PatientCase {
  age: number | null;
  sex: "male" | "female" | "unknown";
  weight_kg: number | null;
  height_cm: number | null;
  diagnoses: string[];
  allergies: string[];
  pregnancy: boolean | null;
  lactating: boolean | null;
  egfr: number | null;
  liver_function: HepaticFunction;
  inr: number | null;
  drugs: DrugOrder[];
  raw_text: string;
  parse_confidence: number;
}

export interface PrescriptionFinding {
  finding_type: FindingType;
  severity: Severity;
  drugs_involved: string[];
  description: string;
  recommendation: string;
  evidence_doc_ids: string[];
  verified: boolean;
  verification_reason: string;
}

export interface PrescriptionReport {
  patient_case: PatientCase;
  findings: PrescriptionFinding[];
  overall_risk_level: Severity;
  summary: string;
  evidence_coverage: number;
  unverified_findings_count: number;
  hallucination_flagged: boolean;
  citations: string[];
  confidence: number;
  elapsed_seconds: number;
}

export interface SafetyAssessment {
  risk_level: string;
  summary: string;
  evidence: Record<string, unknown>[];
  contraindications: string[];
  monitoring: string[];
  citations: string[];
  confidence: number;
}

export interface ExampleCase {
  label: string;
  text: string;
}

export interface ExamplesResponse {
  prescription_examples: ExampleCase[];
  qa_examples: string[];
}

export interface HealthResponse {
  status: string;
  generator_budget_remaining: number;
  router_budget_remaining: number;
}

export type SignalLevel = "none" | "weak" | "moderate" | "strong";
export type SourceMode = "local_demo" | "realtime_openfda" | "mixed" | "fallback_demo";

export interface ADRExample {
  id: string;
  label: string;
  drug: string;
  adr: string;
  case_text: string;
}

export interface ADRExamplesResponse {
  adr_examples: ADRExample[];
}

export interface SuspectedDrug {
  name: string;
  role: "primary_suspect" | "concomitant" | "interacting";
  evidence_text: string;
}

export interface AdverseEvent {
  name: string;
  original_text: string;
  severity: Severity;
  evidence_text: string;
}

export interface TimelineEvent {
  event_type:
    | "drug_start"
    | "concomitant_drug_start"
    | "adr_onset"
    | "lab_abnormality"
    | "dechallenge"
    | "outcome";
  label: string;
  time_text: string;
  description: string;
  risk_relevance: string;
}

export interface ChallengeInfo {
  available: boolean;
  result: "improved" | "worsened" | "unchanged" | "positive" | "negative" | "unknown";
  evidence_text: string;
}

export interface ADRExtractionResult {
  suspected_drugs: SuspectedDrug[];
  adverse_events: AdverseEvent[];
  timeline: TimelineEvent[];
  dechallenge: ChallengeInfo;
  rechallenge: ChallengeInfo;
  concomitant_drugs: string[];
  objective_evidence: string[];
  missing_information: string[];
  extraction_confidence: number;
}

export interface TrendPoint {
  year: number;
  reports: number;
}

export interface DistributionPoint {
  label: string;
  count: number;
}

export interface OpenFDASignal {
  drug: string;
  adr: string;
  source_mode: SourceMode;
  report_count: number;
  serious_count: number;
  death_count: number;
  hospitalization_count: number;
  ror: number | null;
  prr: number | null;
  signal_level: SignalLevel;
  yearly_trend: TrendPoint[];
  sex_distribution: DistributionPoint[];
  age_distribution: DistributionPoint[];
  clinical_interpretation: string;
  limitations: string[];
}

export interface PrescriptionRisk {
  title: string;
  severity: Severity;
  drugs_involved: string[];
  description: string;
  recommendation: string;
  evidence: string;
}

export interface CausalityCriterion {
  criterion: string;
  score: number;
  rationale: string;
}

export interface CausalityAssessment {
  naranjo_score: number;
  naranjo_category: "doubtful" | "possible" | "probable" | "definite";
  who_umc_category: string;
  criteria: CausalityCriterion[];
  supporting_evidence: string[];
  opposing_evidence: string[];
  missing_information: string[];
}

export interface EvidenceItem {
  source: string;
  source_type: "label" | "literature" | "faers" | "case" | "rule" | "lab";
  stance: "supports" | "opposes" | "uncertain";
  summary: string;
  strength: "low" | "moderate" | "high";
}

export interface GraphNode {
  id: string;
  label: string;
  type:
    | "drug"
    | "adr"
    | "patient_factor"
    | "lab"
    | "evidence"
    | "signal"
    | "recommendation"
    | "agent";
  risk: Severity | null;
  detail: string;
}

export interface GraphLink {
  source: string;
  target: string;
  label: string;
  type:
    | "suspected_cause"
    | "increases_risk"
    | "supported_by"
    | "detected_signal"
    | "monitored_by"
    | "evaluated_by"
    | "recommended_action";
  risk: Severity | null;
  evidence: string;
}

export interface ADRKnowledgeGraph {
  nodes: GraphNode[];
  links: GraphLink[];
  highlighted_path: string[];
}

export interface AgentStep {
  name: string;
  status: "pending" | "running" | "completed" | "skipped" | "failed";
  summary: string;
}

export interface ADRSummary {
  overall_risk_level: Severity;
  suspected_drug: string;
  suspected_adr: string;
  causality_level: string;
  signal_level: SignalLevel;
  recommendation: string;
  source_mode: SourceMode;
}

export interface ADRAnalysisReport {
  case_id: string;
  source_mode: SourceMode;
  summary: ADRSummary;
  extraction: ADRExtractionResult;
  timeline: TimelineEvent[];
  faers_signal: OpenFDASignal;
  prescription_risks: PrescriptionRisk[];
  causality: CausalityAssessment;
  evidence_chain: EvidenceItem[];
  graph: ADRKnowledgeGraph;
  agent_steps: AgentStep[];
  final_report: string;
  limitations: string[];
}
