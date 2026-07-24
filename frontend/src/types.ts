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

export interface RuntimeConfigStatus {
  llm_provider: "groq" | "openai_compatible";
  llm_base_url: string;
  router_model: string;
  generator_model: string;
  has_llm_api_key: boolean;
  has_openfda_api_key: boolean;
  strict_real_data: boolean;
  neo4j_uri: string;
  neo4j_username: string;
  neo4j_database: string;
  has_neo4j_password: boolean;
  side_effect_zip_path: string;
  side_effect_zip_available: boolean;
  require_real_sources: boolean;
}

export interface RuntimeConfigUpdate {
  llm_provider?: "groq" | "openai_compatible";
  llm_api_key?: string;
  llm_base_url?: string;
  router_model?: string;
  generator_model?: string;
  openfda_api_key?: string;
  strict_real_data?: boolean;
  neo4j_uri?: string;
  neo4j_username?: string;
  neo4j_password?: string;
  neo4j_database?: string;
  side_effect_zip_path?: string;
  require_real_sources?: boolean;
}

export type SignalLevel = "none" | "weak" | "moderate" | "strong";
export type SourceMode = "local_demo" | "realtime_openfda" | "offline_faers" | "mixed" | "fallback_demo";

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
  source: string;
  source_type: string;
  deduplicated: boolean;
  report_count: number;
  serious_count: number;
  death_count: number;
  hospitalization_count: number;
  ror: number | null;
  prr: number | null;
  contingency_table: Partial<Record<"a" | "b" | "c" | "d", number>>;
  serious_ratio: number;
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
  role: string;
  data_source: string;
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

export interface Neo4jNode {
  id: string;
  labels: string[];
  properties: Record<string, string | number | boolean | null>;
}

export interface Neo4jRelationship {
  source: string;
  target: string;
  type: string;
  properties: Record<string, string | number | boolean | null>;
}

export interface Neo4jGraphPreview {
  nodes: Neo4jNode[];
  relationships: Neo4jRelationship[];
  cypher_examples: string[];
}

export interface Neo4jStatus {
  configured: boolean;
  connected: boolean;
  uri: string;
  database: string;
  node_count: number | null;
  relationship_count: number | null;
  error: string;
}

export interface Neo4jQueryResponse {
  source_type: string;
  cypher: string;
  rows: Array<Record<string, unknown>>;
  nodes: Neo4jNode[];
  relationships: Neo4jRelationship[];
  warnings: string[];
}

export interface SideEffectDatasetSummary {
  dataset_name: string;
  available: boolean;
  source_path: string;
  files: string[];
  row_counts: Record<string, number>;
  index_available: boolean;
  index_manifest?: Record<string, unknown>;
  rag_strategy: string[];
  neo4j_schema: string[];
  graph_preview: Neo4jGraphPreview;
  notes: string[];
}

export interface SideEffectRAGStatus {
  available: boolean;
  source_type: string;
  documents_path: string;
  bm25_path: string;
  chroma_path: string;
  document_count: number;
  bm25_available: boolean;
  chroma_available: boolean;
  chroma_error: string;
  manifest: Record<string, unknown>;
}

export interface SideEffectHit {
  doc_id: string;
  drug_cid: string;
  drug_name: string;
  matched_side_effects: Array<Record<string, string | number | null>>;
  source: string;
  source_type: string;
  score: number;
  retrieval_method: string;
  text: string;
}

export interface SideEffectSearchResponse {
  query: string;
  source_type: string;
  hits: SideEffectHit[];
  limitations: string[];
}

export interface FAERSStatus {
  available: boolean;
  source_type: string;
  cache_path: string;
  manifest_path: string;
  source_label: string;
  case_count: number;
  drug_case_count: number;
  reaction_case_count: number;
  outcome_case_count: number;
  deduplicated: boolean;
  error: string;
  manifest: Record<string, unknown>;
}

export interface FAERSSignalResponse extends OpenFDASignal {
  source: string;
  source_type: string;
  deduplicated: boolean;
  contingency_table: Record<"a" | "b" | "c" | "d", number>;
  serious_ratio: number;
}

export interface ResearchFinding {
  pmid: string;
  drug: string;
  adverse_event: string;
  confidence: number;
  evidence_span: string;
  source: string;
  document_id: string;
}

export interface ResearchMiningReport {
  summary: string;
  agent_steps: AgentStep[];
  findings: ResearchFinding[];
  top_drugs: DistributionPoint[];
  adr_categories: DistributionPoint[];
  confidence_distribution: DistributionPoint[];
  graph_preview: Neo4jGraphPreview;
}

export interface ResearchBatchJob {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  source_label: string;
  total_documents: number;
  processed_documents: number;
  finding_count: number;
  error: string;
  report: ResearchMiningReport | null;
}

export interface PolypharmacyPatient {
  age?: number | null;
  diagnoses: string[];
  eGFR?: number | null;
  labs: Record<string, string | number | boolean | null>;
}

export interface SingleDrugRisk {
  drug: string;
  risk: string;
  severity: Severity;
  evidence_source: string;
  rationale: string;
}

export interface PairwiseInteraction {
  drugs: string[];
  risk: string;
  severity: Severity;
  mechanism: string;
  evidence_source: string;
  recommendation: string;
}

export interface HigherOrderRisk {
  drugs: string[];
  risk: string;
  severity: Severity;
  mechanism: string;
  evidence_level: "rule_supported" | "graph_supported" | "faers_supported" | "hypothesis";
  rationale: string;
}

export interface PolypharmacyRecommendation {
  priority: "immediate" | "soon" | "monitor" | "inform";
  text: string;
  rationale: string;
}

export interface PolypharmacyReport {
  source_type: string;
  overall_risk_level: Severity;
  drugs: string[];
  patient: PolypharmacyPatient;
  single_drug_risks: SingleDrugRisk[];
  pairwise_interactions: PairwiseInteraction[];
  higher_order_risks: HigherOrderRisk[];
  mechanism_graph: Neo4jGraphPreview;
  recommendations: PolypharmacyRecommendation[];
  limitations: string[];
}

export interface PageChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatCitation {
  source: string;
  source_type: string;
  summary: string;
}

export interface ADRChatResponse {
  answer: string;
  citations: ChatCitation[];
  confidence: number;
  used_agents: string[];
  limitations: string[];
}
