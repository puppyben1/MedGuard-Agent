// API client for the MedGuard-Agent backend.

import type {
  ADRAnalysisReport,
  ADRChatResponse,
  ADRExamplesResponse,
  ExamplesResponse,
  FAERSSignalResponse,
  FAERSStatus,
  HealthResponse,
  PageChatMessage,
  PolypharmacyReport,
  PrescriptionReport,
  Neo4jQueryResponse,
  Neo4jStatus,
  ResearchBatchJob,
  ResearchMiningReport,
  RuntimeConfigStatus,
  RuntimeConfigUpdate,
  SafetyAssessment,
  SideEffectDatasetSummary,
  SideEffectRAGStatus,
  SideEffectSearchResponse,
} from "./types";

// During development, Vite proxies /api to http://localhost:8000.
// In production, set VITE_API_BASE or serve frontend from the same origin.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const err = await res.json();
      if (err?.detail) detail = err.detail;
    } catch {
      /* ignore parse error */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function postBlob(path: string, body: unknown): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const err = await res.json();
      if (err?.detail) detail = err.detail;
    } catch {
      /* ignore parse error */
    }
    throw new Error(detail);
  }
  return res.blob();
}

export const api = {
  health: () => getJson<HealthResponse>("/api/health"),
  config: () => getJson<RuntimeConfigStatus>("/api/config"),
  updateConfig: (config: RuntimeConfigUpdate) => postJson<RuntimeConfigStatus>("/api/config", config),
  examples: () => getJson<ExamplesResponse>("/api/examples"),
  adrExamples: () => getJson<ADRExamplesResponse>("/api/adr/examples"),
  sideEffectDataset: () => getJson<SideEffectDatasetSummary>("/api/adr/dataset/side-effects"),
  sideEffectRagStatus: () => getJson<SideEffectRAGStatus>("/api/rag/side-effects/status"),
  searchSideEffects: (body: { query?: string; drug?: string; adr?: string; top_k?: number }) =>
    postJson<SideEffectSearchResponse>("/api/rag/side-effects/search", body),
  faersStatus: () => getJson<FAERSStatus>("/api/faers/status"),
  faersSignal: (drug: string, adr: string) => postJson<FAERSSignalResponse>("/api/faers/signal", { drug, adr }),
  neo4jStatus: () => getJson<Neo4jStatus>("/api/graph/status"),
  neo4jDrugSideEffects: (drug: string, limit = 12) =>
    postJson<Neo4jQueryResponse>("/api/graph/drug-side-effects", { drug, limit }),
  neo4jExpand: (node_id: string, depth = 1, relationship_types: string[] = [], limit = 50) =>
    postJson<Neo4jQueryResponse>("/api/graph/expand", { node_id, depth, relationship_types, limit }),
  researchDemo: () => getJson<ResearchMiningReport>("/api/adr/research/demo"),
  researchBatchExtract: (body: { input_text: string; input_format?: "auto" | "plain" | "jsonl" | "csv"; source_label?: string }) =>
    postJson<ResearchBatchJob>("/api/research/batch-extract", body),
  researchJob: (jobId: string) => getJson<ResearchBatchJob>(`/api/research/jobs/${jobId}`),
  researchJobExportUrl: (jobId: string) => `${API_BASE}/api/research/jobs/${jobId}/export`,
  downloadResearchReportPdf: (report: ResearchMiningReport) => postBlob("/api/research/report/pdf", report),
  analyzePolypharmacy: (body: {
    drugs: string[];
    patient?: { age?: number | null; diagnoses?: string[]; eGFR?: number | null; labs?: Record<string, unknown> };
    external_evidence_path?: string;
  }) => postJson<PolypharmacyReport>("/api/polypharmacy/analyze", body),
  downloadPolypharmacyReportPdf: (report: PolypharmacyReport) => postBlob("/api/polypharmacy/report/pdf", report),
  analyzeADR: (case_text: string, use_realtime_openfda = false) =>
    postJson<ADRAnalysisReport>("/api/adr/analyze", { case_text, use_realtime_openfda }),
  downloadADRReportPdf: (report: ADRAnalysisReport) => postBlob("/api/adr/report/pdf", report),
  chatADR: (question: string, report: ADRAnalysisReport, history: PageChatMessage[] = []) =>
    postJson<ADRChatResponse>("/api/adr/chat", { question, report, history, mode: "adr" }),
  chatResearch: (question: string, research_report: ResearchMiningReport, history: PageChatMessage[] = []) =>
    postJson<ADRChatResponse>("/api/adr/research/chat", { question, research_report, history, mode: "research" }),
  reviewPrescription: (case_text: string, collections?: string[]) =>
    postJson<PrescriptionReport>("/api/prescription", { case_text, collections }),
  askQuestion: (query: string) => postJson<SafetyAssessment>("/api/qa", { query }),
};
