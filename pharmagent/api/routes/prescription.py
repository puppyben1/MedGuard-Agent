"""Prescription review route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pharmagent.prescription.graph import run_prescription_review
from pharmagent.prescription.schemas import PrescriptionReport

router = APIRouter()


class PrescriptionRequest(BaseModel):
    """Request body for /api/prescription."""

    case_text: str = Field(..., description="Free-text clinical case")
    collections: list[str] | None = Field(
        default=None,
        description="Knowledge bases to search; default uses all three",
    )


@router.post("/prescription", response_model=PrescriptionReport)
def review_prescription(req: PrescriptionRequest) -> PrescriptionReport:
    """Run the full prescription review pipeline and return a structured report."""
    if not req.case_text or not req.case_text.strip():
        raise HTTPException(status_code=400, detail="case_text 不能为空")

    try:
        report = run_prescription_review(req.case_text, collections=req.collections)
    except Exception as exc:  # noqa: BLE001 — surface any pipeline error to the client
        raise HTTPException(status_code=500, detail=f"处方审查失败：{exc}") from exc

    return report
