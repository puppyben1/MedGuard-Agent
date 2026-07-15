"""Prescription risk checker.

Combines deterministic safety rules (operating on the structured PatientCase)
with LLM-driven reasoning over retrieved evidence to produce a list of
PrescriptionFindings covering: drug-drug interactions, contraindications,
dose risks, renal/hepatic risks, pregnancy risks, and monitoring needs.

The deterministic layer guarantees that known absolute contraindications
can never be silently under-reported by the LLM — mirroring the safety
philosophy of pharmagent.core.safety_guardrails.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from pharmagent.core.schemas import GradedDoc
from pharmagent.logging_config import get_logger
from pharmagent.prescription.schemas import (
    PatientCase,
    PrescriptionFinding,
)
from pharmagent.prescription.cn_labels import cn_drug_name, cn_hepatic

logger = get_logger(__name__)


# ── Drug class membership (used by deterministic rules) ─────────────

ACE_INHIBITORS = {
    "lisinopril", "enalapril", "ramipril", "captopril", "benazepril",
    "perindopril", "quinapril", "trandolapril",
}
ARBS = {
    "losartan", "valsartan", "irbesartan", "candesartan", "telmisartan",
    "olmesartan", "eprosartan",
}
NSAIDS = {"aspirin", "ibuprofen", "naproxen", "ketorolac", "diclofenac", "indomethacin", "meloxicam", "celecoxib"}
ANTICOAGS = {"warfarin", "heparin", "enoxaparin"}
DOACS = {"apixaban", "rivaroxaban", "dabigatran", "edoxaban"}
ANTIPLATELETS = {"aspirin", "clopidogrel", "prasugrel", "ticagrelor"}
GLP1 = {"semaglutide", "liraglutide", "dulaglutide", "exenatide"}
METFORMIN = {"metformin"}
NEPHROTOXIC = NSAIDS | {"aminoglycosides", "vancomycin", "contrast"}  # representative
HEPATOTOXIC = {"acetaminophen", "isoniazid", "methotrexate", "statin", "atorvastatin", "simvastatin"}

PREGNANCY_CATEGORY_X = ACE_INHIBITORS | ARBS | {"warfarin", "methotrexate", "isotretinoin", "valproic acid"}


def _drug_set(case: PatientCase) -> set[str]:
    return {d.name.lower() for d in case.drugs}


# ── Deterministic rule engine ───────────────────────────────────────

def _rule_pregnancy_teratogen(case: PatientCase) -> list[PrescriptionFinding]:
    if not case.pregnancy:
        return []
    findings: list[PrescriptionFinding] = []
    drugs = _drug_set(case)
    for drug in drugs & PREGNANCY_CATEGORY_X:
        findings.append(PrescriptionFinding(
            finding_type="contraindication",
            severity="critical",
            drugs_involved=[drug],
            description=(
                f"{cn_drug_name(drug)} 具致畸性（FDA 妊娠分级 X），妊娠期绝对禁用，"
                f"可能导致胎儿肾脏发育不良、颅骨骨化不全等严重伤害。"
            ),
            recommendation="立即停药并更换为妊娠期安全替代方案（如甲基多巴/拉贝洛尔），并请产科会诊评估。",
        ))
    return findings


def _rule_metformin_renal(case: PatientCase) -> list[PrescriptionFinding]:
    drugs = _drug_set(case)
    if "metformin" not in drugs or case.egfr is None:
        return []
    findings: list[PrescriptionFinding] = []
    if case.egfr < 30:
        findings.append(PrescriptionFinding(
            finding_type="contraindication",
            severity="critical",
            drugs_involved=["metformin"],
            description=(
                f"二甲双胍在 eGFR < 30 mL/min/1.73m^2 时禁用（当前 eGFR {case.egfr}），"
                f"因可诱发乳酸酸中毒，死亡率高达 50%。"
            ),
            recommendation="立即停用二甲双胍，改用胰岛素控制血糖，监测血乳酸与肾功能。",
        ))
    elif case.egfr < 45:
        findings.append(PrescriptionFinding(
            finding_type="renal_risk",
            severity="high",
            drugs_involved=["metformin"],
            description=(
                f"eGFR 30-45 时二甲双胍需减量（当前 eGFR {case.egfr}），"
                f"应权衡获益与风险。"
            ),
            recommendation="剂量减半，每 3 个月复查 eGFR，关注恶心/呕吐/肌痛等乳酸酸中毒前驱症状。",
        ))
    return findings


def _rule_anticoag_plus_antiplatelet(case: PatientCase) -> list[PrescriptionFinding]:
    drugs = _drug_set(case)
    has_anticoag = bool(drugs & (ANTICOAGS | DOACS))
    has_antiplatelet = bool(drugs & ANTIPLATELETS)
    has_nsaid = bool(drugs & NSAIDS)
    findings: list[PrescriptionFinding] = []

    if has_anticoag and has_antiplatelet:
        involved = sorted(drugs & (ANTICOAGS | DOACS | ANTIPLATELETS))
        findings.append(PrescriptionFinding(
            finding_type="drug_interaction",
            severity="high",
            drugs_involved=involved,
            description=(
                f"抗凝药 + 抗血小板药联用（{', '.join(cn_drug_name(d) for d in involved)}），"
                f"显著增加大出血风险（HR≈2-3）。"
            ),
            recommendation="重新评估适应证；如必须联用，加用 PPI 保护胃黏膜，监测血红蛋白与大便隐血。",
        ))

    if has_anticoag and has_nsaid:
        involved = sorted(drugs & (ANTICOAGS | DOACS | NSAIDS))
        findings.append(PrescriptionFinding(
            finding_type="drug_interaction",
            severity="high",
            drugs_involved=involved,
            description=(
                f"抗凝药 + 非甾体抗炎药（NSAID）联用（{', '.join(cn_drug_name(d) for d in involved)}），"
                f"显著增加消化道出血风险（OR≈4-6）。"
            ),
            recommendation="避免使用 NSAID；可改用对乙酰氨基酚镇痛，若 NSAID 不可避免加用 PPI。",
        ))
    return findings


def _rule_supratherapeutic_inr(case: PatientCase) -> list[PrescriptionFinding]:
    if case.inr is None or case.inr < 4.0:
        return []
    drugs = _drug_set(case)
    bleed_risk = bool(drugs & (ANTIPLATELETS | NSAIDS | DOACS))
    if "warfarin" not in drugs and not bleed_risk:
        return []
    severity = "critical" if case.inr >= 5.0 else "high"
    involved = sorted(drugs & ({"warfarin"} | ANTIPLATELETS | NSAIDS | DOACS))
    return [PrescriptionFinding(
        finding_type="dose_risk",
        severity=severity,
        drugs_involved=involved,
        description=(
            f"INR 超出治疗范围（当前 {case.inr}，房颤目标 2.0-3.0），"
            f"合并出血风险药物（{', '.join(cn_drug_name(d) for d in involved)}），出血事件显著升高。"
        ),
        recommendation="暂停华法林；INR≥5 时考虑维生素 K 1-2.5mg 口服；24 小时内复查 INR。",
    )]


def _rule_glp1_mtc(case: PatientCase) -> list[PrescriptionFinding]:
    drugs = _drug_set(case)
    if not (drugs & GLP1):
        return []
    fhx = " ".join(case.diagnoses).lower() + " " + case.raw_text.lower()
    if re.search(r"medullary thyroid|mtc|men\s*2|multiple endocrine neoplasia", fhx):
        drug = next(iter(drugs & GLP1))
        return [PrescriptionFinding(
            finding_type="contraindication",
            severity="critical",
            drugs_involved=[drug],
            description=(
                f"{cn_drug_name(drug)} 带 FDA 黑框警告：可引起甲状腺 C 细胞肿瘤，"
                f"个人或家族 MTC/MEN 2 病史者绝对禁用。"
            ),
            recommendation="立即停药；更换为其他降糖药（如 SGLT2 抑制剂或 DPP-4 抑制剂）。",
        )]
    return []


def _rule_allergy_cross_reactivity(case: PatientCase) -> list[PrescriptionFinding]:
    if not case.allergies:
        return []
    findings: list[PrescriptionFinding] = []
    drugs = _drug_set(case)
    for allergy in case.allergies:
        allergy_low = allergy.lower().strip()
        if not allergy_low:
            continue
        # exact match
        if allergy_low in drugs:
            findings.append(PrescriptionFinding(
                finding_type="allergy_risk",
                severity="critical",
                drugs_involved=[allergy_low],
                description=f"患者既往对 {cn_drug_name(allergy_low)} 过敏，本次处方仍包含该药，存在严重过敏反应风险。",
                recommendation="立即停药并归档；选择其他类别替代药物，准备肾上腺素备用。",
            ))
        # penicillin → cephalosporin cross-reactivity (representative)
        elif allergy_low == "penicillin" and drugs & {"cephalexin", "cefuroxime", "ceftriaxone", "cephalosporin"}:
            cross = sorted(drugs & {"cephalexin", "cefuroxime", "ceftriaxone", "cephalosporin"})
            findings.append(PrescriptionFinding(
                finding_type="allergy_risk",
                severity="moderate",
                drugs_involved=cross,
                description=f"青霉素过敏与头孢菌素（{', '.join(cn_drug_name(d) for d in cross)}）存在交叉反应风险（约 1-10%）。",
                recommendation="评估过敏反应史；轻症可考虑皮试或剂量试探，重症应改用其他类别。",
            ))
    return findings


def _rule_nephrotoxic_pairs(case: PatientCase) -> list[PrescriptionFinding]:
    """Flag double nephrotoxic exposure when renal function is already impaired."""
    if case.egfr is None or case.egfr >= 60:
        return []
    drugs = _drug_set(case)
    flagged = []
    if drugs & NSAIDS and drugs & (ACE_INHIBITORS | ARBS):
        flagged = sorted(drugs & (NSAIDS | ACE_INHIBITORS | ARBS))
        severity = "high" if case.egfr < 30 else "moderate"
        return [PrescriptionFinding(
            finding_type="renal_risk",
            severity=severity,
            drugs_involved=flagged,
            description=(
                f"三重肾损伤风险：非甾体抗炎药（NSAID）+ ACEI/ARB 联用（{', '.join(cn_drug_name(d) for d in flagged)}）"
                f"合并 eGFR {case.egfr}，急性肾损伤（AKI）风险显著升高。"
            ),
            recommendation="避免 NSAID；1-2 周内复查肌酐与电解质，关注尿量变化。",
        )]
    return []


def _rule_hepatotoxic(case: PatientCase) -> list[PrescriptionFinding]:
    if case.liver_function not in ("moderate", "severe"):
        return []
    drugs = _drug_set(case)
    flagged = sorted(drugs & HEPATOTOXIC)
    if not flagged:
        return []
    severity = "high" if case.liver_function == "severe" else "moderate"
    return [PrescriptionFinding(
        finding_type="hepatic_risk",
        severity=severity,
        drugs_involved=flagged,
        description=(
            f"肝毒性药物（{', '.join(cn_drug_name(d) for d in flagged)}）用于"
            f"{cn_hepatic(case.liver_function)}的患者，可能加重肝损伤。"
        ),
        recommendation="避免使用或减量；定期监测肝功能（ALT/AST/胆红素）。",
    )]


_DETERMINISTIC_RULES = [
    _rule_pregnancy_teratogen,
    _rule_metformin_renal,
    _rule_anticoag_plus_antiplatelet,
    _rule_supratherapeutic_inr,
    _rule_glp1_mtc,
    _rule_allergy_cross_reactivity,
    _rule_nephrotoxic_pairs,
    _rule_hepatotoxic,
]


def run_deterministic_checks(case: PatientCase) -> list[PrescriptionFinding]:
    """Run all deterministic rules; return findings (deterministic, no LLM)."""
    findings: list[PrescriptionFinding] = []
    for rule in _DETERMINISTIC_RULES:
        try:
            findings.extend(rule(case))
        except Exception as exc:
            logger.warning("deterministic_rule_failed", rule=rule.__name__, error=str(exc))
    logger.info("deterministic_checks_done", findings=len(findings))
    return findings


# ── LLM-driven check over retrieved evidence ───────────────────────

LLM_CHECKER_SYSTEM_PROMPT = """你是一名临床药师 AI，正在根据检索到的证据（药品说明书、PubMed 文献、临床指南）审查处方。

