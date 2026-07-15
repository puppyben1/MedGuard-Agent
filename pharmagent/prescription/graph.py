"""LangGraph workflow for MedGuard-Agent prescription review.

Pipeline (7 nodes):

  case_text
     │
     ▼
  parse_case ──► build_queries ──► retrieve ──► grade_docs
                                                   │
                                                   ▼
                                          check_prescription
                                                   │
                                                   ▼
                                          verify_evidence
                                                   │
                                                   ▼
                                             compile_report ──► END

The workflow reuses the existing PharmAgent retrieval (BM25 + ChromaDB
hybrid search) and grading infra, and layers the new prescription risk
checker + evidence verifier on top.
"""

from __future__ import annotations

import time
from itertools import combinations

from langgraph.graph import END, StateGraph

from pharmagent.agent.llm import budget_tracker, get_generator_llm, get_router_llm
from pharmagent.core.document_grader import grade_documents as core_grade
from pharmagent.core.hybrid_retriever import hybrid_search
from pharmagent.core.schemas import RetrievedDoc
from pharmagent.logging_config import get_logger
from pharmagent.prescription.case_parser import parse_case
from pharmagent.prescription.cn_labels import (
    cn_drug_name,
    cn_sex,
    cn_hepatic,
    cn_diagnosis,
    FINDING_TYPE_CN,
    SEVERITY_CN,
)
from pharmagent.prescription.evidence_verifier import verify_findings
from pharmagent.prescription.prescription_checker import check_prescription
from pharmagent.prescription.schemas import (
    PatientCase,
    PrescriptionReport,
)
from pharmagent.prescription.state import PrescriptionState

logger = get_logger(__name__)

DEFAULT_COLLECTIONS = ["drug_labels", "pubmed_literature", "clinical_guidelines"]


# ── Node 1: Parse case ──────────────────────────────────────────────

def parse_case_node(state: PrescriptionState) -> dict:
    """Parse free-text case into a structured PatientCase."""
    case_text = state.get("case_text", "")
    llm = get_router_llm()
    budget_tracker.record_router_call()
    case = parse_case(case_text, llm)
    logger.info(
        "prescription_case_parsed",
        drugs=len(case.drugs),
        age=case.age,
        egfr=case.egfr,
        parse_confidence=case.parse_confidence,
    )
    return {"patient_case": case}


# ── Node 2: Build sub-queries ───────────────────────────────────────

def _drug_query(drug_name: str, case: PatientCase) -> str:
    """Compose a retrieval query for a single drug in this patient's context."""
    parts = [drug_name]
    if case.egfr is not None and case.egfr < 60:
        parts.append("renal impairment dosing contraindication")
    if case.liver_function in ("moderate", "severe"):
        parts.append("hepatic impairment dosing")
    if case.pregnancy:
        parts.append("pregnancy contraindication")
    if case.inr is not None and case.inr >= 4:
        parts.append("INR supratherapeutic bleeding")
    return " ".join(parts)


def _pair_query(d1: str, d2: str) -> str:
    return f"{d1} {d2} drug interaction contraindication bleeding risk"


def _diagnosis_query(diagnosis: str, case: PatientCase) -> str:
    drug_names = ", ".join(d.name for d in case.drugs[:3])
    return f"{diagnosis} {' '.join(case.diagnoses[:2])} {drug_names} guideline contraindication"


def build_queries_node(state: PrescriptionState) -> dict:
    """Plan retrieval sub-queries: per-drug, per-pair, and per-diagnosis."""
    case = state["patient_case"]
    drug_names = [d.name for d in case.drugs]

    sub_queries: list[str] = []

    # Per-drug queries (carry patient context)
    for name in drug_names:
        sub_queries.append(_drug_query(name, case))

    # Drug-pair interaction queries (cap at 6 pairs to bound cost)
    pairs = list(combinations(drug_names, 2))[:6]
    for d1, d2 in pairs:
        sub_queries.append(_pair_query(d1, d2))

    # Diagnosis-specific guideline queries (cap at 3)
    for diagnosis in case.diagnoses[:3]:
        sub_queries.append(_diagnosis_query(diagnosis, case))

    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in sub_queries:
        if q and q not in seen:
            seen.add(q)
            unique.append(q)

    logger.info("subqueries_built", count=len(unique), drugs=len(drug_names))
    return {"sub_queries": unique}


