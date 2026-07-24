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
            AgentStep(
                name="SemanticUnderstandingAgent",
                role="LLM 前置语义理解",
                data_source="病例自由文本",
                summary="解析患者基本信息、用药时序、症状和检验异常。",
            ),
            AgentStep(
                name="ADRExtractionAgent",
                role="ADR 实体抽取",
                data_source="LLM schema + demo fallback",
                summary=f"识别疑似药物 {drug} 与 ADR {adr}。",
            ),
            AgentStep(
                name="PrescriptionRiskAgent",
                role="处方用药风险识别",
                data_source="处方规则/RAG 证据",
                summary=f"识别 {len(prescription_risks)} 条处方或合并用药风险。",
            ),
            AgentStep(
                name="FAERSSignalAgent",
                role="真实世界信号检测",
                data_source="本地 FAERS demo / openFDA",
                summary=f"返回 {signal.signal_level} 信号，报告数 {signal.report_count}。",
            ),
            AgentStep(
                name="CausalityAssessmentAgent",
                role="Naranjo + WHO-UMC 因果评价",
                data_source="病例线索 + 国际量表",
                summary=f"Naranjo {causality.naranjo_score}，{causality.who_umc_category}。",
            ),
            AgentStep(
                name="EvidenceFusionAgent",
                role="层级证据融合",
                data_source="病例/实验室/FAERS/规则",
                summary=f"组织 {len(evidence_chain)} 条高、中、低置信证据。",
            ),
            AgentStep(
                name="GraphRAGAgent",
                role="Neo4j 图谱模式",
                data_source="SIDER/MedDRA + 药物 ADR 图谱",
                summary="生成药物、ADR、证据、机制和监测指标关系。",
            ),
            AgentStep(
                name="VisualizationAgent",
                role="科研级可视化",
                data_source="结构化分析结果",
                summary=f"生成 {len(graph.nodes)} 个节点、{len(graph.links)} 条关系和高危路径。",
            ),
            AgentStep(
                name="ReportQAAgent",
                role="报告生成与问答解释",
                data_source="全流程分析上下文",
                summary="生成专业报告，并为右侧常驻问答面板提供上下文。",
            ),
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

