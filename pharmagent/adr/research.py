"""Research mining workflow for batch ADE exploration."""

from __future__ import annotations

import csv
import io
import json
import re
import threading
import uuid
from collections import Counter
from datetime import datetime

import httpx
from lxml import etree

from pharmagent.adr.schemas import (
    AgentStep,
    BioDEXImportRequest,
    DistributionPoint,
    Neo4jGraphPreview,
    Neo4jNode,
    Neo4jRelationship,
    PubMedDocument,
    PubMedSearchRequest,
    PubMedSearchResponse,
    ResearchBatchExtractRequest,
    ResearchBatchJob,
    ResearchFinding,
    ResearchMiningReport,
)

_JOB_STORE: dict[str, ResearchBatchJob] = {}
_JOB_LOCK = threading.Lock()
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

KNOWN_DRUGS = [
    "warfarin",
    "ibuprofen",
    "metformin",
    "clozapine",
    "ciprofloxacin",
    "atorvastatin",
    "amiodarone",
    "acetaminophen",
    "lisinopril",
    "hydrochlorothiazide",
    "omeprazole",
    "aspirin",
    "heparin",
    "vancomycin",
    "gentamicin",
]

KNOWN_ADRS = [
    "gastrointestinal bleeding",
    "bleeding",
    "lactic acidosis",
    "agranulocytosis",
    "tendon rupture",
    "tendon injury",
    "rhabdomyolysis",
    "liver injury",
    "hepatotoxicity",
    "acute kidney injury",
    "renal failure",
    "hypoglycemia",
    "qt prolongation",
    "arrhythmia",
    "neutropenia",
    "thrombocytopenia",
    "rash",
    "anaphylaxis",
]

ASSOCIATION_CUES = [
    "associated with",
    "increased risk",
    "risk of",
    "induced",
    "caused",
    "linked to",
    "related to",
    "adverse event",
    "adverse reaction",
    "不良反应",
    "相关",
    "风险",
    "导致",
    "诱发",
]


def run_research_demo() -> ResearchMiningReport:
    findings = [
        ResearchFinding(
            pmid="PMID-DEMO-001",
            drug="warfarin",
            adverse_event="gastrointestinal bleeding",
            confidence=0.94,
            evidence_span="Warfarin combined with NSAIDs was associated with increased gastrointestinal bleeding risk.",
        ),
        ResearchFinding(
            pmid="PMID-DEMO-002",
            drug="metformin",
            adverse_event="lactic acidosis",
            confidence=0.89,
            evidence_span="Renal impairment increased the risk of metformin-associated lactic acidosis.",
        ),
        ResearchFinding(
            pmid="PMID-DEMO-003",
            drug="clozapine",
            adverse_event="agranulocytosis",
            confidence=0.92,
            evidence_span="Clozapine therapy requires white blood cell monitoring due to agranulocytosis risk.",
        ),
        ResearchFinding(
            pmid="PMID-DEMO-004",
            drug="ciprofloxacin",
            adverse_event="tendon rupture",
            confidence=0.86,
            evidence_span="Fluoroquinolone exposure was linked to tendon injury, especially in older patients.",
        ),
    ]

    graph = Neo4jGraphPreview(
        nodes=[
            Neo4jNode(id="Drug:warfarin", labels=["Drug"], properties={"name": "warfarin"}),
            Neo4jNode(id="Drug:ibuprofen", labels=["Drug"], properties={"name": "ibuprofen"}),
            Neo4jNode(id="ADR:bleeding", labels=["SideEffect", "MedDRATerm"], properties={"term": "gastrointestinal bleeding"}),
            Neo4jNode(id="Mechanism:mucosa", labels=["Mechanism"], properties={"name": "gastric mucosal injury"}),
            Neo4jNode(id="Evidence:faers", labels=["Evidence"], properties={"source": "FAERS/local demo"}),
        ],
        relationships=[
            Neo4jRelationship(source="Drug:warfarin", target="ADR:bleeding", type="HAS_SIDE_EFFECT", properties={"weight": 0.92}),
            Neo4jRelationship(source="Drug:ibuprofen", target="Mechanism:mucosa", type="CAUSES_MECHANISM", properties={"weight": 0.75}),
            Neo4jRelationship(source="Mechanism:mucosa", target="ADR:bleeding", type="INCREASES_RISK", properties={"weight": 0.82}),
            Neo4jRelationship(source="Evidence:faers", target="ADR:bleeding", type="SUPPORTS", properties={"level": "real_world"}),
        ],
        cypher_examples=[
            "MATCH p=(d:Drug)-[*1..3]->(s:SideEffect {term:'gastrointestinal bleeding'}) RETURN p;",
        ],
    )

    return ResearchMiningReport(
        summary="科研批量模式原型已将多条文献摘要抽取为药物-ADE 结构化证据，并生成 Neo4j 风格图谱。",
        agent_steps=[
            AgentStep(name="SemanticUnderstandingAgent", role="批量语义解析", data_source="PubMed 摘要", summary="识别文献研究对象、药物实体和 ADR 语境。"),
            AgentStep(name="BatchADEMiningAgent", role="并行 ADE 抽取", data_source="LLM schema", summary=f"抽取 {len(findings)} 条药物-ADE 证据。"),
            AgentStep(name="DeduplicationAgent", role="去重清洗", data_source="结构化 findings", summary="按 drug + adverse_event 合并重复证据。"),
            AgentStep(name="StatisticsAgent", role="科研统计", data_source="批量抽取表", summary="生成 TOP 药物、ADR 分类和置信度分布。"),
            AgentStep(name="GraphRAGAgent", role="Neo4j 图谱构建", data_source="SIDER/MedDRA + demo evidence", summary="构建药物、ADR、机制和证据节点。"),
        ],
        findings=findings,
        top_drugs=[
            DistributionPoint(label="warfarin", count=12),
            DistributionPoint(label="metformin", count=9),
            DistributionPoint(label="clozapine", count=7),
            DistributionPoint(label="ciprofloxacin", count=6),
        ],
        adr_categories=[
            DistributionPoint(label="出血事件", count=12),
            DistributionPoint(label="代谢异常", count=9),
            DistributionPoint(label="血液系统", count=7),
            DistributionPoint(label="肌腱损伤", count=6),
        ],
        confidence_distribution=[
            DistributionPoint(label="0.90-1.00", count=2),
            DistributionPoint(label="0.80-0.89", count=2),
            DistributionPoint(label="0.70-0.79", count=0),
        ],
        graph_preview=graph,
    )


