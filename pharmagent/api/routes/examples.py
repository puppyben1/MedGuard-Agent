"""Example cases and queries for the frontend."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ExampleCase(BaseModel):
    label: str
    text: str


PRESCRIPTION_EXAMPLES: list[ExampleCase] = [
    ExampleCase(
        label="妊娠 + ACEI（致畸禁忌）",
        text=(
            "32岁女性，妊娠 24 周，因高血压就诊。"
            "处方：赖诺普利 10mg 每日一次。无药物过敏史。eGFR 95。肝功能正常。"
        ),
    ),
    ExampleCase(
        label="二甲双胍 + 慢性肾病4期（乳酸酸中毒）",
        text=(
            "68岁男性，2型糖尿病，慢性肾脏病4期。eGFR 18 mL/min/1.73m^2。"
            "当前处方：二甲双胍 1000毫克 每日两次，格列吡嗪 5mg 每日一次。"
            "无药物过敏史。肝功能正常。"
        ),
    ),
    ExampleCase(
        label="华法林 + 阿司匹林 + 布洛芬（三重出血风险）",
        text=(
            "74岁男性，房颤，骨关节炎。INR 3.2。"
            "处方：华法林 5mg 每日一次，阿司匹林 81mg 每日一次，"
            "布洛芬 600mg 每日三次 必要时。eGFR 70。无过敏。"
        ),
    ),
    ExampleCase(
        label="司美格鲁肽 + MTC 家族史（禁忌）",
        text=(
            "55岁男性，2型糖尿病，BMI 34。家族史：甲状腺髓样癌（MTC）。"
            "处方：司美格鲁肽 0.25mg 皮下注射 每周一次。eGFR 80。无过敏。"
        ),
    ),
    ExampleCase(
        label="三联肾损伤（AKI 风险）",
        text=(
            "70岁女性，高血压，慢性肾脏病 3a 期（eGFR 50）。"
            "处方：赖诺普利 20mg 每日一次，布洛芬 600mg 每日三次 必要时，"
            "氢氯噻嗪 25mg 每日一次。无过敏。肝功能正常。"
        ),
    ),
    ExampleCase(
        label="阴性对照（无风险）",
        text=(
            "40岁男性，轻度高血压。处方：赖诺普利 10mg 每日一次。"
            "eGFR 100。无过敏。肝功能正常。未使用其他药物。"
        ),
    ),
]

QA_EXAMPLES: list[str] = [
    "肾功能不全患者使用二甲双胍的禁忌症有哪些？",
    "华法林与阿司匹林联用有哪些风险？",
    "司美格鲁肽对有胰腺炎病史的患者安全吗？",
    "赖诺普利的常见不良反应有哪些？",
    "68 岁 3 期 CKD 患者同时服用二甲双胍、赖诺普利和华法林是否安全？",
]


class ExamplesResponse(BaseModel):
    prescription_examples: list[ExampleCase]
    qa_examples: list[str]


@router.get("/examples", response_model=ExamplesResponse)
def get_examples() -> ExamplesResponse:
    return ExamplesResponse(
        prescription_examples=PRESCRIPTION_EXAMPLES,
        qa_examples=QA_EXAMPLES,
    )
