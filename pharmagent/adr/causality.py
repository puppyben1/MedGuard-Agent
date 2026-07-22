"""Naranjo/WHO-UMC causality assessment for ADR demo cases."""

from __future__ import annotations

from pharmagent.adr.schemas import ADRExtractionResult, CausalityAssessment, CausalityCriterion, OpenFDASignal


def evaluate_causality(
    extraction: ADRExtractionResult,
    signal: OpenFDASignal,
) -> CausalityAssessment:
    """Evaluate ADR causality using an explainable Naranjo-like score."""
    criteria: list[CausalityCriterion] = []
    score = 0

    has_timeline = any(e.event_type == "adr_onset" for e in extraction.timeline)
    score += _add(criteria, "时间关系是否合理", 2 if has_timeline else 0, "病例描述了用药后出现疑似 ADR。" if has_timeline else "缺少明确时间关系。")

    if extraction.dechallenge.available and extraction.dechallenge.result == "improved":
        score += _add(criteria, "停药或处理后是否改善", 1, extraction.dechallenge.evidence_text)
    else:
        score += _add(criteria, "停药或处理后是否改善", 0, "病例未提供明确停药改善信息。")

    if extraction.rechallenge.available and extraction.rechallenge.result == "positive":
        score += _add(criteria, "再给药是否复发", 2, extraction.rechallenge.evidence_text)
    else:
        score += _add(criteria, "再给药是否复发", 0, "未进行或未描述再给药。")

    has_objective = bool(extraction.objective_evidence)
    score += _add(
        criteria,
        "是否有客观证据支持",
        1 if has_objective else 0,
        "；".join(extraction.objective_evidence) if has_objective else "缺少实验室或客观检查证据。",
    )

    known_signal = signal.signal_level in {"moderate", "strong"}
    score += _add(
        criteria,
        "既往是否已有报道或信号",
        1 if known_signal else 0,
        signal.clinical_interpretation or "未发现明确预置安全信号。",
    )

    has_concomitant = bool(extraction.concomitant_drugs)
    score += _add(
        criteria,
        "是否存在其他可能原因",
        0,
        "存在合并用药，但更符合风险增强或相互作用场景，暂不作为反对证据。"
        if has_concomitant
        else "病例未提示明显替代药物原因。",
    )

    category = _naranjo_category(score)
    who = _who_umc_category(category, extraction)

    return CausalityAssessment(
        naranjo_score=score,
        naranjo_category=category,
        who_umc_category=who,
        criteria=criteria,
        supporting_evidence=[
            c.rationale for c in criteria if c.score > 0 and c.rationale
        ],
        opposing_evidence=[
            c.rationale for c in criteria if c.score < 0 and c.rationale
        ],
        missing_information=extraction.missing_information,
    )


def _add(criteria: list[CausalityCriterion], criterion: str, score: int, rationale: str) -> int:
    criteria.append(CausalityCriterion(criterion=criterion, score=score, rationale=rationale))
    return score


def _naranjo_category(score: int) -> str:
    if score >= 9:
        return "definite"
    if score >= 5:
        return "probable"
    if score >= 1:
        return "possible"
    return "doubtful"


def _who_umc_category(category: str, extraction: ADRExtractionResult) -> str:
    if category == "definite" and extraction.rechallenge.available:
        return "Certain"
    if category in {"probable", "definite"}:
        return "Probable/Likely"
    if category == "possible":
        return "Possible"
    return "Unlikely"