def submit_research_batch(req: ResearchBatchExtractRequest) -> ResearchBatchJob:
    documents = parse_research_documents(req.input_text, req.input_format)
    if not documents:
        raise ValueError("未解析到可处理的摘要或文本记录")
    job_id = f"research-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    job = ResearchBatchJob(
        job_id=job_id,
        status="pending",
        source_label=req.source_label or "user_provided_batch",
        total_documents=len(documents),
    )
    with _JOB_LOCK:
        _JOB_STORE[job_id] = job
    return job


def run_research_batch_job(job_id: str, req: ResearchBatchExtractRequest) -> None:
    try:
        documents = parse_research_documents(req.input_text, req.input_format)
        _update_job(job_id, status="running", total_documents=len(documents))
        findings: list[ResearchFinding] = []
        for index, document in enumerate(documents, start=1):
            findings.extend(_extract_findings_from_document(document, req.source_label or "user_provided_batch"))
            _update_job(job_id, processed_documents=index, finding_count=len(findings))
        report = build_research_report_from_findings(
            findings,
            total_documents=len(documents),
            source_label=req.source_label or "user_provided_batch",
        )
        _update_job(
            job_id,
            status="completed",
            processed_documents=len(documents),
            finding_count=len(findings),
            report=report,
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(job_id, status="failed", error=str(exc))


def get_research_batch_job(job_id: str) -> ResearchBatchJob:
    with _JOB_LOCK:
        job = _JOB_STORE.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job.model_copy(deep=True)


def export_research_job_csv(job_id: str) -> str:
    job = get_research_batch_job(job_id)
    if job.status != "completed" or job.report is None:
        raise ValueError("任务尚未完成，不能导出 CSV")
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["document_id", "pmid", "drug", "adverse_event", "confidence", "evidence_span", "source"],
    )
    writer.writeheader()
    for finding in job.report.findings:
        writer.writerow(finding.model_dump())
    return output.getvalue()


