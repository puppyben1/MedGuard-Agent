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
