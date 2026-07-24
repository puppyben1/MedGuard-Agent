"""RAG routes for real local side-effect knowledge sources."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pharmagent.adr.side_effect_rag import (
    SideEffectRAGStatus,
    SideEffectSearchRequest,
    SideEffectSearchResponse,
    search_side_effects,
    side_effect_rag_status,
)

router = APIRouter()


@router.get("/rag/side-effects/status", response_model=SideEffectRAGStatus)
def get_side_effect_rag_status() -> SideEffectRAGStatus:
    return side_effect_rag_status()


@router.post("/rag/side-effects/search", response_model=SideEffectSearchResponse)
def search_side_effect_rag(req: SideEffectSearchRequest) -> SideEffectSearchResponse:
    try:
        return search_side_effects(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"SIDER/MedDRA RAG 检索失败：{exc}") from exc