# ── Node 3: Retrieve ────────────────────────────────────────────────

def retrieve_node(state: PrescriptionState) -> dict:
    """Run hybrid search across all sub-queries and aggregate unique docs."""
    sub_queries = state.get("sub_queries", [])
    collections = state.get("collections") or DEFAULT_COLLECTIONS

    seen_keys: set[str] = set()
    aggregated: list[RetrievedDoc] = []

    for q in sub_queries:
        try:
            docs = hybrid_search(q, collections, top_k=10, rerank_top_k=5)
        except Exception as exc:
            logger.warning("retrieve_subquery_failed", query=q[:60], error=str(exc))
            continue
        for doc in docs:
            # Dedupe by source collection + content prefix
            key = f"{doc.source_collection}::{doc.content[:120]}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            aggregated.append(doc)

    logger.info("retrieve_done", sub_queries=len(sub_queries), unique_docs=len(aggregated))
    return {"retrieved_docs": aggregated}


# ── Node 4: Grade documents ─────────────────────────────────────────

def grade_docs_node(state: PrescriptionState) -> dict:
    """Grade all retrieved docs for relevance to the case under review."""
    case = state["patient_case"]
    docs = state.get("retrieved_docs", [])

    # Grade against a single combined query describing the whole case
    drug_summary = ", ".join(d.name for d in case.drugs)
    grade_query = (
        f"Prescription review for {case.age or '?'}y {case.sex} patient. "
        f"Diagnoses: {', '.join(case.diagnoses)}. "
        f"eGFR: {case.egfr}; Liver: {case.liver_function}; INR: {case.inr}. "
        f"Drugs: {drug_summary}."
    )

    llm = get_router_llm()
    budget_tracker.record_router_call()
    graded = core_grade(grade_query, docs, llm)
    relevant = sum(1 for g in graded if g.is_relevant)
    logger.info("grade_done", total=len(graded), relevant=relevant)
    return {"graded_docs": graded}


# ── Node 5: Check prescription ──────────────────────────────────────

def check_prescription_node(state: PrescriptionState) -> dict:
    """Run deterministic + LLM risk checks to produce findings."""
    case = state["patient_case"]
    graded_docs = state.get("graded_docs", [])

    llm = get_generator_llm()
    budget_tracker.record_generator_call()

    findings = check_prescription(case, graded_docs, llm)
    return {"findings": findings}


# ── Node 6: Verify evidence ─────────────────────────────────────────

def verify_evidence_node(state: PrescriptionState) -> dict:
    """Verify each finding against the graded docs."""
    findings = state.get("findings", [])
    graded_docs = state.get("graded_docs", [])

    if not findings:
        return {"verifications": []}

    llm = get_router_llm()
    budget_tracker.record_router_call()
    verifications = verify_findings(findings, graded_docs, llm)
    return {"verifications": verifications}


# ── Node 7: Compile report ──────────────────────────────────────────

_RISK_RANK = {"low": 0, "moderate": 1, "high": 2, "critical": 3}


def _overall_risk(findings) -> str:
    if not findings:
        return "low"
    return max(findings, key=lambda f: _RISK_RANK.get(f.severity, -1)).severity


