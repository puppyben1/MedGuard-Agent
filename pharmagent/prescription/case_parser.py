"""Parse a free-text clinical case into a structured PatientCase.

Uses an LLM as the primary parser with a deterministic regex fallback so
the prescription review workflow still works when the LLM call fails or
returns malformed JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from pharmagent.logging_config import get_logger
from pharmagent.prescription.schemas import DrugOrder, PatientCase

logger = get_logger(__name__)


CASE_PARSER_SYSTEM_PROMPT = """You are a clinical informatics parser. Extract a structured
patient case from the free-text description provided by the user.

Return a JSON object with EXACTLY these fields (omit nothing — use null / empty list when absent):
{
  "age": integer or null,
  "sex": "male" | "female" | "unknown",
  "weight_kg": number or null,
  "height_cm": number or null,
  "diagnoses": ["list of active diagnoses, e.g. 'type 2 diabetes', 'CKD stage 3'"],
  "allergies": ["list of drug allergies, e.g. 'penicillin'"],
  "pregnancy": true | false | null,
  "lactating": true | false | null,
  "egfr": number or null,
  "liver_function": "normal" | "mild" | "moderate" | "severe" | "unknown",
  "inr": number or null,
  "drugs": [
    {"name": "generic name", "dose": "e.g. 500 mg", "route": "oral", "frequency": "e.g. BID", "notes": ""}
  ]
}

Extraction rules:
- Use generic drug names (metformin, not Glucophage). Keep brand names in notes if mentioned.
- If a lab value is described qualitatively ('severe renal impairment', 'Child-Pugh B'),
  convert to the corresponding structured field (egfr estimate, liver_function level).
- 'CKD stage 3' → set egfr to ~45 if no exact number is given; 'stage 4' → ~22; 'stage 5' → ~10.
- For pregnancy: only set true/false if explicitly stated or clearly inferable (e.g. 'gravid 38 weeks');
  otherwise null.