def fetch_pubmed_documents(req: PubMedSearchRequest) -> PubMedSearchResponse:
    query = req.query.strip()
    if not query:
        raise ValueError("query cannot be empty")
    max_results = max(1, min(req.max_results, 100))
    params: dict[str, str | int] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
    }
    if req.api_key:
        params["api_key"] = req.api_key
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        search_response = client.get(PUBMED_SEARCH_URL, params=params)
        search_response.raise_for_status()
        id_list = search_response.json().get("esearchresult", {}).get("idlist", [])
        ids = [str(item) for item in id_list if str(item).strip()]
        if not ids:
            return PubMedSearchResponse(
                query=query,
                documents=[],
                limitations=["PubMed returned no PMIDs for the query; no abstracts were fabricated."],
            )
        fetch_params: dict[str, str | int] = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        }
        if req.api_key:
            fetch_params["api_key"] = req.api_key
        fetch_response = client.get(PUBMED_FETCH_URL, params=fetch_params)
        fetch_response.raise_for_status()
    documents = _parse_pubmed_xml(fetch_response.content)
    input_text = "\n\n".join(
        json.dumps(
            {
                "pmid": doc.pmid,
                "title": doc.title,
                "abstract": doc.abstract,
                "source": doc.source_type,
            },
            ensure_ascii=False,
        )
        for doc in documents
        if doc.abstract.strip()
    )
    limitations = [
        "Results come from PubMed E-utilities at request time.",
        "The system only mines returned title/abstract text; it does not infer missing full-text evidence.",
    ]
    return PubMedSearchResponse(query=query, documents=documents, input_text=input_text, limitations=limitations)


def import_biodex_annotations(req: BioDEXImportRequest) -> ResearchMiningReport:
    rows = _parse_biodex_rows(req.input_text, req.input_format)
    findings: list[ResearchFinding] = []
    for index, row in enumerate(rows, start=1):
        drug = _first_value(row, "drug", "drug_name", "medication", "arg1", "subject")
        adr = _first_value(row, "adverse_event", "adr", "ade", "reaction", "meddra_term", "arg2", "object")
        evidence = _first_value(row, "evidence_span", "evidence", "sentence", "text", "abstract")
        if not drug or not adr or not evidence:
            continue
        confidence = _float_value(row, "confidence", "score", default=0.82)
        findings.append(
            ResearchFinding(
                pmid=_first_value(row, "pmid"),
                document_id=_first_value(row, "document_id", "id") or f"biodex-{index}",
                drug=drug.lower(),
                adverse_event=adr.lower(),
                confidence=max(0.0, min(confidence, 1.0)),
                evidence_span=evidence[:500],
                source=req.source_label or "biodex_user_import",
            )
        )
    return build_research_report_from_findings(
        findings,
        total_documents=len(rows),
        source_label=req.source_label or "biodex_user_import",
    )


def parse_research_documents(input_text: str, input_format: str = "auto") -> list[dict[str, str]]:
    text = input_text.strip()
    if not text:
        return []
    fmt = _detect_format(text, input_format)
    if fmt == "jsonl":
        return _parse_jsonl(text)
    if fmt == "csv":
        return _parse_csv(text)
    return _parse_plain(text)


def _parse_pubmed_xml(content: bytes) -> list[PubMedDocument]:
    root = etree.fromstring(content)
    documents: list[PubMedDocument] = []
    for article in root.xpath(".//PubmedArticle"):
        pmid = "".join(article.xpath(".//MedlineCitation/PMID/text()")).strip()
        title = " ".join(part.strip() for part in article.xpath(".//Article/ArticleTitle//text()") if part.strip())
        abstract = " ".join(part.strip() for part in article.xpath(".//Article/Abstract/AbstractText//text()") if part.strip())
        if pmid:
            documents.append(PubMedDocument(pmid=pmid, title=title, abstract=abstract))
    return documents


