"""ADR end-to-end analysis routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pharmagent.adr.demo_data import get_demo_examples
from pharmagent.adr.openfda import detect_signal
from pharmagent.adr.schemas import ADRAnalysisReport, ADRExample, OpenFDASignal
from pharmagent.adr.workflow import run_adr_analysis

router = APIRouter()


class ADRAnalyzeRequest(BaseModel):
    case_text: str = Field(..., description="Free-text ADR case or prescription")
    use_realtime_openfda: bool = Field(default=False, description="Try realtime openFDA first")


class RealtimeSignalRequest(BaseModel):
    drug: str
    adr: str


class ADRExamplesResponse(BaseModel):
    adr_examples: list[ADRExample]


@router.get("/adr/examples", response_model=ADRExamplesResponse)
def get_adr_examples() -> ADRExamplesResponse:
    return ADRExamplesResponse(adr_examples=get_demo_examples())


@router.post("/adr/analyze", response_model=ADRAnalysisReport)
def analyze_adr(req: ADRAnalyzeRequest) -> ADRAnalysisReport:
    if not req.case_text or not req.case_text.strip():
        raise HTTPException(status_code=400, detail="case_text 不能为空")
    try:
        return run_adr_analysis(req.case_text, use_realtime_openfda=req.use_realtime_openfda)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ADR 分析失败：{exc}") from exc


@router.post("/adr/openfda/realtime", response_model=OpenFDASignal)
def realtime_openfda(req: RealtimeSignalRequest) -> OpenFDASignal:
    if not req.drug.strip() or not req.adr.strip():
        raise HTTPException(status_code=400, detail="drug 和 adr 不能为空")
    return detect_signal(req.drug, req.adr, realtime=True)

