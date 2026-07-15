"""Healthcare safety guardrails for PharmAgent.

This module enforces domain-critical safety rules that must not be left
to LLM judgment alone:
  1. Drug coverage validation — detect out-of-index drugs before synthesis.
  2. Critical-risk escalation — pattern-match known absolute contraindications
     and override the LLM's risk_level when it under-reports.
  3. Missing-drug disclaimers — ensure the final output never silently omits
     drugs it has no data for.
"""

from __future__ import annotations

import re

from pharmagent.core.schemas import SafetyAssessment
from pharmagent.core.vectorstore import get_chroma_client
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

# ── Known absolute contraindications ────────────────────────────────
# Each rule: (pattern on query, required risk_level, reason)
# Patterns are case-insensitive regex applied to the raw user query.
CRITICAL_RULES: list[tuple[re.Pattern, str, str]] = [
    # ACE inhibitors + pregnancy
    (
        re.compile(
            r"(lisinopril|enalapril|ramipril|captopril|benazepril|ace\s*inhibitor)"
            r".*pregnan",
            re.IGNORECASE | re.DOTALL,
        ),
        "critical",
        "ACE inhibitors are FDA Category X — absolutely contraindicated in pregnancy "
        "due to risk of fetal renal failure, oligohydramnios, and death.",
    ),
    # ARBs + pregnancy
    (
        re.compile(
            r"(losartan|valsartan|irbesartan|candesartan|arb\b)"
            r".*pregnan",
            re.IGNORECASE | re.DOTALL,
        ),
        "critical",
        "ARBs are contraindicated in pregnancy (same fetal toxicity as ACE inhibitors).",
    ),
    # Warfarin + pregnancy
    (
        re.compile(r"warfarin.*pregnan", re.IGNORECASE | re.DOTALL),
        "critical",
        "Warfarin is teratogenic (FDA Category X) — causes warfarin embryopathy.",
    ),
    # Metformin + severe renal failure (eGFR <30 / stage 4-5 / dialysis)
    (
        re.compile(
            r"metformin.*("
            r"egfr\s*(below|under|<|less\s*than)\s*(15|20|25|30)"
            r"|stage\s*(4|5|IV|V)\s*(ckd|kidney)"
            r"|dialysis|end.stage\s*renal"
            r")",
            re.IGNORECASE | re.DOTALL,
        ),
        "critical",
        "Metformin is contraindicated when eGFR <30 mL/min due to lactic acidosis risk.",
    ),
    # Semaglutide + medullary thyroid carcinoma / MEN 2
    (
        re.compile(
            r"semaglutide.*(medullary\s*thyroid|MTC|MEN\s*2|multiple\s*endocrine\s*neoplasia)",
            re.IGNORECASE | re.DOTALL,
        ),
        "critical",
        "Semaglutide carries a BLACK BOX WARNING for thyroid C-cell tumors — "
        "contraindicated in patients with personal/family history of MTC or MEN 2.",
    ),
    # Supratherapeutic INR + adding antiplatelet/NSAID
    (
        re.compile(
            r"INR\s*(is|of|=|:)?\s*([4-9]|[1-9]\d)(\.\d+)?"
            r".*("
            r"aspirin|ibuprofen|naproxen|nsaid|antiplatelet"
            r")",
            re.IGNORECASE | re.DOTALL,
        ),
        "critical",
        "Adding antiplatelet/NSAID agents with supratherapeutic INR (>=4) "
        "carries extreme bleeding risk.",
    ),
]

# Patterns that should be at LEAST "high" even if LLM says moderate/low
HIGH_FLOOR_RULES: list[tuple[re.Pattern, str]] = [
    # Any drug + pregnancy (general)
    (
        re.compile(
            r"(drug|medication|medicine|metformin|warfarin|lisinopril|semaglutide|aspirin)"
            r".*pregnan",
            re.IGNORECASE | re.DOTALL,
        ),
        "Drug safety in pregnancy requires at minimum a high-risk classification "
        "due to potential fetal harm.",
    ),
    # Bleeding risk combinations
    (
        re.compile(
            r"(warfarin|coumadin).*(aspirin|ibuprofen|nsaid|antiplatelet|clopidogrel)"
            r"|(aspirin|ibuprofen|nsaid|antiplatelet|clopidogrel).*(warfarin|coumadin)",
            re.IGNORECASE | re.DOTALL,
        ),
        "Anticoagulant + antiplatelet/NSAID combinations carry significant bleeding risk.",
    ),
]

