from __future__ import annotations

from pharmagent.adr.research import (
    export_research_job_csv,
    fetch_pubmed_documents,
    get_research_batch_job,
    import_biodex_annotations,
    parse_research_documents,
    run_research_batch_job,
    submit_research_batch,
)
from pharmagent.adr.schemas import BioDEXImportRequest, PubMedSearchRequest, ResearchBatchExtractRequest


def test_parse_plain_and_jsonl_documents() -> None:
    plain = "Warfarin was associated with gastrointestinal bleeding.\n\nMetformin increased risk of lactic acidosis."
    docs = parse_research_documents(plain)
    assert len(docs) == 2
    assert docs[0]["document_id"] == "doc-1"

    jsonl = '{"pmid":"123","abstract":"Clozapine was associated with agranulocytosis."}'
    docs = parse_research_documents(jsonl)
    assert docs[0]["pmid"] == "123"
    assert "Clozapine" in docs[0]["text"]


def test_research_batch_job_extracts_findings_and_exports_csv() -> None:
    req = ResearchBatchExtractRequest(
        input_text=(
            "PMID: 1001 Warfarin combined with ibuprofen was associated with gastrointestinal bleeding.\n"
            "Metformin use in renal impairment increased risk of lactic acidosis.\n"
            "This sentence has no known ADE pair."
        ),
        input_format="plain",
        source_label="unit_test_batch",
    )
    job = submit_research_batch(req)
    run_research_batch_job(job.job_id, req)
    completed = get_research_batch_job(job.job_id)

    assert completed.status == "completed"
    assert completed.total_documents == 3
    assert completed.report is not None
    assert completed.finding_count >= 2
    assert completed.report.findings[0].source == "unit_test_batch"
    assert completed.report.graph_preview.nodes

    csv_text = export_research_job_csv(job.job_id)
    assert "drug,adverse_event" in csv_text
    assert "warfarin" in csv_text


def test_biodex_import_uses_only_provided_annotations() -> None:
    payload = (
        '{"pmid":"2001","drug":"warfarin","adverse_event":"bleeding",'
        '"evidence_span":"Warfarin bleeding annotation from BioDEX row.","confidence":0.91}\n'
        '{"pmid":"2002","drug":"metformin","adr":"lactic acidosis",'
        '"sentence":"Metformin lactic acidosis annotation from BioDEX row."}'
    )

    report = import_biodex_annotations(
        BioDEXImportRequest(input_text=payload, input_format="jsonl", source_label="biodex_unit")
    )

    assert len(report.findings) == 2
    assert report.findings[0].source == "biodex_unit"
    assert report.findings[0].pmid == "2001"
    assert report.graph_preview.nodes


def test_fetch_pubmed_documents_with_mocked_eutilities(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, payload: object = None, content: bytes = b"") -> None:
            self._payload = payload
            self.content = content

        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return self._payload

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.calls: list[str] = []

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, params: dict[str, object]) -> FakeResponse:
            if "esearch" in url:
                return FakeResponse({"esearchresult": {"idlist": ["12345"]}})
            xml = b"""
            <PubmedArticleSet>
              <PubmedArticle>
                <MedlineCitation>
                  <PMID>12345</PMID>
                  <Article>
                    <ArticleTitle>Warfarin and bleeding</ArticleTitle>
                    <Abstract><AbstractText>Warfarin was associated with bleeding.</AbstractText></Abstract>
                  </Article>
                </MedlineCitation>
              </PubmedArticle>
            </PubmedArticleSet>
            """
            return FakeResponse(content=xml)

    monkeypatch.setattr("pharmagent.adr.research.httpx.Client", FakeClient)

    result = fetch_pubmed_documents(PubMedSearchRequest(query="warfarin bleeding", max_results=1))

    assert result.source_type == "pubmed_eutils"
    assert result.documents[0].pmid == "12345"
    assert "Warfarin was associated with bleeding" in result.input_text
