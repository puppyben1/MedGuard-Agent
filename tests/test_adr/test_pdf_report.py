from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from pharmagent.adr.demo_data import get_demo_examples
from pharmagent.adr.pdf_report import render_adr_report_html, render_adr_report_pdf
from pharmagent.adr.workflow import run_adr_analysis
from pharmagent.api.main import app


def test_render_adr_report_html_and_pdf() -> None:
    example = get_demo_examples()[0]
    report = run_adr_analysis(example.case_text)

    html = render_adr_report_html(report)
    assert "MedGuard-Agent ADR 个案报告" in html
    assert report.summary.suspected_drug in html

    pdf = render_adr_report_pdf(report)
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) >= 1


def test_adr_report_pdf_endpoint_returns_attachment() -> None:
    example = get_demo_examples()[0]
    report = run_adr_analysis(example.case_text)
    client = TestClient(app)

    response = client.post("/api/adr/report/pdf", json=report.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) >= 1
