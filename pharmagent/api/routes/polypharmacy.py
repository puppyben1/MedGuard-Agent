"""Routes for higher-order polypharmacy risk analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from pharmagent.adr.interaction_evidence import interaction_evidence_status
from pharmagent.adr.pdf_report import render_polypharmacy_report_pdf
from pharmagent.adr.polypharmacy import analyze_polypharmacy
from pharmagent.adr.schemas import InteractionEvidenceStatus, PolypharmacyAnalyzeRequest, PolypharmacyReport

router = APIRouter()


@router.post("/polypharmacy/analyze", response_model=PolypharmacyReport)
def analyze(req: PolypharmacyAnalyzeRequest) -> PolypharmacyReport:
    try:
        return analyze_polypharmacy(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"多药高阶风险分析失败：{exc}") from exc


@router.get("/polypharmacy/evidence/status", response_model=InteractionEvidenceStatus)
def evidence_status(source_path: str = "") -> InteractionEvidenceStatus:
    return interaction_evidence_status(source_path)


@router.post("/polypharmacy/report/pdf")
def export_polypharmacy_report_pdf(report: PolypharmacyReport) -> Response:
    try:
        pdf = render_polypharmacy_report_pdf(report)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"多药风险 PDF 报告生成失败：{exc}") from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="medguard-polypharmacy-report.pdf"'},
    )
