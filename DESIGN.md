# Design

<!-- impeccable:design-schema 1 -->

## Visual World

MedGuard-Agent now uses a biomedical research-platform world inspired by modern drug-discovery product sites: bright clinical surfaces, blue-cyan molecular graph lines, dark slate runtime consoles, and restrained red/orange only for clinical risk.

The memorable object is the evidence graph console: Drug, ADR, FAERS, RAG, and Neo4j nodes connected as a live-looking molecular safety network. It communicates the product mechanism without claiming unverified real-world results.

## Interface Principles

- The first viewport must explain the platform and lead directly into a usable workbench.
- Real data, demo data, fallback data, realtime APIs, offline datasets, and live graph sources must remain visibly separated.
- Marketing rhythm is allowed for competition presentation, but operational controls stay familiar, scan-friendly, and touch-safe.
- Dark panels are reserved for runtime consoles, graph surfaces, and high-attention clinical work areas.
- Cards are used for repeated technical modules and scenario summaries; the workbench itself remains a broad operational surface.

## Composition

The page opens with a fixed platform navigation, a left-side value proposition and CTAs, and a right-side evidence graph console. Below it are compact architecture and application bands, followed by the real MedGuard workbench with ADR, research mining, polypharmacy, prescription review, QA, and system configuration modules.

## Color And Type

The base is cool white and pale blue for projected competition rooms and clinical review contexts. Blue/cyan marks computational evidence flow, slate marks runtime surfaces, emerald marks ready sources, amber marks missing configuration, and red/orange are reserved for drug-safety risk.

Typography uses the system UI stack for dependable Chinese and English medical text rendering. Display type is large, compact, and weight-driven rather than decorative.

## Motion

Motion is limited to the evidence graph line flow, loading rings, and small control transitions. It must respect reduced-motion preferences and never obscure clinical content or source labels.

## Source Integrity

No visual treatment may imply that missing PubMed, DrugBank, FAERS, Neo4j, or LLM data exists. Synthetic or demo states must remain labeled as demo, fallback, preview, or unavailable.
