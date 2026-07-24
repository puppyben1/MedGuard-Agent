"""Research batch ADE extraction routes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

from pharmagent.adr.pdf_report import render_research_report_pdf
from pharmagent.adr.research import (
    export_research_job_csv,
    fetch_pubmed_documents,
    get_research_batch_job,
    import_biodex_annotations,
    run_research_batch_job,
    submit_research_batch,
)
from pharmagent.adr.schemas import (
    BioDEXImportRequest,
    PubMedSearchRequest,
    PubMedSearchResponse,
    ResearchBatchExtractRequest,
    ResearchBatchJob,
    ResearchMiningReport,
)

router = APIRouter()


@router.post("/research/batch-extract", response_model=ResearchBatchJob)
def batch_extract(req: ResearchBatchExtractRequest, background_tasks: BackgroundTasks) -> ResearchBatchJob:
    if not req.input_text.strip():
        raise HTTPException(status_code=400, detail="input_text 不能为空")
    try:
        job = submit_research_batch(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(run_research_batch_job, job.job_id, req)
    return job


@router.get("/research/jobs/{job_id}", response_model=ResearchBatchJob)
def get_job(job_id: str) -> ResearchBatchJob:
    try:
        return get_research_batch_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未找到科研批处理任务") from exc


@router.get("/research/jobs/{job_id}/export")
def export_job(job_id: str) -> Response:
    try:
        csv_text = export_research_job_csv(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未找到科研批处理任务") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.csv"'},
    )


@router.post("/research/pubmed/search", response_model=PubMedSearchResponse)
def search_pubmed(req: PubMedSearchRequest) -> PubMedSearchResponse:
    try:
        return fetch_pubmed_documents(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"PubMed query failed: {exc}") from exc


@router.post("/research/biodex/import", response_model=ResearchMiningReport)
def import_biodex(req: BioDEXImportRequest) -> ResearchMiningReport:
    try:
        return import_biodex_annotations(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"BioDEX import failed: {exc}") from exc


@router.post("/research/report/pdf")
def export_research_report_pdf(report: ResearchMiningReport) -> Response:
    try:
        pdf = render_research_report_pdf(report)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"科研 PDF 报告生成失败：{exc}") from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="medguard-research-report.pdf"'},
    )
