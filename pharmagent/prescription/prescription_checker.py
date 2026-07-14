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
                f"{drug} is teratogenic (FDA pregnancy category X) and is absolutely "
                f"contraindicated during pregnancy due to fetal harm."
            ),
            recommendation="Discontinue immediately and switch to a pregnancy-safe alternative; involve obstetrics.",
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
                f"Metformin is contraindicated at eGFR < 30 mL/min/1.73m^2 "
                f"(current eGFR {case.egfr}) due to lactic acidosis risk."
            ),
            recommendation="Hold metformin; consider insulin for glycemic control.",
        ))
    elif case.egfr < 45:
        findings.append(PrescriptionFinding(
            finding_type="renal_risk",
            severity="high",
            drugs_involved=["metformin"],
            description=(
                f"Metformin dosing should be reduced at eGFR 30-45 "
                f"(current eGFR {case.egfr}); review benefit/risk."
            ),
            recommendation="Reduce dose by 50% and reassess eGFR every 3 months.",
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
                f"Anticoagulant + antiplatelet combination ({', '.join(involved)}) "
                f"significantly increases bleeding risk."
            ),
            recommendation="Reassess indication; if both required, add PPI and monitor Hb/cross-match.",
        ))

    if has_anticoag and has_nsaid:
        involved = sorted(drugs & (ANTICOAGS | DOACS | NSAIDS))
        findings.append(PrescriptionFinding(
            finding_type="drug_interaction",
            severity="high",
            drugs_involved=involved,
            description=(
                f"Anticoagulant + NSAID combination ({', '.join(involved)}) "
                f"markedly increases GI bleeding risk."
            ),
            recommendation="Avoid NSAID; use acetaminophen or add PPI if NSAID unavoidable.",
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
            f"Supratherapeutic INR ({case.inr}) with concurrent bleeding-risk drugs "
            f"({', '.join(involved)})."
        ),
        recommendation="Hold warfarin; consider vitamin K; recheck INR in 24h.",
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
                f"{drug} carries a black box warning for thyroid C-cell tumors and is "
                f"contraindicated in personal/family history of MTC or MEN 2."
            ),
            recommendation="Discontinue; use alternative glycemic agent.",
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
                description=f"Patient is documented allergic to {allergy_low}, which is on the current prescription.",
                recommendation="Discontinue and document; select alternative class.",
            ))
        # penicillin → cephalosporin cross-reactivity (representative)
        elif allergy_low == "penicillin" and drugs & {"cephalexin", "cefuroxime", "ceftriaxone", "cephalosporin"}:
            cross = sorted(drugs & {"cephalexin", "cefuroxime", "ceftriaxone", "cephalosporin"})
            findings.append(PrescriptionFinding(
                finding_type="allergy_risk",
                severity="moderate",
                drugs_involved=cross,
                description=f"Possible cross-reactivity between penicillin allergy and cephalosporin(s): {', '.join(cross)}.",
                recommendation="Assess reaction history; consider alternative or test dose.",
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
                f"Triple-whammy-like renal insult: NSAID + ACE inhibitor/ARB "
                f"with eGFR {case.egfr} (AKI risk)."
            ),
            recommendation="Avoid NSAID; monitor creatinine and electrolytes within 1-2 weeks.",
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
            f"Hepatotoxic drug(s) ({', '.join(flagged)}) in a patient with "
            f"{case.liver_function} hepatic impairment."
        ),
        recommendation="Avoid or reduce dose; monitor LFTs periodically.",
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

LLM_CHECKER_SYSTEM_PROMPT = """You are a clinical pharmacist AI reviewing a prescription against
retrieved evidence (drug labels, PubMed, clinical guidelines).

Your job: identify risk findings that are SUPPORTED by the provided source documents.
Do NOT invent findings that are not grounded in the sources. If the sources do not
mention a risk, do not output it.

Return a JSON object with EXACTLY this shape:
{
  "findings": [
    {
      "finding_type": "drug_interaction" | "contraindication" | "dose_risk" | "renal_risk"
                    | "hepatic_risk" | "pregnancy_risk" | "allergy_risk" | "monitoring_required",
      "severity": "low" | "moderate" | "high" | "critical",
      "drugs_involved": ["drug names"],
      "description": "1-2 sentence description grounded in the sources",
      "recommendation": "suggested clinical action",
      "supporting_doc_snippets": ["short verbatim snippet(s) from the sources that support this finding"]
    }
  ]
}

Rules:
- Only produce findings supported by the source documents.
- For each finding, include at least one supporting_doc_snippet (a few words quoted from the source).
- If no risks are supported by the sources, return {"findings": []}.
- Respond ONLY with the JSON object."""


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

    drug_summary = ", ".join(f"{d.name} {d.dose} {d.frequency}".strip() for d in case.drugs) or "none"
    case_brief = (
        f"Patient: {case.age or '?'}y {case.sex}; "
        f"Diagnoses: {', '.join(case.diagnoses) or 'none'}; "
        f"Allergies: {', '.join(case.allergies) or 'none'}; "
        f"eGFR: {case.egfr}; Liver: {case.liver_function}; INR: {case.inr}; "
        f"Pregnancy: {case.pregnancy}; "
        f"Prescription: {drug_summary}"
    )

    user_content = f"Case brief:\n{case_brief}\n\nSource documents:\n\n{context}"
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
