"""Runtime configuration routes for API keys and real-data connectors."""

from __future__ import annotations

from fastapi import APIRouter

from pharmagent.adr.faers_cache import faers_status
from pharmagent.adr.interaction_evidence import interaction_evidence_status
from pharmagent.adr.neo4j_graph import neo4j_status
from pharmagent.adr.side_effect_rag import side_effect_rag_status
from pharmagent.runtime_config import (
    RuntimeConfigStatus,
    RuntimeConfigUpdate,
    load_runtime_config,
    runtime_status,
    save_runtime_config,
)

router = APIRouter()


@router.get("/config", response_model=RuntimeConfigStatus)
def get_config() -> RuntimeConfigStatus:
    return runtime_status(load_runtime_config())


@router.post("/config", response_model=RuntimeConfigStatus)
def update_config(req: RuntimeConfigUpdate) -> RuntimeConfigStatus:
    config = save_runtime_config(req)
    return runtime_status(config)


@router.get("/data/diagnostics")
def data_diagnostics() -> dict:
    config = load_runtime_config()
    status = runtime_status(config)
    rag = side_effect_rag_status()
    faers = faers_status()
    neo4j = neo4j_status()
    ddi = interaction_evidence_status()
    sources = [
        {
            "id": "llm",
            "label": "Runtime LLM",
            "available": status.has_llm_api_key,
            "source_type": "runtime_external_api" if status.has_llm_api_key else "missing_configuration",
            "next_step": "Configure LLM API key in System Config." if not status.has_llm_api_key else "",
        },
        {
            "id": "openfda",
            "label": "Realtime openFDA",
            "available": status.has_openfda_api_key,
            "source_type": "realtime_api" if status.has_openfda_api_key else "missing_configuration",
            "next_step": "Configure openFDA API key or keep outputs labeled as fallback/demo." if not status.has_openfda_api_key else "",
        },
        {
            "id": "sider_meddra_rag",
            "label": "SIDER/MedDRA RAG",
            "available": rag.available,
            "source_type": rag.source_type,
            "next_step": "Run scripts/build_side_effect_rag.py from offline SIDER/MedDRA documents." if not rag.available else "",
        },
        {
            "id": "faers_offline",
            "label": "FAERS offline cache",
            "available": faers.available,
            "source_type": faers.source_type,
            "next_step": "Prepare official FAERS quarterly files and run scripts/build_faers_cache.py." if not faers.available else "",
        },
        {
            "id": "neo4j_live",
            "label": "Neo4j live graph",
            "available": neo4j.configured and neo4j.connected,
            "source_type": "neo4j_live" if neo4j.configured and neo4j.connected else "missing_or_disconnected_graph",
            "next_step": "Import generated CSVs into Neo4j and configure URI/user/password/database." if not (neo4j.configured and neo4j.connected) else "",
        },
        {
            "id": "ddi_external",
            "label": "External DDI/DrugBank-style evidence",
            "available": ddi.available,
            "source_type": ddi.source_type,
            "next_step": "Provide data/interactions/drug_interactions.csv or pass external_evidence_path." if not ddi.available else "",
        },
    ]
    return {
        "source_policy": "Missing real sources are reported as unavailable; the system must not fabricate evidence.",
        "strict_real_data": status.strict_real_data,
        "sources": sources,
    }