RISK_RANK = {"low": 0, "moderate": 1, "high": 2, "critical": 3, "unknown": -1}


# ── Drug coverage validation ────────────────────────────────────────

def get_indexed_drugs() -> set[str]:
    """Return the set of drug names present in the ChromaDB drug_labels collection."""
    try:
        client = get_chroma_client()
        collection = client.get_collection("drug_labels")
        results = collection.get(include=["metadatas"])
        drugs: set[str] = set()
        for meta in results.get("metadatas") or []:
            if meta and "drug_name" in meta:
                drugs.add(meta["drug_name"].lower())
        return drugs
    except Exception as exc:
        logger.warning("indexed_drugs_lookup_failed", error=str(exc))
        return set()


# Common drug names to scan for (broader than just our index)
COMMON_DRUGS: set[str] = {
    "metformin", "warfarin", "lisinopril", "semaglutide", "aspirin",
    "ibuprofen", "naproxen", "acetaminophen", "tylenol", "advil",
    "atorvastatin", "simvastatin", "amlodipine", "omeprazole",
    "losartan", "hydrochlorothiazide", "gabapentin", "prednisone",
    "amoxicillin", "azithromycin", "clopidogrel", "pantoprazole",
    "levothyroxine", "furosemide", "albuterol", "insulin",
    "glipizide", "glyburide", "pioglitazone", "sitagliptin",
    "empagliflozin", "dapagliflozin", "liraglutide", "dulaglutide",
    "rosuvastatin", "pravastatin", "valsartan", "enalapril",
    "ramipril", "captopril", "benazepril", "diltiazem", "verapamil",
    "digoxin", "apixaban", "rivaroxaban", "dabigatran", "heparin",
    "enoxaparin", "phenytoin", "carbamazepine", "valproic acid",
    "lithium", "sertraline", "fluoxetine", "escitalopram",
    "duloxetine", "bupropion", "tramadol", "morphine", "oxycodone",
    "hydrocodone", "fentanyl", "diazepam", "lorazepam", "alprazolam",
    "coumadin", "plavix", "eliquis", "xarelto", "penicillin",
    "celecoxib", "metoprolol",
}

# Chinese → English drug name map so Chinese queries are not
# mistakenly rejected as out-of-index, and so the retrieval pipeline
# (which indexes English FDA labels) can match Chinese drug names.
CN_DRUG_MAP: dict[str, str] = {
    "二甲双胍": "metformin", "格华止": "metformin",
    "华法林": "warfarin",
    "赖诺普利": "lisinopril",
    "司美格鲁肽": "semaglutide", "诺和泰": "semaglutide",
    "阿司匹林": "aspirin", "拜阿": "aspirin",
    "布洛芬": "ibuprofen",
    "萘普生": "naproxen",
    "对乙酰氨基酚": "acetaminophen", "扑热息痛": "acetaminophen", "泰诺": "acetaminophen",
    "阿托伐他汀": "atorvastatin", "立普妥": "atorvastatin",
    "辛伐他汀": "simvastatin",
    "氨氯地平": "amlodipine", "络活喜": "amlodipine",
    "奥美拉唑": "omeprazole",
    "氯沙坦": "losartan",
    "氢氯噻嗪": "hydrochlorothiazide",
    "加巴喷丁": "gabapentin",
    "泼尼松": "prednisone",
    "阿莫西林": "amoxicillin", "阿莫仙": "amoxicillin",
    "阿奇霉素": "azithromycin",
    "氯吡格雷": "clopidogrel", "波立维": "clopidogrel",
    "泮托拉唑": "pantoprazole",
    "左甲状腺素": "levothyroxine", "优甲乐": "levothyroxine",
    "呋塞米": "furosemide", "速尿": "furosemide",
    "胰岛素": "insulin",
    "格列吡嗪": "glipizide",
    "格列本脲": "glyburide",
    "恩格列净": "empagliflozin",
    "利拉鲁肽": "liraglutide",
    "瑞舒伐他汀": "rosuvastatin",
    "缬沙坦": "valsartan",
    "依那普利": "enalapril",
    "雷米普利": "ramipril",
    "地尔硫卓": "diltiazem",
    "维拉帕米": "verapamil",
    "地高辛": "digoxin",
    "阿哌沙班": "apixaban",
    "利伐沙班": "rivaroxaban",
    "达比加群": "dabigatran",
    "肝素": "heparin",
    "依诺肝素": "enoxaparin",
    "碳酸锂": "lithium", "锂盐": "lithium",
    "舍曲林": "sertraline",
    "氟西汀": "fluoxetine",
    "曲马多": "tramadol",
    "青霉素": "penicillin",
    "塞来昔布": "celecoxib",
    "美托洛尔": "metoprolol",
}

