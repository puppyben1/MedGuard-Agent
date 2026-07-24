# MedGuard-Agent PR Plan

## 2026-07-24 Update

This PR continues the "real data chain first, presentation second" roadmap. It adds PDF export support for research mining and polypharmacy reports, and records the current implementation boundaries before PR submission.

## Newly Completed In This Step

- Added research mining PDF export:
  - `POST /api/research/report/pdf`
  - Exports the current `ResearchMiningReport` only.
  - Does not fabricate PubMed, BioDEX, literature conclusions, or real-world metrics.
- Added polypharmacy PDF export:
  - `POST /api/polypharmacy/report/pdf`
  - Exports the current `PolypharmacyReport` only.
  - Does not claim HODDI, DrugBank, or clinically validated prediction.
- Added endpoint tests:
  - `tests/test_adr/test_pdf_exports.py`
  - Verifies PDF attachment headers, `%PDF` bytes, and readable pages with `pypdf`.
- Added P5 real-source research ingestion:
  - `POST /api/research/pubmed/search`
  - `POST /api/research/biodex/import`
  - PubMed uses NCBI E-utilities returned title/abstract text only.
  - BioDEX import uses user-provided CSV/JSONL annotations only.
- Added P6 external interaction evidence fusion:
  - `GET /api/polypharmacy/evidence/status`
  - `PolypharmacyAnalyzeRequest.external_evidence_path`
  - Supports user-provided DDI/DrugBank-style CSV/JSONL evidence files.
- Maintained P7 and demo readiness:
  - PDF exports now include static graph snapshots generated from current report graph data.
  - Research and polypharmacy pages expose frontend PDF download actions with loading/error states.
  - 3D graph rendering samples large graphs and respects reduced-motion / coarse-pointer contexts.
  - Added Neo4j import, FAERS data preparation, and competition demo runbooks.

## PR Scope Already Implemented

- P0: Runtime LLM schema extraction and report-grounded QA panels.
- P1: SIDER/MedDRA offline index and side-effect RAG search.
- P2: Neo4j live driver query APIs and graph expansion contracts.
- P3: Real Three.js / `react-force-graph-3d` graph rendering.
- P4: Offline FAERS cache and disproportionality signal calculation.
- P5: Research batch extraction with in-memory jobs, CSV export, PubMed query ingestion, and BioDEX-style annotation import.
- P6: Polypharmacy risk analysis with rule + evidence graph output and external DDI/DrugBank-style evidence fusion.
- P7: ADR, research, and polypharmacy PDF export endpoints with report graph snapshots.

## Remaining Work After This PR

- P5 enhancement: LLM schema batch extraction, persistent SQLite/Redis/Celery job queue, and richer PubMed/BioDEX field normalization.
- P6 enhancement: curated DrugBank/DDI dataset packaging, dose/lab rules, and offline FAERS combination evidence fusion.
- P7 enhancement: richer report theme templates and optional frontend-captured WebGL screenshots.
- Demo polish: additional real-device mobile QA and final presentation screenshots.
- Data operations: package-specific data validation for user-provided Neo4j, FAERS, PubMed, BioDEX, and DDI files.

## PR Checklist

- Keep runtime secrets out of git; `data/runtime/api_config.json` must remain ignored.
- Confirm every visible data source is labeled as real source, offline real dataset, realtime API, demo, or fallback.
- Run frontend build, focused backend tests, and impeccable frontend detection before staging.
- Review `git status --short` and stage only intended files.