- Do NOT invent labs. If absent, use null / 'unknown'.
- Respond ONLY with the JSON object, no surrounding prose."""


# ── LLM-based parser ────────────────────────────────────────────────

def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def parse_case_with_llm(case_text: str, llm: Any) -> PatientCase | None:
    """Primary path: ask the LLM to extract a structured case.

    Returns None if parsing fails so the caller can fall back to the
    regex extractor.
    """
    messages = [
        SystemMessage(content=CASE_PARSER_SYSTEM_PROMPT),
        HumanMessage(content=f"Case text:\n{case_text}"),
    ]

    try:
        response = llm.invoke(messages)
        content = _strip_code_fence(response.content)
        data = json.loads(content)
    except Exception as exc:
        logger.warning("case_parser_llm_failed", error=str(exc))
        return None

    try:
        drugs = [DrugOrder(**d) for d in data.get("drugs", [])]
        case = PatientCase(
            age=data.get("age"),
            sex=data.get("sex", "unknown"),
            weight_kg=data.get("weight_kg"),
            height_cm=data.get("height_cm"),
            diagnoses=data.get("diagnoses", []) or [],
            allergies=data.get("allergies", []) or [],
            pregnancy=data.get("pregnancy"),
            lactating=data.get("lactating"),
            egfr=data.get("egfr"),
            liver_function=data.get("liver_function", "unknown"),
            inr=data.get("inr"),
            drugs=drugs,
            raw_text=case_text,
            parse_confidence=0.9 if drugs else 0.6,
        )
        logger.info(
            "case_parsed_llm",
            drugs=len(case.drugs),
            diagnoses=len(case.diagnoses),
            egfr=case.egfr,
        )
        return case
    except Exception as exc:
        logger.warning("case_parser_validation_failed", error=str(exc))
        return None


# ── Deterministic fallback ──────────────────────────────────────────

_CKD_STAGE_EGFR = {
    "1": 90, "2": 65, "3a": 50, "3b": 35, "3": 45,
    "4": 22, "5": 10,
}

_DRUG_DOSE_RE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z\-]+)\s+(?P<dose>\d+(\.\d+)?\s*(?:mg|mcg|µg|g|ml|units?))\s*"
    r"(?P<route>po|oral|iv|im|sc|sl|topical|inhaled|pr)?\s*"
    r"(?P<freq>qd|od|bid|b\.i\.d|tid|t\.i\.d|qid|q\.i\.d|prn|q\d+h|once daily|twice daily|three times daily|daily)?",
    re.IGNORECASE,
)

_DRUG_NAMES_HINT = {
    "metformin", "warfarin", "lisinopril", "semaglutide", "aspirin",
    "ibuprofen", "naproxen", "acetaminophen", "atorvastatin", "simvastatin",
    "amlodipine", "omeprazole", "losartan", "hydrochlorothiazide", "gabapentin",
    "prednisone", "amoxicillin", "azithromycin", "clopidogrel", "pantoprazole",
    "levothyroxine", "furosemide", "insulin", "glipizide", "empagliflozin",
    "liraglutide", "rosuvastatin", "valsartan", "enalapril", "ramipril",
    "diltiazem", "verapamil", "digoxin", "apixaban", "rivaroxaban", "dabigatran",
    "heparin", "enoxaparin", "lithium", "sertraline", "fluoxetine", "tramadol",
}

# Chinese → English generic name mapping (covers common outpatient drugs).
# Keys include brand names and pinyin/hanzi forms seen in Chinese charts.
_CN_DRUG_MAP: dict[str, str] = {
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
}

# Chinese dose unit pattern: 药名 + 数字 + 毫克/微克/毫升/片/粒 + (可选)频次词
_CN_DOSE_RE = re.compile(
    r"(?P<name>[\u4e00-\u9fa5]{2,8})\s*(?P<dose>\d+(?:\.\d+)?\s*(?:毫克|微克|mg|片|粒|ml|毫升|单位))"
    r"\s*(?P<freq>每日一次|每日两次|每日三次|一天一次|一天两次|一天三次|每天一次|每天两次|每天三次|每日|每天|qd|bid|tid)?",
    re.IGNORECASE,
)

_CN_FREQ_MAP = {
    "每日一次": "qd", "每天一次": "qd", "一天一次": "qd",
    "每日两次": "bid", "每天两次": "bid", "一天两次": "bid",
    "每日三次": "tid", "每天三次": "tid", "一天三次": "tid",
    "每日": "qd", "每天": "qd",
}


def _extract_drugs_regex(text: str) -> list[DrugOrder]:
    """Fallback drug extraction using regex on dose patterns + known drug names.

    Handles both English (dose pattern + known name) and Chinese charts
    (hanzi name → generic via _CN_DRUG_MAP, with Chinese dose units).
    """
    text_lower = text.lower()
    found: dict[str, DrugOrder] = {}

    # Pass 1a: English dose patterns like "metformin 500 mg BID"
    for m in _DRUG_DOSE_RE.finditer(text):
        name = m.group("name").lower()
        if name in _DRUG_NAMES_HINT:
            found[name] = DrugOrder(
                name=name,
                dose=m.group("dose").strip(),
                route=(m.group("route") or "oral").lower(),
                frequency=(m.group("freq") or "").lower().replace(".", ""),
            )

    # Pass 1b: Chinese dose patterns like "二甲双胍 500毫克 每日两次"
    for m in _CN_DOSE_RE.finditer(text):
        cn_name = m.group("name")
        en_name = _CN_DRUG_MAP.get(cn_name)
        if en_name and en_name not in found:
            freq_raw = (m.group("freq") or "").strip()
            freq = _CN_FREQ_MAP.get(freq_raw, freq_raw.lower())
            found[en_name] = DrugOrder(
                name=en_name,
                dose=m.group("dose").strip(),
                route="oral",
                frequency=freq,
                notes=cn_name,
            )

    # Pass 2: English known drug names mentioned without explicit dose
    for drug in _DRUG_NAMES_HINT:
        if drug in found:
            continue
        if re.search(rf"\b{re.escape(drug)}\b", text_lower):
            found[drug] = DrugOrder(name=drug)

    # Pass 3: Chinese drug names mentioned without explicit dose
    for cn_name, en_name in _CN_DRUG_MAP.items():
        if en_name in found:
            continue
        if cn_name in text:
            found[en_name] = DrugOrder(name=en_name, notes=cn_name)

    return list(found.values())


def _extract_egfr_regex(text: str) -> float | None:
    text_lower = text.lower()
    # explicit eGFR number (English)
    m = re.search(r"egfr[^0-9]{0,10}(\d{1,3}(?:\.\d+)?)", text_lower)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # Chinese eGFR / 肾小球滤过率
    m = re.search(r"(?:egfr|肾小球滤过率|肾小球滤过|eGFR)[^0-9]{0,10}(\d{1,3}(?:\.\d+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # CKD stage mapping (English)
    m = re.search(r"ckd\s*stage\s*([12345]\w?)", text_lower)
    if m:
        stage = m.group(1)
        return _CKD_STAGE_EGFR.get(stage)
    # Chinese CKD stage: 慢性肾脏病/慢性肾病 3期 / 4期 / Ⅴ期
    m = re.search(r"(?:慢性肾脏病|慢性肾病|CKD)\s*([1-5Ⅰ-Ⅴ])[a-d期]?\s*期?", text)
    if m:
        stage = m.group(1)
        # normalize roman numerals
        roman_map = {"Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5"}
        stage = roman_map.get(stage, stage)
        return _CKD_STAGE_EGFR.get(stage)
    # qualitative renal impairment (English + Chinese)
    if re.search(r"severe\s*renal|esrd|dialysis", text_lower) or re.search(r"重度肾|终末期肾病|透析", text):
        return 10.0
    if re.search(r"moderate\s*renal", text_lower) or re.search(r"中度肾", text):
        return 30.0
    if re.search(r"mild\s*renal", text_lower) or re.search(r"轻度肾", text):
        return 60.0
    return None


def _extract_age_regex(text: str) -> int | None:
    # English: "68-year-old", "68yo male", "68 y/o"
    m = re.search(r"(\d{1,3})[\s-]*(?:year|yo|y/o|y\.o\.|yr)[- ]?(?:old)?\s*(?:male|female|man|woman|patient|gentleman|lady)?", text, re.IGNORECASE)
    if m:
        try:
            age = int(m.group(1))
            if 0 < age < 130:
                return age
        except ValueError:
            pass
    # Chinese: "68岁男性", "68岁女性", "68岁患者", "年龄68岁"
    m = re.search(r"(?:年龄\s*)?(\d{1,3})\s*岁\s*(?:男性|女性|患者|男|女)?", text)
    if m:
        try:
            age = int(m.group(1))
            if 0 < age < 130:
                return age
        except ValueError:
            pass
    return None


def _extract_sex_regex(text: str) -> str:
    text_lower = text.lower()
    if re.search(r"\b(male|man|gentleman|boy)\b", text_lower):
        return "male"
    if re.search(r"\b(female|woman|lady|girl)\b", text_lower):
        return "female"
    # Chinese
    if re.search(r"男性|(?<!\w)男(?![孩童子])", text):
        return "male"
    if re.search(r"女性|(?<!\w)女(?![孩童子])", text):
        return "female"
    return "unknown"


def _extract_pregnancy_regex(text: str) -> bool | None:
    text_lower = text.lower()
    # Negation must be checked BEFORE the affirmative pattern, since
    # "not pregnant" contains the substring "pregnan".
    if re.search(r"\bnot pregnant\b", text_lower):
        return False
    if re.search(r"pregnan|gravid|gestation|\bG\dP\d\b", text_lower):
        return True
    # Chinese
    if re.search(r"未孕|非孕", text):
        return False
    if re.search(r"怀孕|妊娠|孕\s*\d+\s*周|产妇|孕妇", text):
        return True
    return None


def _extract_liver_function_regex(text: str) -> str:
    text_lower = text.lower()
    if re.search(r"child.?pugh\s*c|severe hepatic|cirrhosis|decompensat", text_lower):
        return "severe"
    if re.search(r"child.?pugh\s*b|moderate hepatic", text_lower):
        return "moderate"
    if re.search(r"child.?pugh\s*a|mild hepatic|hepatitis", text_lower):
        return "mild"
    if re.search(r"normal liver|no hepatic|liver function normal", text_lower):
        return "normal"
    # Chinese
    if re.search(r"重度肝|肝硬化|失代偿|肝衰竭", text):
        return "severe"
    if re.search(r"中度肝", text):
        return "moderate"
    if re.search(r"轻度肝|肝炎", text):
        return "mild"
    if re.search(r"肝功能正常|肝脏正常|无肝功能异常", text):
        return "normal"
    return "unknown"


def _extract_inr_regex(text: str) -> float | None:
    m = re.search(r"\bINR\s*(?:is|of|=|:)?\s*(\d(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _extract_allergies_regex(text: str) -> list[str]:
    text_lower = text.lower()
    allergies: list[str] = []
    m = re.search(r"allerg(?:y|ies)[^:]*[:\-]?\s*([^.]+)", text_lower)
    if m:
        raw = m.group(1)
        for chunk in re.split(r",|;| and ", raw):
            chunk = chunk.strip()
            if 3 < len(chunk) < 40 and "no known" not in chunk and "nka" not in chunk:
                allergies.append(chunk)
    return allergies


def parse_case_with_regex(case_text: str) -> PatientCase:
    """Deterministic fallback parser. Always returns a PatientCase (possibly sparse)."""
    case = PatientCase(
        age=_extract_age_regex(case_text),
        sex=_extract_sex_regex(case_text),
        egfr=_extract_egfr_regex(case_text),
        liver_function=_extract_liver_function_regex(case_text),
        inr=_extract_inr_regex(case_text),
        pregnancy=_extract_pregnancy_regex(case_text),
        allergies=_extract_allergies_regex(case_text),
        drugs=_extract_drugs_regex(case_text),
        raw_text=case_text,
        parse_confidence=0.4,
    )
    logger.info(
        "case_parsed_regex",
        drugs=len(case.drugs),
        age=case.age,
        egfr=case.egfr,
    )
    return case


# ── Public entry point ──────────────────────────────────────────────

def parse_case(case_text: str, llm: Any | None = None) -> PatientCase:
    """Parse a free-text case into a structured PatientCase.

    Tries the LLM first; falls back to regex extraction on any failure.
    """
    if not case_text or not case_text.strip():
        return PatientCase(raw_text="", parse_confidence=0.0)

    if llm is not None:
        case = parse_case_with_llm(case_text, llm)
        if case is not None and case.drugs:
            return case
        # If LLM returned no drugs, try regex as a supplement before giving up
        if case is not None and not case.drugs:
            regex_drugs = _extract_drugs_regex(case_text)
            if regex_drugs:
                case.drugs = regex_drugs
                case.parse_confidence = max(case.parse_confidence, 0.7)
                return case

    return parse_case_with_regex(case_text)
