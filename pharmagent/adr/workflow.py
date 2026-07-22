"""Coordinator workflow for ADR end-to-end analysis."""

from __future__ import annotations

from uuid import uuid4

from pharmagent.adr.causality import evaluate_causality
from pharmagent.adr.evidence import build_evidence_chain
from pharmagent.adr.extractor import extract_adr_case
from pharmagent.adr.graph_builder import build_knowledge_graph
from pharmagent.adr.openfda import detect_signal
from pharmagent.adr.report import compile_final_report, summarize
from pharmagent.adr.schemas import ADRAnalysisReport, AgentStep, PrescriptionRisk


def run_adr_analysis(case_text: str, use_realtime_openfda: bool = False) -> ADRAnalysisReport:
    extraction = extract_adr_case(case_text)
    drug = extraction.suspected_drugs[0].name if extraction.suspected_drugs else "unknown"
    adr = extraction.adverse_events[0].name if extraction.adverse_events else "unknown"

    signal = detect_signal(drug, adr, realtime=use_realtime_openfda)
    prescription_risks = _prescription_risks(case_text, drug, adr, extraction.concomitant_drugs)
    causality = evaluate_causality(extraction, signal)
    evidence_chain = build_evidence_chain(extraction, signal, prescription_risks, causality)
    graph = build_knowledge_graph(extraction, signal, causality, evidence_chain, prescription_risks)
    summary = summarize(extraction, signal, causality, prescription_risks)
    final_report = compile_final_report(summary, signal, causality, evidence_chain)

    return ADRAnalysisReport(
        case_id=str(uuid4()),
        source_mode=signal.source_mode,
        summary=summary,
        extraction=extraction,
        timeline=extraction.timeline,
        faers_signal=signal,
        prescription_risks=prescription_risks,
        causality=causality,
        evidence_chain=evidence_chain,
        graph=graph,
        agent_steps=[
            AgentStep(name="ADR 抽取 Agent", summary=f"识别 {drug} 与 {adr}。"),
            AgentStep(name="FAERS 信号 Agent", summary=f"返回 {signal.signal_level} 信号，报告数 {signal.report_count}。"),
            AgentStep(name="处方风险 Agent", summary=f"识别 {len(prescription_risks)} 条处方/合并用药风险。"),
            AgentStep(name="因果评价 Agent", summary=f"Naranjo {causality.naranjo_score}，{causality.who_umc_category}。"),
            AgentStep(name="证据链 Agent", summary=f"组织 {len(evidence_chain)} 条证据。"),
            AgentStep(name="3D 图谱 Agent", summary=f"生成 {len(graph.nodes)} 个节点、{len(graph.links)} 条关系。"),
        ],
        final_report=final_report,
        limitations=[
            "本系统用于比赛展示和临床决策辅助，不能替代医生或临床药师判断。",
            "本地 FAERS demo 数据用于保证演示稳定，实时查询结果可能受网络和 openFDA 查询口径影响。",
            *signal.limitations,
        ],
    )


def _prescription_risks(
    case_text: str,
    drug: str,
    adr: str,
    concomitant_drugs: list[str],
) -> list[PrescriptionRisk]:
    text = case_text.lower()
    risks: list[PrescriptionRisk] = []
    if "华法林" in case_text and ("布洛芬" in case_text or "ibuprofen" in text):
        risks.append(
            PrescriptionRisk(
                title="抗凝药 + NSAID 出血风险",
                severity="critical",
                drugs_involved=["warfarin", "ibuprofen"],
                description="华法林与布洛芬合用可增加胃肠道出血风险，病例已有黑便、INR 升高和血红蛋白下降。",
                recommendation="建议停用 NSAID 或更换镇痛方案，复查 INR、血红蛋白并评估出血处理。",
                evidence="确定性处方风险规则 + 病例客观指标。",
            )
        )
    if "二甲双胍" in case_text and ("egfr 18" in text or "egfr 1" in text or "肾脏病 4" in case_text):
        risks.append(
            PrescriptionRisk(
                title="二甲双胍 + 严重肾功能不全",
                severity="critical",
                drugs_involved=["metformin"],
                description="严重肾功能不全背景下继续使用二甲双胍会增加乳酸酸中毒风险。",
                recommendation="建议停用二甲双胍，评估酸碱状态、乳酸和肾功能，选择替代降糖方案。",
                evidence="确定性处方风险规则。",
            )
        )
    if ("赖诺普利" in case_text or "lisinopril" in text) and ("布洛芬" in case_text or "ibuprofen" in text):
        risks.append(
            PrescriptionRisk(
                title="ACEI/ARB + NSAID 肾损伤风险",
                severity="high",
                drugs_involved=["lisinopril", "ibuprofen", *concomitant_drugs],
                description="CKD 或利尿剂背景下 ACEI/ARB 与 NSAID 合用可增加急性肾损伤风险。",
                recommendation="建议停用 NSAID，补液并复查肌酐、尿量和电解质。",
                evidence="确定性处方风险规则。",
            )
        )
    if not risks and drug != "unknown":
        risks.append(
            PrescriptionRisk(
                title="疑似 ADR 需药师复核",
                severity="high",
                drugs_involved=[drug, *concomitant_drugs],
                description=f"病例提示 {drug} 与 {adr} 可能相关，需结合完整病历复核。",
                recommendation="建议补充用药剂量、开始时间、停药反应、既往史和实验室指标。",
                evidence="ADR 抽取结果 + 因果评价。",
            )
        )
    return risks

