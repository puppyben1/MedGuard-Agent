"""Chinese display labels and translation helpers for the prescription UI.

Standalone module with NO dependencies on other pharmagent modules, so it
can be safely imported from anywhere (case_parser, prescription_checker,
graph, app) without risking circular imports.
"""

from __future__ import annotations

import re

# ── English → Chinese drug name map ─────────────────────────────────
# Mirrors the reverse of case_parser._CN_DRUG_MAP, with canonical names
# preferred over brand names when duplicates exist.
_EN_DRUG_MAP: dict[str, str] = {
    "metformin": "二甲双胍",
    "warfarin": "华法林",
    "lisinopril": "赖诺普利",
    "semaglutide": "司美格鲁肽",
    "aspirin": "阿司匹林",
    "ibuprofen": "布洛芬",
    "naproxen": "萘普生",
    "acetaminophen": "对乙酰氨基酚",
    "atorvastatin": "阿托伐他汀",
    "simvastatin": "辛伐他汀",
    "amlodipine": "氨氯地平",
    "omeprazole": "奥美拉唑",
    "losartan": "氯沙坦",
    "hydrochlorothiazide": "氢氯噻嗪",
    "gabapentin": "加巴喷丁",
    "prednisone": "泼尼松",
    "amoxicillin": "阿莫西林",
    "azithromycin": "阿奇霉素",
    "clopidogrel": "氯吡格雷",
    "pantoprazole": "泮托拉唑",
    "levothyroxine": "左甲状腺素",
    "furosemide": "呋塞米",
    "insulin": "胰岛素",
    "glipizide": "格列吡嗪",
    "empagliflozin": "恩格列净",
    "liraglutide": "利拉鲁肽",
    "rosuvastatin": "瑞舒伐他汀",
    "valsartan": "缬沙坦",
    "enalapril": "依那普利",
    "ramipril": "雷米普利",
    "diltiazem": "地尔硫卓",
    "verapamil": "维拉帕米",
    "digoxin": "地高辛",
    "apixaban": "阿哌沙班",
    "rivaroxaban": "利伐沙班",
    "dabigatran": "达比加群",
    "heparin": "肝素",
    "enoxaparin": "依诺肝素",
    "lithium": "碳酸锂",
    "sertraline": "舍曲林",
    "fluoxetine": "氟西汀",
    "tramadol": "曲马多",
    "glyburide": "格列本脲",
    "penicillin": "青霉素",
    "celecoxib": "塞来昔布",
    "captopril": "卡托普利",
    "benazepril": "贝那普利",
    "perindopril": "培哚普利",
    "quinapril": "喹那普利",
    "trandolapril": "群多普利",
    "irbesartan": "厄贝沙坦",
    "candesartan": "坎地沙坦",
    "telmisartan": "替米沙坦",
    "olmesartan": "奥美沙坦",
    "eprosartan": "依普罗沙坦",
    "cephalexin": "头孢氨苄",
    "cefuroxime": "头孢呋辛",
    "ceftriaxone": "头孢曲松",
    "cephalosporin": "头孢菌素",
}

DIAGNOSIS_CN: dict[str, str] = {
    "atrial fibrillation": "房颤",
    "af": "房颤",
    "osteoporosis": "骨质疏松",
    "osteoarthritis": "骨关节炎",
    "type 2 diabetes": "2型糖尿病",
    "t2dm": "2型糖尿病",
    "type 2 diabetes mellitus": "2型糖尿病",
    "diabetes": "糖尿病",
    "hypertension": "高血压",
    "htn": "高血压",
    "chronic kidney disease": "慢性肾脏病",
    "ckd": "慢性肾脏病",
    "heart failure": "心力衰竭",
    "hf": "心力衰竭",
    "coronary artery disease": "冠心病",
    "cad": "冠心病",
    "deep vein thrombosis": "深静脉血栓",
    "dvt": "深静脉血栓",
    "pulmonary embolism": "肺栓塞",
    "pe": "肺栓塞",
    "stroke": "脑卒中",
    "hyperlipidemia": "高脂血症",
    "hyperthyroidism": "甲亢",
    "hypothyroidism": "甲减",
    "community-acquired pneumonia": "社区获得性肺炎",
    "pneumonia": "肺炎",
    "depression": "抑郁症",
    "anxiety": "焦虑症",
    "epilepsy": "癫痫",
    "gout": "痛风",
    "copd": "慢性阻塞性肺疾病",
    "asthma": "哮喘",
    "atrial flutter": "房扑",
    "peripheral arterial disease": "外周动脉疾病",
    "pad": "外周动脉疾病",
    "medullary thyroid cancer": "甲状腺髓样癌",
    "mtc": "甲状腺髓样癌",
}

SEX_CN = {"male": "男性", "female": "女性", "unknown": "未知"}
HEPATIC_CN = {
    "normal": "正常",
    "mild": "轻度异常",
    "moderate": "中度异常",
    "severe": "重度异常",
    "unknown": "未知",
}
FINDING_TYPE_CN = {
    "drug_interaction": "药物相互作用",
    "contraindication": "绝对禁忌",
    "dose_risk": "剂量风险",
    "renal_risk": "肾功能风险",
    "hepatic_risk": "肝功能风险",
    "pregnancy_risk": "妊娠风险",
    "allergy_risk": "过敏风险",
    "monitoring_required": "需要监测",
    "missing_evidence": "证据缺失",
}
SEVERITY_CN = {"low": "低", "moderate": "中", "high": "高", "critical": "严重"}

# Frequency English → Chinese
FREQ_CN = {
    "once daily": "每日一次", "qd": "每日一次", "q.d.": "每日一次",
    "twice daily": "每日两次", "bid": "每日两次", "b.i.d.": "每日两次",
    "three times daily": "每日三次", "tid": "每日三次", "t.i.d.": "每日三次",
    "four times daily": "每日四次", "qid": "每日四次",
    "as needed": "必要时", "prn": "必要时", "p.r.n.": "必要时",
    "every other day": "隔日一次", "qod": "隔日一次",
    "at bedtime": "睡前", "hs": "睡前",
}


def cn_drug_name(name: str) -> str:
    """Translate an English generic drug name to Chinese for display."""
    if not name:
        return name
    key = name.strip().lower()
    return _EN_DRUG_MAP.get(key, name)


def cn_diagnosis(text: str) -> str:
    """Translate a diagnosis string to Chinese for display."""
    if not text:
        return text
    lower = text.strip().lower()
    if lower in DIAGNOSIS_CN:
        return DIAGNOSIS_CN[lower]
    result = text
    for en, cn in sorted(DIAGNOSIS_CN.items(), key=lambda x: -len(x[0])):
        if en in result.lower():
            result = re.sub(re.escape(en), cn, result, flags=re.IGNORECASE)
    return result


def cn_sex(sex: str) -> str:
    return SEX_CN.get(sex, sex)


def cn_hepatic(val: str) -> str:
    return HEPATIC_CN.get(val, val)


def cn_freq(freq: str) -> str:
    if not freq:
        return ""
    lower = freq.strip().lower()
    return FREQ_CN.get(lower, freq)
