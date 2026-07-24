"""Runtime configuration routes for API keys and real-data connectors."""

from __future__ import annotations

from fastapi import APIRouter

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