def _parse_biodex_rows(input_text: str, input_format: str) -> list[dict[str, object]]:
    text = input_text.strip()
    if not text:
        return []
    fmt = _detect_format(text, input_format)
    if fmt == "jsonl":
        rows: list[dict[str, object]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            if isinstance(raw, dict):
                rows.append(raw)
        return rows
    if fmt == "csv":
        return [dict(row) for row in csv.DictReader(io.StringIO(text))]
    raise ValueError("BioDEX import supports CSV or JSONL only")


def build_research_report_from_findings(
    findings: list[ResearchFinding],
    total_documents: int,
    source_label: str,
) -> ResearchMiningReport:
    top_drugs = [DistributionPoint(label=drug, count=count) for drug, count in Counter(f.drug for f in findings).most_common(8)]
    adr_categories = [
        DistributionPoint(label=adr, count=count)
        for adr, count in Counter(f.adverse_event for f in findings).most_common(8)
    ]
    confidence_distribution = _confidence_distribution(findings)
    graph = _graph_from_findings(findings)
    summary = (
        f"已处理 {total_documents} 条用户提供文本，抽取 {len(findings)} 条药物-ADE 证据。"
        "结果来自用户输入文本的保守规则抽取，不代表 PubMed/BioDEX 在线检索。"
    )
    return ResearchMiningReport(
        summary=summary,
        agent_steps=[
            AgentStep(
                name="InputParsingAgent",
                role="批量输入解析",
                data_source=source_label,
                summary=f"解析 {total_documents} 条 CSV/JSONL/文本记录。",
            ),
            AgentStep(
                name="ConservativeADEExtractor",
                role="药物-ADE 保守抽取",
                data_source="用户提供文本",
                summary=f"仅在同一证据句中命中药物和 ADR 时产出 finding，共 {len(findings)} 条。",
            ),
            AgentStep(
                name="DeduplicationAgent",
                role="去重清洗",
                data_source="drug + adverse_event + document_id",
                summary="按文档、药物和 ADR 合并重复命中。",
            ),
            AgentStep(
                name="StatisticsAgent",
                role="科研统计",
                data_source="批量抽取表",
                summary="生成 TOP 药物、ADR 分布和置信度分布。",
            ),
            AgentStep(
                name="GraphRAGPreviewAgent",
                role="Neo4j 图谱预览",
                data_source="批量抽取 findings",
                summary="构建 Drug、SideEffect 和 Evidence 节点；未连接外部 PubMed/BioDEX。",
            ),
        ],
        findings=findings,
        top_drugs=top_drugs,
        adr_categories=adr_categories,
        confidence_distribution=confidence_distribution,
        graph_preview=graph,
    )


def _detect_format(text: str, requested: str) -> str:
    if requested != "auto":
        return requested
    first_line = text.splitlines()[0]
    if first_line.lstrip().startswith("{"):
        return "jsonl"
    if "," in first_line and any(key in first_line.lower() for key in ("abstract", "text", "pmid")):
        return "csv"
    return "plain"


def _parse_jsonl(text: str) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            continue
        doc_text = str(raw.get("abstract") or raw.get("text") or raw.get("title") or "").strip()
        if not doc_text:
            continue
        documents.append(
            {
                "document_id": str(raw.get("id") or raw.get("document_id") or f"doc-{index}"),
                "pmid": str(raw.get("pmid") or ""),
                "text": doc_text,
            }
        )
    return documents


def _parse_csv(text: str) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    reader = csv.DictReader(io.StringIO(text))
    for index, row in enumerate(reader, start=1):
        lowered = {str(key).lower(): value for key, value in row.items() if key}
        doc_text = str(lowered.get("abstract") or lowered.get("text") or lowered.get("title") or "").strip()
        if not doc_text:
            continue
        documents.append(
            {
                "document_id": str(lowered.get("id") or lowered.get("document_id") or f"doc-{index}"),
                "pmid": str(lowered.get("pmid") or ""),
                "text": doc_text,
            }
        )
    return documents


def _parse_plain(text: str) -> list[dict[str, str]]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n|^-{3,}$", text, flags=re.MULTILINE) if chunk.strip()]
    if len(chunks) == 1:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) > 1:
            chunks = lines
    return [{"document_id": f"doc-{index}", "pmid": _extract_pmid(chunk), "text": chunk} for index, chunk in enumerate(chunks, start=1)]


