"""ADR extraction for demo-first end-to-end analysis."""

from __future__ import annotations

from pharmagent.adr.demo_data import find_demo_by_text
from pharmagent.adr.schemas import (
    ADRExtractionResult,
    AdverseEvent,
    ChallengeInfo,
    SuspectedDrug,
    TimelineEvent,
)


def extract_adr_case(case_text: str) -> ADRExtractionResult:
    """Extract a structured ADR case using demo matching plus simple rules."""
    demo = find_demo_by_text(case_text)
    if demo is None:
        return ADRExtractionResult(
            suspected_drugs=[SuspectedDrug(name="unknown", evidence_text="未识别到明确疑似药物")],
            adverse_events=[AdverseEvent(name="unknown", evidence_text="未识别到明确 ADR")],
            missing_information=["疑似药物", "ADR 标准术语", "用药时间", "停药/再给药信息"],
            extraction_confidence=0.35,
        )

    text = case_text or demo.case_text
    concomitant = _concomitant_drugs(demo.id)
    objective = _objective_evidence(demo.id)
    timeline = _timeline_for_demo(demo.id)

    return ADRExtractionResult(
        suspected_drugs=[
            SuspectedDrug(name=demo.drug, role="primary_suspect", evidence_text=_drug_evidence(demo.id)),
            *[
                SuspectedDrug(name=drug, role="interacting", evidence_text=f"病例中提及合用 {drug}")
                for drug in concomitant
            ],
        ],
        adverse_events=[
            AdverseEvent(
                name=demo.adr,
                original_text=_adr_original_text(demo.id),
                severity="critical" if demo.id in {"warfarin_ibuprofen_bleeding", "clozapine_agranulocytosis"} else "high",
                evidence_text=_adr_evidence(demo.id),
            )
        ],
        timeline=timeline,
        dechallenge=ChallengeInfo(
            available="停" in text or "好转" in text or "改善" in text,
            result="improved" if ("好转" in text or "改善" in text or "缓解" in text) else "unknown",
            evidence_text=_dechallenge_evidence(demo.id),
        ),
        rechallenge=ChallengeInfo(available=False, result="unknown", evidence_text="病例未描述再给药。"),
        concomitant_drugs=concomitant,
        objective_evidence=objective,
        missing_information=["未描述再给药反应", "未提供完整既往 ADR 史"],
        extraction_confidence=0.88,
    )


def _concomitant_drugs(example_id: str) -> list[str]:
    return {
        "warfarin_ibuprofen_bleeding": ["ibuprofen"],
        "acei_nsaid_ckd_aki": ["ibuprofen", "hydrochlorothiazide"],
        "ciprofloxacin_tendon": ["glucocorticoid"],
    }.get(example_id, [])


def _objective_evidence(example_id: str) -> list[str]:
    return {
        "warfarin_ibuprofen_bleeding": ["INR 4.8", "血红蛋白下降", "黑便"],
        "metformin_ckd_lactic_acidosis": ["eGFR 18", "乳酸升高", "呼吸深快"],
        "statin_rhabdomyolysis": ["CK 显著升高", "茶色尿"],
        "amiodarone_thyroid": ["TSH 降低", "FT4 升高"],
        "ciprofloxacin_tendon": ["跟腱疼痛", "跟腱断裂"],
        "clozapine_agranulocytosis": ["白细胞下降", "中性粒细胞下降", "发热"],
        "acetaminophen_liver_injury": ["ALT 升高", "AST 升高"],
        "acei_nsaid_ckd_aki": ["eGFR 50", "肌酐升高", "尿量减少"],
    }.get(example_id, [])


def _timeline_for_demo(example_id: str) -> list[TimelineEvent]:
    common = {
        "warfarin_ibuprofen_bleeding": [
            ("drug_start", "开始/长期使用华法林", "长期", "房颤抗凝治疗", "建立疑似药物暴露"),
            ("concomitant_drug_start", "加入布洛芬", "近日", "因关节痛自行服用 NSAID", "合用药增加出血风险"),
            ("adr_onset", "出现黑便和乏力", "3 天后", "提示胃肠道出血", "时间关系合理"),
            ("lab_abnormality", "INR 4.8 / 血红蛋白下降", "就诊时", "存在客观证据", "支持严重出血"),
            ("dechallenge", "停用布洛芬并调整华法林后改善", "处理后", "停药后症状改善", "支持因果关系"),
        ],
        "metformin_ckd_lactic_acidosis": [
            ("drug_start", "长期使用二甲双胍", "长期", "糖尿病治疗", "暴露明确"),
            ("lab_abnormality", "eGFR 18", "入院时", "严重肾功能不全", "显著增加乳酸酸中毒风险"),
            ("adr_onset", "乏力、恶心、呼吸深快", "近两日", "疑似乳酸酸中毒表现", "时间关系可疑"),
            ("dechallenge", "停药并纠正酸中毒后好转", "处理后", "停药改善", "支持因果关系"),
        ],
    }
    rows = common.get(
        example_id,
        [
            ("drug_start", "疑似药物暴露", "用药后", "病例描述存在药物暴露", "建立时间顺序"),
            ("adr_onset", "出现疑似 ADR", "随后", "症状或检查异常出现", "提示药物相关可能"),
            ("dechallenge", "停药后改善", "处理后", "病例描述改善或需进一步确认", "支持因果判断"),
        ],
    )
    return [
        TimelineEvent(
            event_type=event_type,
            label=label,
            time_text=time_text,
            description=description,
            risk_relevance=risk_relevance,
        )
        for event_type, label, time_text, description, risk_relevance in rows
    ]


def _drug_evidence(example_id: str) -> str:
    return {
        "warfarin_ibuprofen_bleeding": "因房颤长期服用华法林",
        "metformin_ckd_lactic_acidosis": "长期服用二甲双胍 1000mg 每日两次",
        "statin_rhabdomyolysis": "服用阿托伐他汀后出现明显肌痛",
    }.get(example_id, "病例中描述疑似药物暴露")


def _adr_original_text(example_id: str) -> str:
    return {
        "warfarin_ibuprofen_bleeding": "黑便、乏力",
        "metformin_ckd_lactic_acidosis": "乳酸升高、呼吸深快",
        "statin_rhabdomyolysis": "肌痛、茶色尿",
    }.get(example_id, "疑似不良反应")


def _adr_evidence(example_id: str) -> str:
    return {
        "warfarin_ibuprofen_bleeding": "3 天后出现黑便、乏力，INR 4.8，血红蛋白下降",
        "metformin_ckd_lactic_acidosis": "出现乏力、恶心、呼吸深快，乳酸升高",
    }.get(example_id, "病例中描述症状或实验室异常")


def _dechallenge_evidence(example_id: str) -> str:
    return {
        "warfarin_ibuprofen_bleeding": "停用布洛芬并调整华法林后症状改善",
        "metformin_ckd_lactic_acidosis": "停用二甲双胍并纠正酸中毒后好转",
    }.get(example_id, "病例描述停药或处理后改善")