任务：识别出**被所给源文档明确支持**的风险发现。不要凭空捏造源文档未提及的风险。

返回严格符合以下结构的 JSON 对象：
{
  "findings": [
    {
      "finding_type": "drug_interaction" | "contraindication" | "dose_risk" | "renal_risk"
                    | "hepatic_risk" | "pregnancy_risk" | "allergy_risk" | "monitoring_required",
      "severity": "low" | "moderate" | "high" | "critical",
      "drugs_involved": ["药物名"],
      "description": "1-2 句中文描述，必须基于源文档内容",
      "recommendation": "中文临床处置建议",
      "supporting_doc_snippets": ["源文档中支持该发现的简短原文片段"]
    }
  ]
}

规则：
- 仅生成被源文档支持的风险发现。
- 每条发现至少包含一条 supporting_doc_snippet（来自源文档的少量原文引用）。
- 若源文档未提及任何风险，返回 {"findings": []}。
- **description 与 recommendation 必须使用中文（简体中文）书写。** 源文档可能是英文，但你必须将内容翻译成中文后填写，绝不能输出英文描述或英文建议。
- drugs_involved 中的药物名使用英文通用名（如 "warfarin"），以便与系统其他部分匹配。
- supporting_doc_snippet 保留源文档的原文片段（可以是英文），用于证据追溯。
- 仅输出 JSON 对象本身，不要附加任何解释性文本。

