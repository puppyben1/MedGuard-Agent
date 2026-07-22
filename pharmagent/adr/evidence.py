"""Evidence-chain assembly for ADR analysis."""

from __future__ import annotations

from pharmagent.adr.schemas import ADRExtractionResult, CausalityAssessment, EvidenceItem, OpenFDASignal, PrescriptionRisk


def build_evidence_chain(
    extraction: ADRExtractionResult,
    signal: OpenFDASignal,
    prescription_risks: list[PrescriptionRisk],
    causality: CausalityAssessment,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []

    for event in extraction.adverse_events:
        items.append(
            EvidenceItem(
                source="病例原文",
                source_type="case",
                stance="supports",
                summary=f"抽取到疑似 ADR：{event.name}；证据原句：{event.evidence_text}",
                strength="high",
            )
        )

    if extraction.objective_evidence:
        items.append(
            EvidenceItem(
                source="实验室/客观指标",
                source_type="lab",
                stance="supports",
                summary="；".join(extraction.objective_evidence),
                strength="high",
            )
        )

    items.append(
        EvidenceItem(
            source="FAERS/openFDA 信号检测",
            source_type="faers",
            stance="supports" if signal.signal_level != "none" else "uncertain",
            summary=(
                f"{signal.drug} - {signal.adr} 报告数 {signal.report_count}，"
                f"ROR={signal.ror}，PRR={signal.prr}，信号强度：{signal.signal_level}。"
            ),
            strength="high" if signal.signal_level == "strong" else "moderate",
        )
    )

    for risk in prescription_risks:
        items.append(
            EvidenceItem(
                source="处方风险规则",
                source_type="rule",
                stance="supports",
                summary=f"{risk.title}：{risk.description}",
                strength="high" if risk.severity in {"high", "critical"} else "moderate",
            )
        )

    items.append(
        EvidenceItem(
            source="Naranjo / WHO-UMC 因果评价",
            source_type="rule",
            stance="supports",
            summary=(
                f"Naranjo 得分 {causality.naranjo_score}，分类 {causality.naranjo_category}；"
                f"WHO-UMC：{causality.who_umc_category}。"
            ),
            strength="moderate",
        )
    )

    return items

