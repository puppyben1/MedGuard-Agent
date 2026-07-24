from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from pharmagent.adr.polypharmacy import analyze_polypharmacy
from pharmagent.adr.schemas import (
    DistributionPoint,
    Neo4jGraphPreview,
    PolypharmacyAnalyzeRequest,
    PolypharmacyPatient,
    ResearchFinding,
    ResearchMiningReport,
)
from pharmagent.api.main import app


def test_research_report_pdf_endpoint_returns_attachment() -> None:
    report = ResearchMiningReport(
        summary="Test research report generated from provided abstracts only.",
        findings=[
            ResearchFinding(
                pmid="1001",
                drug="warfarin",
                adverse_event="gastrointestinal bleeding",
                confidence=0.86,
                evidence_span="Warfarin was associated with gastrointestinal bleeding.",
                source="unit_test",
                document_id="doc-1",
            )
        ],
        top_drugs=[DistributionPoint(label="warfarin", count=1)],
        adr_categories=[DistributionPoint(label="gastrointestinal bleeding", count=1)],
        confidence_distribution=[DistributionPoint(label="0.80-0.89", count=1)],
        graph_preview=Neo4jGraphPreview(),
    )
    client = TestClient(app)

    response = client.post("/api/research/report/pdf", json=report.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) >= 1


def test_polypharmacy_report_pdf_endpoint_returns_attachment() -> None:
    report = analyze_polypharmacy(
        PolypharmacyAnalyzeRequest(
            drugs=["warfarin", "ibuprofen", "omeprazole"],
            patient=PolypharmacyPatient(age=78, diagnoses=["atrial fibrillation"]),
        )
    )
    client = TestClient(app)

    response = client.post("/api/polypharmacy/report/pdf", json=report.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) >= 1