def _extract_findings_from_document(document: dict[str, str], source_label: str) -> list[ResearchFinding]:
    text = document["text"]
    sentences = _sentences(text)
    findings: dict[tuple[str, str], ResearchFinding] = {}
    for sentence in sentences:
        normalized_sentence = sentence.lower()
        drugs = [drug for drug in KNOWN_DRUGS if _contains_term(normalized_sentence, drug)]
        adrs = [adr for adr in KNOWN_ADRS if _contains_term(normalized_sentence, adr)]
        if not drugs or not adrs:
            continue
        confidence = _confidence(sentence)
        for drug in drugs:
            for adr in adrs:
                key = (drug, adr)
                existing = findings.get(key)
                finding = ResearchFinding(
                    pmid=document.get("pmid", ""),
                    document_id=document.get("document_id", ""),
                    drug=drug,
                    adverse_event=adr,
                    confidence=confidence,
                    evidence_span=sentence[:500],
                    source=source_label or "user_provided_batch",
                )
                if existing is None or finding.confidence > existing.confidence:
                    findings[key] = finding
    return list(findings.values())


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if item.strip()]


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text) is not None


def _confidence(sentence: str) -> float:
    text = sentence.lower()
    cue_hits = sum(1 for cue in ASSOCIATION_CUES if cue in text)
    if cue_hits >= 2:
        return 0.86
    if cue_hits == 1:
        return 0.78
    return 0.62


def _confidence_distribution(findings: list[ResearchFinding]) -> list[DistributionPoint]:
    buckets = {"0.90-1.00": 0, "0.80-0.89": 0, "0.70-0.79": 0, "0.60-0.69": 0}
    for finding in findings:
        if finding.confidence >= 0.9:
            buckets["0.90-1.00"] += 1
        elif finding.confidence >= 0.8:
            buckets["0.80-0.89"] += 1
        elif finding.confidence >= 0.7:
            buckets["0.70-0.79"] += 1
        else:
            buckets["0.60-0.69"] += 1
    return [DistributionPoint(label=label, count=count) for label, count in buckets.items()]


def _graph_from_findings(findings: list[ResearchFinding]) -> Neo4jGraphPreview:
    nodes: dict[str, Neo4jNode] = {}
    relationships: dict[tuple[str, str, str], Neo4jRelationship] = {}
    for finding in findings[:80]:
        drug_id = f"Drug:{finding.drug}"
        adr_id = f"ADR:{finding.adverse_event}"
        evidence_id = f"Evidence:{finding.document_id or finding.pmid or finding.drug + '-' + finding.adverse_event}"
        nodes.setdefault(drug_id, Neo4jNode(id=drug_id, labels=["Drug"], properties={"name": finding.drug}))
        nodes.setdefault(adr_id, Neo4jNode(id=adr_id, labels=["SideEffect"], properties={"term": finding.adverse_event}))
        nodes.setdefault(
            evidence_id,
            Neo4jNode(
                id=evidence_id,
                labels=["Evidence"],
                properties={"source": finding.source, "pmid": finding.pmid, "document_id": finding.document_id},
            ),
        )
        relationships[(drug_id, "HAS_OBSERVED_ADE", adr_id)] = Neo4jRelationship(
            source=drug_id,
            target=adr_id,
            type="HAS_OBSERVED_ADE",
            properties={"confidence": round(finding.confidence, 3), "source": finding.source},
        )
        relationships[(evidence_id, "SUPPORTS", adr_id)] = Neo4jRelationship(
            source=evidence_id,
            target=adr_id,
            type="SUPPORTS",
            properties={"evidence_span": finding.evidence_span[:180]},
        )
    return Neo4jGraphPreview(
        nodes=list(nodes.values()),
        relationships=list(relationships.values()),
        cypher_examples=[
            "MATCH (d:Drug)-[r:HAS_OBSERVED_ADE]->(s:SideEffect) RETURN d,r,s LIMIT 50;",
            "MATCH (e:Evidence)-[:SUPPORTS]->(s:SideEffect) RETURN e,s LIMIT 50;",
        ],
    )


def _extract_pmid(text: str) -> str:
    match = re.search(r"PMID[:\s-]*(\d+)", text, re.IGNORECASE)
    return match.group(1) if match else ""


def _first_value(row: dict[str, object], *keys: str) -> str:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _float_value(row: dict[str, object], *keys: str, default: float) -> float:
    text = _first_value(row, *keys)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _update_job(job_id: str, **updates: object) -> None:
    with _JOB_LOCK:
        job = _JOB_STORE[job_id].model_copy(update=updates)
        _JOB_STORE[job_id] = job
