# Competition Demo Runbook

Use this sequence for a stable MedGuard-Agent demonstration.

## 1. Start Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn pharmagent.api.main:app --reload --port 8000
```

## 2. Start Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the local Vite URL.

## 3. Configure Real Sources

In the system configuration page:

- configure LLM API key for schema extraction and report-grounded QA;
- configure openFDA API key if realtime openFDA is used;
- configure Neo4j if live graph queries are required;
- confirm SIDER/MedDRA RAG and FAERS offline cache status.

Do not describe demo or fallback results as real data.

## 4. Suggested Demo Path

1. ADR case analysis: run one clinical case, show extraction, timeline, signal source, causality, evidence chain, graph, QA, and PDF export.
2. Research mining: run demo or batch text input, show RAG status, PubMed/BioDEX ingestion endpoints, graph preview, QA, CSV export, and PDF export.
3. Polypharmacy: analyze `warfarin, ibuprofen, omeprazole`, then optionally provide a DDI/DrugBank-style CSV path and rerun.
4. System configuration: show runtime source status and strict real-data behavior.

## 5. Verification Commands

```powershell
cd frontend
npm run build

cd ..
.\.venv\Scripts\python.exe -m pytest -q
node C:\Users\Administrator\.codex\skills\impeccable\scripts\detect.mjs --json frontend/src/components/ADRAnalysis.tsx frontend/src/components/ResearchMining.tsx frontend/src/components/PolypharmacyAnalysis.tsx frontend/src/components/Neo4j3DGraph.tsx frontend/src/components/SystemConfig.tsx frontend/src/index.css
```