# Chinese clinical terms → English for retrieval compatibility
CN_CLINICAL_TERMS: dict[str, str] = {
    "禁忌症": "contraindications",
    "禁忌": "contraindications",
    "不良反应": "adverse effects",
    "副作用": "side effects",
    "相互作用": "drug interactions",
    "肾功能": "renal function",
    "肝功能": "hepatic function",
    "妊娠": "pregnancy",
    "孕妇": "pregnancy",
    "哺乳": "lactation",
    "剂量": "dosage",
    "用法": "administration",
    "警告": "warnings",
    "过敏": "allergy",
    "出血风险": "bleeding risk",
}


def normalize_query_language(query: str) -> str:
    """Translate Chinese drug names and clinical terms in a query to English
    so the retrieval pipeline (which indexes English FDA labels) can match.
    """
    if not query:
        return query
    result = query
    # Replace longer Chinese terms first to avoid partial overlaps.
    for cn, en in sorted(CN_DRUG_MAP.items(), key=lambda x: -len(x[0])):
        if cn in result:
            result = result.replace(cn, en)
    for cn, en in sorted(CN_CLINICAL_TERMS.items(), key=lambda x: -len(x[0])):
        if cn in result:
            result = result.replace(cn, en)
    return result


def extract_drug_names_from_query(query: str, known_drugs: set[str]) -> tuple[list[str], list[str]]:
    """Extract drug names from the query by matching against known indexed drugs
    and common drug names/patterns.

    Returns (found_drugs, missing_drugs).
    """
    query_lower = normalize_query_language(query).lower()

    all_known = known_drugs | COMMON_DRUGS

    found_in_index: list[str] = []
    missing_from_index: list[str] = []

    for drug in all_known:
        # ASCII-letter boundary (not Unicode \b, which treats CJK as \w and
        # breaks matches like "metformin的"). Ensures the drug name is not a
        # substring of a longer English word while still matching next to CJK.
        pattern = re.compile(rf"(?<![a-z]){re.escape(drug)}(?![a-z])", re.IGNORECASE)
        if pattern.search(query_lower):
            if drug.lower() in known_drugs:
                found_in_index.append(drug)
            else:
                missing_from_index.append(drug)

    # Also detect drug class references that map to specific drugs
    CLASS_MAP = {
        r"\bace\s*inhibitor": ("lisinopril", ["enalapril", "ramipril", "captopril", "benazepril"]),
        r"\bnsaid": ("aspirin", ["ibuprofen", "naproxen"]),
        r"\banticoagulant": ("warfarin", ["apixaban", "rivaroxaban"]),
        r"\bglp.?1": ("semaglutide", ["liraglutide", "dulaglutide"]),
        r"\bbiguanide": ("metformin", []),
        r"\barb\b": (None, ["losartan", "valsartan"]),
    }

    for class_pattern, (indexed_drug, other_drugs) in CLASS_MAP.items():
        if re.search(class_pattern, query_lower):
            if indexed_drug and indexed_drug not in found_in_index and indexed_drug not in missing_from_index:
                if indexed_drug.lower() in known_drugs:
                    found_in_index.append(indexed_drug)
                else:
                    missing_from_index.append(indexed_drug)

    return found_in_index, missing_from_index


# ── Critical risk escalation ────────────────────────────────────────

