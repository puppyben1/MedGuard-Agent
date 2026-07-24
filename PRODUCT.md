# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are clinical pharmacists, physicians, and medical AI competition judges evaluating whether the system can produce evidence-constrained ADR and prescription-risk analysis from free-text clinical cases.

Secondary users are pharmacy or biomedical researchers who want to batch-mine drug-adverse-event associations from public literature or side-effect datasets. This secondary audience is inferred from the current research-mining brief and code.

## Product Purpose

MedGuard-Agent helps users analyze drug safety risk from natural language cases, prescriptions, drug-safety questions, and research corpora. Success means the user can see what was extracted, which agents contributed, which evidence supports the conclusion, what remains uncertain, and what clinical or research action follows.

## Positioning

The product is positioned as a multi-agent ADR pharmacovigilance system rather than a generic drug chatbot. Its differentiating mechanism is the combination of LLM semantic understanding, deterministic safety rules, RAG evidence retrieval, FAERS/openFDA style signal detection, Naranjo/WHO-UMC causality scoring, and Neo4j-style knowledge-graph presentation.

## Operating Context

Confirmed workflows:

- Drug safety Q&A for natural-language medication risk questions.
- Clinical prescription review from free-text patient and medication cases.
- ADR end-to-end case analysis with structured extraction, timeline, FAERS signal metrics, causality scoring, evidence chain, graph view, and report.
- Research batch-mining demo for ADE extraction, aggregate statistics, and Neo4j/GraphRAG preview.

The product is currently a local web app with a React/Vite frontend and FastAPI backend. It is used in a Chinese-language academic and competition context.

## Capabilities and Constraints

Confirmed capabilities:

- Chinese-first UI with mixed Chinese/English medical terminology.
- Structured prescription risk reports with severity, evidence, confidence, and hallucination flags.
- ADR demo analysis over eight stable local cases.
- Local FAERS-style demo data plus optional realtime openFDA querying.
- Runtime preview of a local SIDER/MedDRA side-effect dataset intended for RAG and Neo4j graph construction.

Constraints and open decisions:

- Clinical outputs are decision support only and must not replace physician or pharmacist judgment.
- FAERS/openFDA data indicates reporting association, not causality.
- Some current ADR and research workflows are demo-first and must label local demo/fallback data clearly.
- Full LLM schema extraction, true context-aware Q&A panels, PDF export, full Neo4j persistence, and production GraphRAG remain future work unless explicitly implemented.

## Brand Commitments

The product name is MedGuard-Agent. The voice should be direct, professional, clinically cautious, and evidence-oriented. Competition presentation may use a high-end research-dashboard feel, but factual claims must remain restrained and source-aware.

## Evidence on Hand

- Current implementation: `pharmagent/`, `frontend/src/`, and FastAPI routes.
- Product documentation: `README.md`.
- Local side-effect dataset copied for runtime use: `data/incoming/adr_data.zip` and ignored from git.
- Demo UI screenshots: `docs/images/`.
- Existing tests cover prescription parsing and agent graph behavior.

No real clinical validation, hospital deployment evidence, prospective trials, or formal regulatory approval is present; future work must not imply those exist.

## Product Principles

- Show the reasoning path, not only the answer.
- Prefer source-backed, structured outputs over free-form medical claims.
- Separate statistical association, mechanistic plausibility, and causal assessment.
- Keep competition visuals persuasive while preserving clinical scanability.
- Make demo data, realtime data, and missing evidence visibly distinguishable.

## Accessibility & Inclusion

No product-specific accessibility standard was confirmed. The web interface should preserve readable contrast, keyboard-visible controls, touch-appropriate targets, and Chinese medical terminology clarity.