def _build_summary(case: PatientCase, findings) -> str:
    """Build a detailed Chinese summary of the prescription review."""
    drug_names = [cn_drug_name(d.name) for d in case.drugs] or ["未知药物"]
    drug_str = "、".join(drug_names)

    # Patient profile line (all Chinese)
    sex_cn = cn_sex(case.sex)
    age_sex = f"{case.age}岁{sex_cn}" if case.age else sex_cn
    profile_parts = [f"患者：{age_sex}"]
    if case.egfr is not None:
        profile_parts.append(f"eGFR {case.egfr}")
    if case.liver_function and case.liver_function != "unknown":
        profile_parts.append(f"肝功能{cn_hepatic(case.liver_function)}")
    if case.inr is not None:
        profile_parts.append(f"INR {case.inr}")
    if case.pregnancy:
        profile_parts.append("妊娠中")
    if case.allergies:
        profile_parts.append(f"过敏史: {', '.join(case.allergies)}")
    profile = "，".join(profile_parts)

    if not findings:
        return (
            f"{profile}。当前处方：{drug_str}。\n\n"
            f"✅ 经确定性安全规则与检索证据审查，未发现用药风险或禁忌。"
            f"处方药物与患者状况（肾功能、肝功能、妊娠状态、过敏史）之间未检出相互作用或绝对禁忌。"
        )

    n_critical = sum(1 for f in findings if f.severity == "critical")
    n_high = sum(1 for f in findings if f.severity == "high")
    n_other = len(findings) - n_critical - n_high

    # Risk overview (all Chinese)
    risk_parts = [f"⚠️ 处方审查发现 {len(findings)} 项风险"]
    if n_critical:
        risk_parts.append(f"其中 {n_critical} 项严重（需立即干预）")
    if n_high:
        risk_parts.append(f"{n_high} 项高（需临床评估）")
    if n_other:
        risk_parts.append(f"{n_other} 项其他")
    risk_overview = "，".join(risk_parts) + "。"

    # Per-finding detail (Chinese type labels and drug names)
    finding_lines = []
    for i, f in enumerate(findings, 1):
        sev_label = SEVERITY_CN.get(f.severity, f.severity)
        type_label = FINDING_TYPE_CN.get(f.finding_type, f.finding_type)
        drugs = "、".join(cn_drug_name(d) for d in f.drugs_involved) if f.drugs_involved else "—"
        line = f"  {i}. [{sev_label}] {type_label} — 涉及药物：{drugs}\n     {f.description}"
        if f.recommendation:
            line += f"\n     建议：{f.recommendation}"
        verified_tag = "✅ 已验证" if f.verified else "⚠️ 未验证"
        line += f"\n     证据状态：{verified_tag}"
        finding_lines.append(line)

    return (
        f"{profile}。当前处方：{drug_str}。\n\n"
        f"{risk_overview}\n\n"
        + "\n\n".join(finding_lines)
    )


def compile_report_node(state: PrescriptionState) -> dict:
    """Assemble the final PrescriptionReport with evidence-quality metrics."""
    case = state["patient_case"]
    findings = state.get("findings", [])
    verifications = state.get("verifications", [])
    graded_docs = state.get("graded_docs", [])

    verified_count = sum(1 for v in verifications if v.verified)
    total = len(findings)
    coverage = verified_count / total if total else 0.0

    # Hallucination flag: any high/critical finding without evidence support
    unverified_high_severity = any(
        not v.verified and findings[v.finding_index].severity in ("high", "critical")
        for v in verifications
        if v.finding_index < len(findings)
    )

    # Citations: list all relevant graded docs (broader evidence trail).
    # Prioritize docs that backed a finding, then fill with other relevant docs.
    # Each citation includes: source (Chinese label) + drug + section + title
    # (when available) + a short content excerpt for traceability.
    SOURCE_CN = {
        "pubmed": "PubMed 文献",
        "dailymed": "FDA 药品说明书 (DailyMed)",
        "statpearls": "StatPearls 临床指南",
        "textbooks": "医学教科书",
    }
    SECTION_CN = {
        "warnings": "警告",
        "drug_interactions": "药物相互作用",
        "adverse_reactions": "不良反应",
        "contraindications": "禁忌症",
        "dosage_and_administration": "用法用量",
        "description": "药品描述",
        "warnings_and_precautions": "警告与注意事项",
    }
    cited_doc_ids: set[str] = set()
    for v in verifications:
        for did in v.supporting_doc_ids:
            cited_doc_ids.add(did)

    # Include all retrieved docs (both relevant and not), up to 30.
    # Sort: relevant first, then PubMed (which has titles), then others.
    relevant_docs = sorted(
        graded_docs,
        key=lambda g: (
            not g.is_relevant,            # relevant docs first
            g.doc.metadata.get("source", "") != "pubmed",  # PubMed second
        ),
    )[:30]
    backed = []
    other = []
    for i, gd in enumerate(relevant_docs, start=1):
        doc_id = f"doc-{i}"
        meta = gd.doc.metadata
        source_raw = meta.get("source", "unknown")
        source = SOURCE_CN.get(source_raw, source_raw)
        drug = meta.get("drug_name", "")
        section_raw = meta.get("section", "")
        section = SECTION_CN.get(section_raw, section_raw)
        title = meta.get("title", "").strip()
        # Build a informative citation: source + drug + section + title + excerpt
        parts = [f"[{doc_id}] {source}"]
        if drug:
            parts.append(f"药物：{cn_drug_name(drug)}")
        if section:
            parts.append(f"章节：{section}")
        if title:
            # PubMed articles can have long titles; truncate for readability.
            title_short = title if len(title) <= 120 else title[:117] + "..."
            parts.append(f"标题：{title_short}")
        header = " | ".join(parts)
        excerpt = gd.doc.content[:140].replace("\n", " ").strip()
        entry = f"{header}\n     摘录：{excerpt}..."
        if doc_id in cited_doc_ids:
            backed.append(entry)
        else:
            other.append(entry)
    citations = backed + other

    confidence = 0.0
    if total:
        # confidence = avg over findings of (verified ? 1.0 : 0.4) scaled by parse_confidence
        confidence = sum(1.0 if v.verified else 0.4 for v in verifications) / total
        confidence *= case.parse_confidence

    report = PrescriptionReport(
        patient_case=case,
        findings=findings,
        overall_risk_level=_overall_risk(findings),
        summary=_build_summary(case, findings),
        evidence_coverage=round(coverage, 3),
        unverified_findings_count=total - verified_count,
        hallucination_flagged=unverified_high_severity,
        citations=citations,
        confidence=round(confidence, 3),
        elapsed_seconds=0.0,  # filled by run_prescription_review
    )
    logger.info(
        "report_compiled",
        findings=total,
        verified=verified_count,
        coverage=report.evidence_coverage,
        overall_risk=report.overall_risk_level,
        hallucination_flagged=report.hallucination_flagged,
    )
    return {"report": report}


