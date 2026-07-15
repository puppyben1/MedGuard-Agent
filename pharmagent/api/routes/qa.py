"""Drug safety QA route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pharmagent.agent.graph import run_agent
from pharmagent.core.schemas import SafetyAssessment

router = APIRouter()


class QARequest(BaseModel):
    """Request body for /api/qa."""

    query: str = Field(..., description="Natural-language drug safety question")


@router.post("/qa", response_model=SafetyAssessment)
def ask_question(req: QARequest) -> SafetyAssessment:
    """Run the PharmAgent drug-safety QA and return a structured assessment."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query 不能为空")

    try:
        assessment = run_agent(req.query)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"问答失败：{exc}") from exc

    return assessment