def check_critical_escalation(query: str) -> tuple[str | None, str | None]:
    """Check if the query matches any known critical contraindication pattern.

    Returns (required_risk_level, reason) or (None, None) if no match.
    """
    for pattern, risk_level, reason in CRITICAL_RULES:
        if pattern.search(query):
            logger.info(
                "critical_rule_matched",
                risk_level=risk_level,
                reason=reason[:80],
            )
            return risk_level, reason
    return None, None


def check_high_floor(query: str) -> tuple[str | None, str | None]:
    """Check if the query warrants at minimum a 'high' risk classification.

    Returns (minimum_risk, reason) or (None, None).
    """
    for pattern, reason in HIGH_FLOOR_RULES:
        if pattern.search(query):
            return "high", reason
    return None, None


# ── Pre-retrieval validation ────────────────────────────────────────

def is_query_valid(query: str, detected_drugs: list[str], missing_drugs: list[str]) -> tuple[bool, str]:
    """Check if query is valid for processing (has known drugs and reasonable dates)."""
    # 1. Date Validation
    years = map(int, re.findall(r"\b([12]\d{3})\b", query))
    for year in years:
        if year < 1960 or year > 2026:
            return False, f"Query contains an invalid year ({year}). Only dates between 1960 and 2026 are supported."
    
    # 2. Total Drug Misses
    if missing_drugs and not detected_drugs:
        return False, f"All specifically mentioned drugs ({', '.join(missing_drugs)}) are missing from our knowledge base."
        
    return True, ""


# ── Post-synthesis safety enforcement ───────────────────────────────

def enforce_safety_guardrails(
    query: str,
    assessment: SafetyAssessment,
    missing_drugs: list[str],
) -> SafetyAssessment:
    """Apply deterministic safety rules AFTER LLM synthesis.

    This is the last line of defense — it overrides the LLM when it
    under-classifies known dangerous scenarios and injects missing-drug
    disclaimers.
    """
    modified = False

    # 1. Enforce critical-level for absolute contraindications
    required_risk, critical_reason = check_critical_escalation(query)
    if required_risk:
        current_rank = RISK_RANK.get(assessment.risk_level, -1)
        required_rank = RISK_RANK.get(required_risk, -1)
        if current_rank < required_rank:
            logger.warning(
                "risk_escalated",
                original=assessment.risk_level,
                escalated_to=required_risk,
                reason=critical_reason[:80],
            )
            assessment.risk_level = required_risk
            # Prepend the safety reason to the summary
            assessment.summary = (
                f"SAFETY ESCALATION: {critical_reason} "
                f"Original assessment: {assessment.summary}"
            )
            if critical_reason not in assessment.contraindications:
                assessment.contraindications.insert(0, critical_reason)
            modified = True

    # 2. Enforce high-floor for risky combinations
    if not required_risk:  # Don't downgrade a critical
        floor_risk, floor_reason = check_high_floor(query)
        if floor_risk:
            current_rank = RISK_RANK.get(assessment.risk_level, -1)
            floor_rank = RISK_RANK.get(floor_risk, -1)
            if current_rank < floor_rank:
                logger.warning(
                    "risk_floor_applied",
                    original=assessment.risk_level,
                    floor=floor_risk,
                    reason=floor_reason[:80],
                )
                assessment.risk_level = floor_risk
                assessment.summary = (
                    f"RISK FLOOR APPLIED: {floor_reason} "
                    f"Original assessment: {assessment.summary}"
                )
                modified = True

    # 3. Inject missing-drug disclaimer
    if missing_drugs:
        disclaimer = (
            f"WARNING: The following drug(s) mentioned in the query are NOT in the "
            f"knowledge base and could NOT be verified: {', '.join(missing_drugs)}. "
            f"This assessment may be incomplete. Consult a pharmacist or physician "
            f"for information on these medications."
        )
        assessment.summary = f"{disclaimer} {assessment.summary}"
        # Cap confidence — you cannot be confident about drugs you have no data for
        assessment.confidence = min(assessment.confidence, 0.4)
        logger.warning(
            "missing_drug_disclaimer",
            missing=missing_drugs,
            capped_confidence=assessment.confidence,
        )
        modified = True

    if modified:
        logger.info("guardrails_applied", final_risk=assessment.risk_level)

    return assessment