# ── Graph construction ──────────────────────────────────────────────

def build_prescription_graph() -> StateGraph:
    """Build and compile the prescription review state graph."""
    builder = StateGraph(PrescriptionState)

    builder.add_node("parse_case", parse_case_node)
    builder.add_node("build_queries", build_queries_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("grade_docs", grade_docs_node)
    builder.add_node("check_prescription", check_prescription_node)
    builder.add_node("verify_evidence", verify_evidence_node)
    builder.add_node("compile_report", compile_report_node)

    builder.set_entry_point("parse_case")
    builder.add_edge("parse_case", "build_queries")
    builder.add_edge("build_queries", "retrieve")
    builder.add_edge("retrieve", "grade_docs")
    builder.add_edge("grade_docs", "check_prescription")
    builder.add_edge("check_prescription", "verify_evidence")
    builder.add_edge("verify_evidence", "compile_report")
    builder.add_edge("compile_report", END)

    return builder.compile()


# Pre-built graph instance
prescription_graph = build_prescription_graph()


def run_prescription_review(case_text: str, collections: list[str] | None = None) -> PrescriptionReport:
    """Run the full prescription review pipeline on a free-text case.

    Args:
        case_text: free-text clinical case description
        collections: knowledge bases to search (default: all three)

    Returns:
        PrescriptionReport with findings, verifications, and metrics.
    """
    logger.info("prescription_review_start", case_text=case_text[:80])

    start = time.time()
    initial_state: PrescriptionState = {
        "case_text": case_text,
        "collections": collections or DEFAULT_COLLECTIONS,
    }
    final_state = prescription_graph.invoke(initial_state)
    elapsed = time.time() - start

    report = final_state.get("report")
    if report is None:
        # Compile a minimal failure report so callers always get a PrescriptionReport
        report = PrescriptionReport(
            patient_case=final_state.get("patient_case") or PatientCase(raw_text=case_text),
            summary="Prescription review failed to produce a report.",
            confidence=0.0,
            elapsed_seconds=round(elapsed, 3),
        )
    else:
        report.elapsed_seconds = round(elapsed, 3)

    logger.info(
        "prescription_review_complete",
        elapsed_s=report.elapsed_seconds,
        findings=len(report.findings),
        overall_risk=report.overall_risk_level,
        coverage=report.evidence_coverage,
    )
    return report
