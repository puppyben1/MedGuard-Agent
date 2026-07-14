"""Unit tests for pharmagent.prescription.case_parser regex fallback.

These tests exercise the deterministic regex extraction paths only — no LLM
calls — so they run offline without a Groq API key. They cover both English
and Chinese clinical-chart phrasing.
"""

from __future__ import annotations

import pytest

from pharmagent.prescription.case_parser import (
    _extract_age_regex,
    _extract_drugs_regex,
    _extract_egfr_regex,
    _extract_liver_function_regex,
    _extract_pregnancy_regex,
    _extract_sex_regex,
)


# ── Age ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("68-year-old male with T2DM", 68),
        ("74yo female, atrial fibrillation", 74),
        ("45 y/o man", 45),
        ("68岁男性，2型糖尿病", 68),
        ("年龄72岁女性患者", 72),
        ("Patient with diabetes", None),
    ],
)
def test_extract_age(text, expected):
    assert _extract_age_regex(text) == expected


# ── Sex ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("68-year-old male", "male"),
        ("45-year-old female", "female"),
        ("68岁男性", "male"),
        ("32岁女性", "female"),
        ("Patient with diabetes", "unknown"),
    ],
)
def test_extract_sex(text, expected):
    assert _extract_sex_regex(text) == expected


# ── eGFR / CKD ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("eGFR 18 mL/min", 18.0),
        ("CKD stage 4", 22.0),
        ("severe renal impairment, on dialysis", 10.0),
        ("慢性肾脏病4期", 22.0),
        ("慢性肾病3期", 45.0),
        ("eGFR 18 mL/min/1.73m^2", 18.0),
        ("No renal issues", None),
    ],
)
def test_extract_egfr(text, expected):
    assert _extract_egfr_regex(text) == expected


# ── Pregnancy ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("28-year-old pregnant female", True),
        ("G2P1 at 24 weeks gestation", True),
        ("妊娠24周", True),
        ("孕妇", True),
        ("not pregnant", False),
        ("Male patient", None),
    ],
)
def test_extract_pregnancy(text, expected):
    assert _extract_pregnancy_regex(text) == expected


# ── Liver function ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Child-Pugh C, cirrhosis", "severe"),
        ("Child-Pugh B", "moderate"),
        ("hepatitis, mild hepatic impairment", "mild"),
        ("肝硬化", "severe"),
        ("肝功能正常", "normal"),
        ("No liver disease mentioned", "unknown"),
    ],
)
def test_extract_liver_function(text, expected):
    assert _extract_liver_function_regex(text) == expected


# ── Drug extraction ────────────────────────────────────────────────────
def test_extract_drugs_english_with_dose():
    drugs = _extract_drugs_regex("metformin 1000 mg BID, lisinopril 10 mg daily")
    names = {d.name for d in drugs}
    assert "metformin" in names
    assert "lisinopril" in names
    met = next(d for d in drugs if d.name == "metformin")
    assert "1000" in met.dose
    assert met.frequency == "bid"


def test_extract_drugs_english_name_only():
    drugs = _extract_drugs_regex("Patient takes warfarin and aspirin")
    names = {d.name for d in drugs}
    assert "warfarin" in names
    assert "aspirin" in names


def test_extract_drugs_chinese_with_dose():
    drugs = _extract_drugs_regex(
        "处方：二甲双胍 1000毫克 每日两次，格列吡嗪 5mg 每日一次"
    )
    by_name = {d.name: d for d in drugs}
    assert "metformin" in by_name
    assert "glipizide" in by_name
    met = by_name["metformin"]
    assert "1000" in met.dose
    assert met.frequency == "bid"
    # Chinese source name preserved in notes for traceability
    assert "二甲双胍" in met.notes


def test_extract_drugs_chinese_name_only():
    drugs = _extract_drugs_regex("患者长期服用华法林和阿司匹林")
    names = {d.name for d in drugs}
    assert "warfarin" in names
    assert "aspirin" in names


def test_extract_drugs_chinese_full_case():
    """End-to-end Chinese chart phrasing for the CKD4 golden case."""
    text = (
        "68岁男性，2型糖尿病，慢性肾脏病4期。eGFR 18 mL/min/1.73m^2。"
        "当前处方：二甲双胍 1000毫克 每日两次，格列吡嗪 5mg 每日一次。"
    )
    drugs = _extract_drugs_regex(text)
    by_name = {d.name: d for d in drugs}
    assert "metformin" in by_name
    assert "glipizide" in by_name
    assert by_name["metformin"].frequency == "bid"
