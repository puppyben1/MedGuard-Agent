"""Compile a reader-facing ADR report."""

from __future__ import annotations

from pharmagent.adr.schemas import (
    ADRExtractionResult,
    ADRSummary,
    CausalityAssessment,
    EvidenceItem,
    OpenFDASignal,
    PrescriptionRisk,
)


def summarize(
    extraction: ADRExtractionResult,
    signal: OpenFDASignal,
    causality: CausalityAssessment,
    prescription_risks: list[PrescriptionRisk],
) -> ADRSummary:
    drug = extraction.suspected_drugs[0].name if extraction.suspected_drugs else signal.drug
    adr = extraction.adverse_events[0].name if extraction.adverse_events else signal.adr
    risk = _overall_risk(signal, causality, prescription_risks)
    return ADRSummary(
        overall_risk_level=risk,
        suspected_drug=drug,
        suspected_adr=adr,
        causality_level=causality.who_umc_category,
        signal_level=signal.signal_level,
        recommendation=_recommendation(risk, prescription_risks),
        source_mode=signal.source_mode,
    )


def compile_final_report(
    summary: ADRSummary,
    signal: OpenFDASignal,
    causality: CausalityAssessment,
    evidence_chain: list[EvidenceItem],
) -> str:
    evidence_lines = "\n".join(f"- {item.source}：{item.summary}" for item in evidence_chain[:5])
    return (
        f"综合判断：病例中 {summary.suspected_drug} 与 {summary.suspected_adr} 存在"
        f" {summary.causality_level} 级别的药物相关性，综合风险为 {summary.overall_risk_level}。\n\n"
        f"真实世界信号：{signal.clinical_interpretation} 报告数 {signal.report_count}，"
        f"严重病例 {signal.serious_count}，ROR={signal.ror}，PRR={signal.prr}。\n\n"
        f"因果评价：Naranjo 得分 {causality.naranjo_score}，分类 {causality.naranjo_category}；"
        f"WHO-UMC 分类为 {causality.who_umc_category}。\n\n"
        f"核心证据：\n{evidence_lines}\n\n"
        f"建议：{summary.recommendation}\n\n"
        "限制：FAERS/openFDA 自发报告只能提示报告关联，不能直接证明因果关系；"
        "最终处置需由医生或临床药师结合完整病历复核。"
    )


def _overall_risk(
    signal: OpenFDASignal,
    causality: CausalityAssessment,
    prescription_risks: list[PrescriptionRisk],
) -> str:
    if any(r.severity == "critical" for r in prescription_risks):
        return "critical"
    if signal.signal_level == "strong" and causality.naranjo_category in {"probable", "definite"}:
        return "critical"
    if signal.signal_level in {"moderate", "strong"} or causality.naranjo_score >= 5:
        return "high"
    return "moderate"


def _recommendation(risk: str, prescription_risks: list[PrescriptionRisk]) -> str:
    if prescription_risks:
        return prescription_risks[0].recommendation
    if risk in {"critical", "high"}:
        return "建议立即由医生/临床药师复核，评估停药、替代治疗和必要监测。"
    return "建议继续监测症状变化，并补充用药时间、停药反应和实验室指标。"

