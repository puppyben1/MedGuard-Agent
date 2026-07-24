"""Routes for offline FAERS quarterly signal analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pharmagent.adr.faers_cache import (
    FAERSSignalRequest,
    FAERSSignalResponse,
    FAERSStatus,
    faers_status,
    query_faers_signal,
)

router = APIRouter()


@router.get("/faers/status", response_model=FAERSStatus)
def get_faers_status() -> FAERSStatus:
    return faers_status()


@router.post("/faers/signal", response_model=FAERSSignalResponse)
def get_faers_signal(req: FAERSSignalRequest) -> FAERSSignalResponse:
    try:
        return query_faers_signal(req.drug, req.adr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"FAERS 离线信号计算失败：{exc}") from exc
