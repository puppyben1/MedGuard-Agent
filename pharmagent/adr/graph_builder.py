"""Build frontend-ready ADR knowledge graph data."""

from __future__ import annotations

from pharmagent.adr.schemas import (
    ADRExtractionResult,
    ADRKnowledgeGraph,
    CausalityAssessment,
    EvidenceItem,
    GraphLink,
    GraphNode,
    OpenFDASignal,
    PrescriptionRisk,
)


def build_knowledge_graph(
    extraction: ADRExtractionResult,
    signal: OpenFDASignal,
    causality: CausalityAssessment,
    evidence_chain: list[EvidenceItem],
    prescription_risks: list[PrescriptionRisk],
) -> ADRKnowledgeGraph:
    nodes: dict[str, GraphNode] = {}
    links: list[GraphLink] = []

    primary_drug = extraction.suspected_drugs[0].name if extraction.suspected_drugs else signal.drug
    primary_adr = extraction.adverse_events[0].name if extraction.adverse_events else signal.adr

    _node(nodes, primary_drug, primary_drug, "drug", "high", "疑似主要责任药物")
    _node(nodes, primary_adr, primary_adr, "adr", "critical", "疑似药物不良反应")
    links.append(
        GraphLink(
            source=primary_drug,
            target=primary_adr,
            label="suspected cause",
            type="suspected_cause",
            risk="high",
            evidence="病例时间关系和因果评分支持该关联。",
        )
    )

    for drug in extraction.concomitant_drugs:
        _node(nodes, drug, drug, "drug", "high", "合并用药/相互作用药物")
        links.append(
            GraphLink(
                source=drug,
                target=primary_adr,
                label="increases risk",
                type="increases_risk",
                risk="high",
                evidence="合并用药可能增加 ADR 风险。",
            )
        )

    signal_id = "FAERS signal"
    _node(nodes, signal_id, "FAERS 信号", "signal", "high" if signal.signal_level == "strong" else "moderate", signal.clinical_interpretation)
    links.append(
        GraphLink(
            source=signal_id,
            target=primary_adr,
            label="detected signal",
            type="detected_signal",
            risk="high" if signal.signal_level == "strong" else "moderate",
            evidence=f"报告数 {signal.report_count}，ROR={signal.ror}，PRR={signal.prr}",
        )
    )

    causality_id = "Causality assessment"
    _node(nodes, causality_id, "因果评价", "agent", "high", f"Naranjo {causality.naranjo_score}; {causality.who_umc_category}")
    links.append(
        GraphLink(
            source=causality_id,
            target=primary_adr,
            label="evaluated by",
            type="evaluated_by",
            risk="high",
            evidence=f"Naranjo 分类：{causality.naranjo_category}",
        )
    )

    for value in extraction.objective_evidence[:4]:
        _node(nodes, value, value, "lab", "moderate", "病例中的客观检查或症状证据")
        links.append(
            GraphLink(
                source=value,
                target=primary_adr,
                label="monitored by",
                type="monitored_by",
                risk="moderate",
                evidence="客观指标支持 ADR 判断或后续监测。",
            )
        )

    for idx, item in enumerate(evidence_chain[:5], start=1):
        evidence_id = f"Evidence {idx}"
        _node(nodes, evidence_id, item.source, "evidence", None, item.summary)
        links.append(
            GraphLink(
                source=evidence_id,
                target=primary_adr,
                label="supported by",
                type="supported_by",
                risk=None,
                evidence=item.summary,
            )
        )

    for risk in prescription_risks:
        rec_id = f"Recommendation {risk.title}"
        _node(nodes, rec_id, risk.title, "recommendation", risk.severity, risk.recommendation)
        links.append(
            GraphLink(
                source=rec_id,
                target=primary_drug,
                label="recommended action",
                type="recommended_action",
                risk=risk.severity,
                evidence=risk.description,
            )
        )

    highlighted = [primary_drug]
    if extraction.concomitant_drugs:
        highlighted.append(extraction.concomitant_drugs[0])
    highlighted.extend([primary_adr, signal_id, causality_id])

    return ADRKnowledgeGraph(nodes=list(nodes.values()), links=links, highlighted_path=highlighted)


def _node(
    nodes: dict[str, GraphNode],
    node_id: str,
    label: str,
    node_type: str,
    risk: str | None,
    detail: str,
) -> None:
    if node_id not in nodes:
        nodes[node_id] = GraphNode(id=node_id, label=label, type=node_type, risk=risk, detail=detail)