示例（注意 description 和 recommendation 均为中文）：
{
  "findings": [
    {
      "finding_type": "drug_interaction",
      "severity": "high",
      "drugs_involved": ["warfarin", "ibuprofen"],
      "description": "华法林与布洛芬（NSAID）联用会显著增加消化道出血风险，患者 INR 已达 3.2，出血风险进一步升高。",
      "recommendation": "避免联用 NSAID；可改用对乙酰氨基酚镇痛，若必须使用 NSAID 则加用质子泵抑制剂并密切监测 INR 和出血征象。",
      "supporting_doc_snippets": ["concomitant use of NSAIDs increases the risk of bleeding"]
    }
  ]
}"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _build_context(graded_docs: list[GradedDoc]) -> tuple[str, dict[str, str]]:
    """Build a numbered context string and a doc_id → metadata map.

    Each relevant doc gets a stable id like 'doc-1' so the verifier can
    link findings back to specific sources.
    """
    relevant = [d for d in graded_docs if d.is_relevant] or graded_docs[:5]
    parts: list[str] = []
    id_map: dict[str, str] = {}
    for i, gd in enumerate(relevant, start=1):
        doc_id = f"doc-{i}"
        meta = gd.doc.metadata
        source = meta.get("source", "unknown")
        drug = meta.get("drug_name", "")
        section = meta.get("section", "")
        header = f"[{doc_id} | {source}"
        if drug:
            header += f" | {drug}"
        if section:
            header += f" | {section}"
        header += "]"
        parts.append(f"{header}\n{gd.doc.content[:1200]}")
        id_map[doc_id] = f"{source} | {drug} | {section}"
    return "\n\n---\n\n".join(parts), id_map


