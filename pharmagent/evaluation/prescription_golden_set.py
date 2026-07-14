"""Golden prescription review cases with ground-truth expected findings.

Each case pairs a free-text clinical scenario with the findings a
pharmacist would be expected to flag. The evaluation harness uses these
expected findings to compute Precision / Recall / F1.

A finding is counted as a match when:
  - finding_type matches, AND
  - the drug sets overlap (intersection non-empty), AND
  - severity matches OR the produced severity is at least as severe
    (we never penalize the system for being more cautious than ground truth).

Cases are designed to stress each risk axis:
  1. pregnancy teratogenicity (ACE inhibitor)
  2. renal contraindication (metformin + severe CKD)
  3. triple bleeding combination (warfarin + aspirin + ibuprofen)
  4. black-box warning (semaglutide + MTC family history)
  5. allergy cross-reactivity (penicillin allergy + amoxicillin)
  6. triple-whammy renal (NSAID + ACE inhibitor + impaired eGFR)
  7. negative control — stable patient, no findings expected (FP test)
"""

from __future__ import annotations

from typing import Literal


# Type alias mirroring PrescriptionFinding.severity
Severity = Literal["low", "moderate", "high", "critical"]


def _expected(
    finding_type: str,
    severity: Severity,
    drugs: list[str],
    keyword: str = "",
) -> dict:
    return {
        "finding_type": finding_type,
        "severity": severity,
        "drugs_involved": [d.lower() for d in drugs],
        "keyword": keyword,  # optional extra signal for keyword-based recall check
    }


PRESCRIPTION_GOLDEN_CASES: list[dict] = [
    # ── Case 1: ACE inhibitor in pregnancy ──────────────────────────
    {
        "id": "case_01_pregnancy_acei",
        "case_text": (
            "32-year-old female, currently 24 weeks pregnant, presents for hypertension management. "
            "Started on lisinopril 10 mg daily. No known drug allergies. eGFR 95 mL/min. "
            "No hepatic impairment."
        ),
        "expected_findings": [
            _expected("contraindication", "critical", ["lisinopril"], keyword="pregnan"),
        ],
    },

    # ── Case 2: Metformin in severe CKD ─────────────────────────────
    {
        "id": "case_02_metformin_severe_ckd",
        "case_text": (
            "68-year-old male with type 2 diabetes and CKD stage 4. eGFR 18 mL/min/1.73m^2. "
            "Current prescription: metformin 1000 mg BID, glipizide 5 mg daily. "
            "No known allergies. Liver function normal."
        ),
        "expected_findings": [
            _expected("contraindication", "critical", ["metformin"], keyword="lactic acidosis"),
        ],
    },

    # ── Case 3: Triple bleeding combination ─────────────────────────
    {
        "id": "case_03_warfarin_aspirin_ibuprofen",
        "case_text": (
            "74-year-old male with atrial fibrillation and osteoarthritis. "
            "Prescription: warfarin 5 mg daily (INR 3.2), aspirin 81 mg daily, "
            "ibuprofen 600 mg TID PRN for joint pain. eGFR 70. No allergies."
        ),
        "expected_findings": [
            _expected("drug_interaction", "high", ["warfarin", "aspirin"], keyword="bleeding"),
            _expected("drug_interaction", "high", ["warfarin", "ibuprofen"], keyword="GI bleeding"),
        ],
    },

    # ── Case 4: Semaglutide + MTC family history ────────────────────
    {
        "id": "case_04_semaglutide_mtc",
        "case_text": (
            "55-year-old female with type 2 diabetes and strong family history of "
            "medullary thyroid carcinoma (MEN 2). Prescription: semaglutide 1 mg weekly. "
            "eGFR 80. No allergies."
        ),
        "expected_findings": [
            _expected("contraindication", "critical", ["semaglutide"], keyword="thyroid"),
        ],
    },

    # ── Case 5: Penicillin allergy + amoxicillin ────────────────────
    {
        "id": "case_05_penicillin_allergy_amoxicillin",
        "case_text": (
            "45-year-old male with community-acquired pneumonia. "
            "Allergy: penicillin (anaphylaxis). Prescription: amoxicillin 500 mg TID, "
            "azithromycin 500 mg daily. eGFR 90. Liver normal."
        ),
        "expected_findings": [
            _expected("allergy_risk", "critical", ["amoxicillin"], keyword="penicillin"),
        ],
    },

    # ── Case 6: NSAID + ACE inhibitor + impaired eGFR (triple-whammy) ──
    {
        "id": "case_06_triple_whammy_renal",
        "case_text": (
            "70-year-old female with hypertension, CKD stage 3a (eGFR 50). "
            "Prescription: lisinopril 20 mg daily, ibuprofen 400 mg TID, "
            "hydrochlorothiazide 25 mg daily. Allergies: none. Liver normal."
        ),
        "expected_findings": [
            _expected("renal_risk", "moderate", ["lisinopril", "ibuprofen"], keyword="AKI"),
        ],
    },

    # ── Case 7: Negative control — no findings expected ─────────────
    {
        "id": "case_07_negative_control",
        "case_text": (
            "40-year-old male with mild hypertension. Prescription: lisinopril 10 mg daily. "
            "eGFR 100. No allergies. Liver normal. Not on any other medications."
        ),
        "expected_findings": [],
    },

    # ── Case 8 (Chinese): 二甲双胍 + 慢性肾病4期 ───────────────────
    # Stress-tests the Chinese case_parser fallback path.
    {
        "id": "case_08_cn_metformin_ckd4",
        "case_text": (
            "68岁男性，2型糖尿病，慢性肾脏病4期。eGFR 18 mL/min/1.73m^2。"
            "当前处方：二甲双胍 1000毫克 每日两次，格列吡嗪 5mg 每日一次。"
            "无药物过敏史。肝功能正常。"
        ),
        "expected_findings": [
            _expected("contraindication", "critical", ["metformin"], keyword="lactic acidosis"),
        ],
    },

    # ── Case 9 (Chinese): 华法林 + 阿司匹林 + 布洛芬（三重出血风险）─
    {
        "id": "case_09_cn_warfarin_aspirin_ibuprofen",
        "case_text": (
            "74岁男性，房颤，骨关节炎。INR 3.2。"
            "处方：华法林 5mg 每日一次，阿司匹林 81mg 每日一次，"
            "布洛芬 600mg 每日三次 必要时。eGFR 70。无过敏。"
        ),
        "expected_findings": [
            _expected("drug_interaction", "high", ["warfarin", "aspirin"], keyword="bleeding"),
            _expected("drug_interaction", "high", ["warfarin", "ibuprofen"], keyword="GI bleeding"),
        ],
    },

    # ── Case 10 (Chinese): 妊娠 + 赖诺普利（致畸禁忌）──────────────
    {
        "id": "case_10_cn_pregnancy_acei",
        "case_text": (
            "32岁女性，妊娠24周，高血压。处方：赖诺普利 10mg 每日一次。"
            "无过敏。eGFR 95。肝功能正常。"
        ),
        "expected_findings": [
            _expected("contraindication", "critical", ["lisinopril"], keyword="pregnan"),
        ],
    },
]
