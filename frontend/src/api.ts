// API client for the MedGuard-Agent backend.

import type {
  ADRAnalysisReport,
  ADRExamplesResponse,
  ExamplesResponse,
  HealthResponse,
  PrescriptionReport,
  SafetyAssessment,
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

export const api = {
  health: () => getJson<HealthResponse>("/api/health"),
  examples: () => getJson<ExamplesResponse>("/api/examples"),
  adrExamples: () => getJson<ADRExamplesResponse>("/api/adr/examples"),
  analyzeADR: (case_text: string, use_realtime_openfda = false) =>
    postJson<ADRAnalysisReport>("/api/adr/analyze", { case_text, use_realtime_openfda }),
  reviewPrescription: (case_text: string, collections?: string[]) =>
    postJson<PrescriptionReport>("/api/prescription", { case_text, collections }),
  askQuestion: (query: string) => postJson<SafetyAssessment>("/api/qa", { query }),
};