def _match_snippet_to_doc_id(snippet: str, context: str, id_map: dict[str, str]) -> list[str]:
    """Find doc ids whose content contains the supporting snippet (fuzzy).

    Uses multiple sliding anchors instead of a single prefix, so a long
    snippet or one with leading paraphrase still matches the right doc.
    A doc is counted as a supporter if ANY anchor window is found in it.
    """
    if not snippet:
        return []
    snippet_norm = re.sub(r"\s+", " ", snippet.lower()).strip()
    if len(snippet_norm) < 8:
        return []

    # Build several candidate anchor windows from different positions of the
    # snippet. Skip very short windows which are likely to false-match.
    anchor_len = 30
    anchors: list[str] = []
    if len(snippet_norm) <= anchor_len:
        anchors.append(snippet_norm)
    else:
        # Take windows from start, middle, and end to survive paraphrase at edges.
        positions = [0, len(snippet_norm) // 2 - anchor_len // 2, len(snippet_norm) - anchor_len]
        for pos in positions:
            pos = max(0, min(pos, len(snippet_norm) - anchor_len))
            anchor = snippet_norm[pos:pos + anchor_len]
            if len(anchor) >= 12 and anchor not in anchors:
                anchors.append(anchor)

    # Tokenize snippet into significant words as a last-resort signal: if
    # >=60% of the snippet's content words appear in a doc block, count it.
    snippet_words = [w for w in re.findall(r"[a-z]{4,}", snippet_norm)]
    snippet_word_set = set(snippet_words)

    matches: list[str] = []
    for doc_id in id_map:
        pattern = re.compile(rf"\[{re.escape(doc_id)}\s*\|.*?\]\n(.*?)(?=\n\n---|\Z)", re.DOTALL)
        block = pattern.search(context)
        if not block:
            continue
        block_norm = re.sub(r"\s+", " ", block.group(1).lower())

        # Anchor match (strong signal)
        if any(anchor in block_norm for anchor in anchors):
            matches.append(doc_id)
            continue

        # Word-overlap fallback (weak signal) — only when snippet has enough
        # distinctive words to avoid matching generic boilerplate.
        if snippet_word_set:
            block_words = set(re.findall(r"[a-z]{4,}", block_norm))
            overlap = snippet_word_set & block_words
            if len(snippet_word_set) >= 5 and len(overlap) / len(snippet_word_set) >= 0.6:
                matches.append(doc_id)
    return matches


def run_llm_checks(
    case: PatientCase,
    graded_docs: list[GradedDoc],
    llm: Any,
) -> list[PrescriptionFinding]:
    """Ask the LLM to identify findings grounded in retrieved evidence."""
    context, id_map = _build_context(graded_docs)
    if not context:
        logger.info("llm_checker_skipped_no_docs")
        return []

    drug_summary = ", ".join(f"{d.name} {d.dose} {d.frequency}".strip() for d in case.drugs) or "无"
    case_brief = (
        f"患者：{case.age or '?'}岁 {case.sex}；"
        f"诊断：{', '.join(case.diagnoses) or '无'}；"
        f"过敏史：{', '.join(case.allergies) or '无'}；"
        f"eGFR：{case.egfr}；肝功能：{case.liver_function}；INR：{case.inr}；"
        f"妊娠：{case.pregnancy}；"
        f"处方：{drug_summary}"
    )

    user_content = f"患者信息：\n{case_brief}\n\n检索到的源文档：\n\n{context}"
    messages = [
        SystemMessage(content=LLM_CHECKER_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    try:
        response = llm.invoke(messages)
        content = _strip_code_fence(response.content)
        data = json.loads(content)
    except Exception as exc:
        logger.warning("llm_checker_failed", error=str(exc))
        return []

    findings: list[PrescriptionFinding] = []
    for item in data.get("findings", []):
        try:
            snippets = item.get("supporting_doc_snippets", []) or []
            doc_ids: list[str] = []
            for snippet in snippets:
                doc_ids.extend(_match_snippet_to_doc_id(snippet, context, id_map))
            doc_ids = list(dict.fromkeys(doc_ids))  # dedupe preserve order
            findings.append(PrescriptionFinding(
                finding_type=item.get("finding_type", "monitoring_required"),
                severity=item.get("severity", "moderate"),
                drugs_involved=item.get("drugs_involved", []) or [],
                description=item.get("description", ""),
                recommendation=item.get("recommendation", ""),
                evidence_doc_ids=doc_ids,
                verified=False,
            ))
        except Exception as exc:
            logger.warning("llm_finding_parse_failed", error=str(exc))
            continue

    logger.info("llm_checker_done", findings=len(findings), with_evidence=sum(1 for f in findings if f.evidence_doc_ids))
    return findings


# ── Merge + dedupe ──────────────────────────────────────────────────

def _dedupe(findings: list[PrescriptionFinding]) -> list[PrescriptionFinding]:
    """Drop near-duplicate findings (same type + same drug set)."""
    seen: set[tuple] = set()
    unique: list[PrescriptionFinding] = []
    for f in findings:
        key = (f.finding_type, tuple(sorted(d.lower() for d in f.drugs_involved)))
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique


def check_prescription(
    case: PatientCase,
    graded_docs: list[GradedDoc],
    llm: Any,
) -> list[PrescriptionFinding]:
    """Run deterministic + LLM checks and return merged, deduped findings.

    Deterministic findings are always kept (they encode known absolute
    contraindications). LLM findings are only kept when at least one
    supporting doc snippet could be matched (others are dropped to curb
    hallucination at this layer; the evidence_verifier still re-checks).
    """
    deterministic = run_deterministic_checks(case)
    llm_findings = run_llm_checks(case, graded_docs, llm)

    # Drop LLM findings without any matched doc id (likely hallucination)
    grounded_llm = [f for f in llm_findings if f.evidence_doc_ids]

    merged = _dedupe(deterministic + grounded_llm)
    logger.info(
        "prescription_check_complete",
        deterministic=len(deterministic),
        llm_grounded=len(grounded_llm),
        llm_dropped=len(llm_findings) - len(grounded_llm),
        merged=len(merged),
    )
    return merged
