"""ADR end-to-end analysis routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from pharmagent.adr.chat import ChatConfigurationError, answer_page_question
from pharmagent.adr.demo_data import get_demo_examples
from pharmagent.adr.openfda import detect_signal
from pharmagent.adr.pdf_report import render_adr_report_html, render_adr_report_pdf
from pharmagent.adr.research import run_research_demo
from pharmagent.adr.schemas import (
    ADRAnalysisReport,
    ADRChatRequest,
    ADRChatResponse,
    ADRExample,
    OpenFDASignal,
    ResearchMiningReport,
    SideEffectDatasetSummary,
)
from pharmagent.adr.side_effect_data import summarize_side_effect_dataset
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


@router.get("/adr/dataset/side-effects", response_model=SideEffectDatasetSummary)
def get_side_effect_dataset() -> SideEffectDatasetSummary:
    return summarize_side_effect_dataset()


@router.get("/adr/research/demo", response_model=ResearchMiningReport)
def research_demo() -> ResearchMiningReport:
    return run_research_demo()


@router.post("/adr/report/html")
def adr_report_html(report: ADRAnalysisReport) -> Response:
    try:
        html = render_adr_report_html(report)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ADR HTML 报告生成失败：{exc}") from exc
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.post("/adr/report/pdf")
def adr_report_pdf(report: ADRAnalysisReport) -> Response:
    try:
        pdf = render_adr_report_pdf(report)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ADR PDF 报告生成失败：{exc}") from exc
    filename = f"medguard-adr-{report.case_id or 'report'}.pdf".replace(" ", "_")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/adr/chat", response_model=ADRChatResponse)
def adr_chat(req: ADRChatRequest) -> ADRChatResponse:
    req.mode = "adr"
    try:
        return answer_page_question(req)
    except ChatConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ADR 问答失败：{exc}") from exc


@router.post("/adr/research/chat", response_model=ADRChatResponse)
def research_chat(req: ADRChatRequest) -> ADRChatResponse:
    req.mode = "research"
    try:
        return answer_page_question(req)
    except ChatConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"科研问答失败：{exc}") from exc

