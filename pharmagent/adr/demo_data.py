"""Local ADR demo cases and FAERS-like signal data for stable presentations."""

from __future__ import annotations

from pharmagent.adr.schemas import ADRExample, OpenFDASignal


ADR_DEMO_EXAMPLES: list[ADRExample] = [
    ADRExample(
        id="warfarin_ibuprofen_bleeding",
        label="华法林 + 布洛芬 -> 胃肠道出血",
        drug="warfarin",
        adr="gastrointestinal bleeding",
        case_text=(
            "患者，72 岁男性，因房颤长期服用华法林。近日因关节痛自行服用布洛芬，"
            "3 天后出现黑便、乏力。检查 INR 4.8，血红蛋白下降。"
            "停用布洛芬并调整华法林后症状改善。"
        ),
    ),
    ADRExample(
        id="metformin_ckd_lactic_acidosis",
        label="二甲双胍 + 严重肾功能不全 -> 乳酸酸中毒",
        drug="metformin",
        adr="lactic acidosis",
        case_text=(
            "68 岁男性，2 型糖尿病合并慢性肾脏病 4 期，eGFR 18。"
            "长期服用二甲双胍 1000mg 每日两次，近两日出现乏力、恶心、呼吸深快，"
            "乳酸升高。停用二甲双胍并纠正酸中毒后好转。"
        ),
    ),
    ADRExample(
        id="statin_rhabdomyolysis",
        label="他汀类 -> 横纹肌溶解",
        drug="atorvastatin",
        adr="rhabdomyolysis",
        case_text=(
            "61 岁男性，高脂血症，服用阿托伐他汀后出现明显肌痛、茶色尿，"
            "肌酸激酶 CK 显著升高。停药并补液治疗后肌痛缓解。"
        ),
    ),
    ADRExample(
        id="amiodarone_thyroid",
        label="胺碘酮 -> 甲状腺功能异常",
        drug="amiodarone",
        adr="thyroid dysfunction",
        case_text=(
            "70 岁女性，因心律失常长期服用胺碘酮。近期出现心悸、体重下降，"
            "甲状腺功能检查提示 TSH 降低、FT4 升高，考虑药物相关甲状腺功能异常。"
        ),
    ),
    ADRExample(
        id="ciprofloxacin_tendon",
        label="环丙沙星 -> 跟腱断裂",
        drug="ciprofloxacin",
        adr="tendon rupture",
        case_text=(
            "76 岁男性，因泌尿系感染使用环丙沙星。用药 5 天后出现跟腱疼痛，"
            "随后活动时发生跟腱断裂。既往有糖皮质激素使用史。"
        ),
    ),
    ADRExample(
        id="clozapine_agranulocytosis",
        label="氯氮平 -> 粒细胞缺乏",
        drug="clozapine",
        adr="agranulocytosis",
        case_text=(
            "45 岁男性，精神分裂症，服用氯氮平治疗。复查血常规发现白细胞和中性粒细胞"
            "显著下降，伴发热。停用氯氮平并给予升白治疗后逐渐恢复。"
        ),
    ),
    ADRExample(
        id="acetaminophen_liver_injury",
        label="对乙酰氨基酚 -> 肝损伤",
        drug="acetaminophen",
        adr="liver injury",
        case_text=(
            "39 岁女性，感冒后连续多日大剂量服用对乙酰氨基酚。随后出现恶心、右上腹不适，"
            "ALT 和 AST 明显升高。停药并护肝治疗后肝酶下降。"
        ),
    ),
    ADRExample(
        id="acei_nsaid_ckd_aki",
        label="ACEI/ARB + NSAID + CKD -> 急性肾损伤",
        drug="lisinopril",
        adr="acute kidney injury",
        case_text=(
            "70 岁女性，高血压合并 CKD 3a 期，eGFR 50。长期服用赖诺普利，"
            "近期因腰痛服用布洛芬，并合用氢氯噻嗪。1 周后肌酐升高、尿量减少，"
            "停用 NSAID 并补液后肾功能改善。"
        ),
    ),
]


LOCAL_FAERS_SIGNALS: dict[str, OpenFDASignal] = {
    "warfarin|gastrointestinal bleeding": OpenFDASignal(
        drug="warfarin",
        adr="gastrointestinal bleeding",
        report_count=18420,
        serious_count=13980,
        death_count=1260,
        hospitalization_count=8420,
        ror=7.8,
        prr=5.9,
        signal_level="strong",
        yearly_trend=[
            {"year": 2020, "reports": 2510},
            {"year": 2021, "reports": 2820},
            {"year": 2022, "reports": 3040},
            {"year": 2023, "reports": 3220},
            {"year": 2024, "reports": 3380},
            {"year": 2025, "reports": 3450},
        ],
        sex_distribution=[{"label": "男", "count": 9200}, {"label": "女", "count": 8420}],
        age_distribution=[
            {"label": "<45", "count": 980},
            {"label": "45-64", "count": 4320},
            {"label": "65-79", "count": 8120},
            {"label": "80+", "count": 5000},
        ],
        clinical_interpretation="华法林相关出血在 FAERS 中呈强报告信号，合用 NSAID 会进一步增加胃肠道出血风险。",
        limitations=["FAERS 自发报告只能提示报告关联，不能证明因果关系。", "报告数可能受到漏报、重复报告和适应证偏倚影响。"],
    ),
    "metformin|lactic acidosis": OpenFDASignal(
        drug="metformin",
        adr="lactic acidosis",
        report_count=6420,
        serious_count=5880,
        death_count=930,
        hospitalization_count=4120,
        ror=9.4,
        prr=6.7,
        signal_level="strong",
        yearly_trend=[
            {"year": 2020, "reports": 870},
            {"year": 2021, "reports": 920},
            {"year": 2022, "reports": 1010},
            {"year": 2023, "reports": 1120},
            {"year": 2024, "reports": 1210},
            {"year": 2025, "reports": 1290},
        ],
        sex_distribution=[{"label": "男", "count": 3520}, {"label": "女", "count": 2900}],
        age_distribution=[
            {"label": "<45", "count": 520},
            {"label": "45-64", "count": 1740},
            {"label": "65-79", "count": 2780},
            {"label": "80+", "count": 1380},
        ],
        clinical_interpretation="二甲双胍相关乳酸酸中毒虽少见但严重，严重肾功能不全是关键危险因素。",
        limitations=["本地演示数据用于稳定展示，需结合实时查询或原始 FAERS 分析确认。"],
    ),
    "atorvastatin|rhabdomyolysis": OpenFDASignal(
        drug="atorvastatin",
        adr="rhabdomyolysis",
        report_count=9280,
        serious_count=8010,
        death_count=510,
        hospitalization_count=3620,
        ror=6.3,
        prr=4.8,
        signal_level="strong",
        yearly_trend=[
            {"year": 2020, "reports": 1210},
            {"year": 2021, "reports": 1390},
            {"year": 2022, "reports": 1510},
            {"year": 2023, "reports": 1640},
            {"year": 2024, "reports": 1710},
            {"year": 2025, "reports": 1820},
        ],
        sex_distribution=[{"label": "男", "count": 5140}, {"label": "女", "count": 4140}],
        age_distribution=[
            {"label": "<45", "count": 820},
            {"label": "45-64", "count": 3020},
            {"label": "65-79", "count": 3820},
            {"label": "80+", "count": 1620},
        ],
        clinical_interpretation="他汀类与肌病、横纹肌溶解存在已知风险，应结合肌痛症状和 CK 监测判断。",
        limitations=["不同他汀、剂量和 CYP3A4 相互作用会显著改变个体风险。"],
    ),
    "amiodarone|thyroid dysfunction": OpenFDASignal(
        drug="amiodarone",
        adr="thyroid dysfunction",
        report_count=7340,
        serious_count=3840,
        death_count=180,
        hospitalization_count=1560,
        ror=5.5,
        prr=4.1,
        signal_level="strong",
        yearly_trend=[
            {"year": 2020, "reports": 980},
            {"year": 2021, "reports": 1080},
            {"year": 2022, "reports": 1190},
            {"year": 2023, "reports": 1280},
            {"year": 2024, "reports": 1360},
            {"year": 2025, "reports": 1450},
        ],
        sex_distribution=[{"label": "男", "count": 3920}, {"label": "女", "count": 3420}],
        age_distribution=[
            {"label": "<45", "count": 360},
            {"label": "45-64", "count": 1620},
            {"label": "65-79", "count": 3560},
            {"label": "80+", "count": 1800},
        ],
        clinical_interpretation="胺碘酮含碘量高，甲状腺功能异常是长期治疗的重要监测点。",
        limitations=["需结合基线甲状腺疾病、用药时长和实验室检查解释。"],
    ),
    "ciprofloxacin|tendon rupture": OpenFDASignal(
        drug="ciprofloxacin",
        adr="tendon rupture",
        report_count=5120,
        serious_count=3660,
        death_count=35,
        hospitalization_count=980,
        ror=8.1,
        prr=5.6,
        signal_level="strong",
        yearly_trend=[
            {"year": 2020, "reports": 740},
            {"year": 2021, "reports": 810},
            {"year": 2022, "reports": 830},
            {"year": 2023, "reports": 880},
            {"year": 2024, "reports": 910},
            {"year": 2025, "reports": 950},
        ],
        sex_distribution=[{"label": "男", "count": 2860}, {"label": "女", "count": 2260}],
        age_distribution=[
            {"label": "<45", "count": 420},
            {"label": "45-64", "count": 1360},
            {"label": "65-79", "count": 2240},
            {"label": "80+", "count": 1100},
        ],
        clinical_interpretation="喹诺酮类与肌腱炎和跟腱断裂存在明确警示，老年和糖皮质激素使用者风险更高。",
        limitations=["病例中需确认外伤、运动负荷和合并激素使用。"],
    ),
    "clozapine|agranulocytosis": OpenFDASignal(
        drug="clozapine",
        adr="agranulocytosis",
        report_count=4380,
        serious_count=4210,
        death_count=420,
        hospitalization_count=2860,
        ror=12.6,
        prr=8.8,
        signal_level="strong",
        yearly_trend=[
            {"year": 2020, "reports": 590},
            {"year": 2021, "reports": 640},
            {"year": 2022, "reports": 710},
            {"year": 2023, "reports": 750},
            {"year": 2024, "reports": 820},
            {"year": 2025, "reports": 870},
        ],
        sex_distribution=[{"label": "男", "count": 2380}, {"label": "女", "count": 2000}],
        age_distribution=[
            {"label": "<45", "count": 1410},
            {"label": "45-64", "count": 1820},
            {"label": "65-79", "count": 900},
            {"label": "80+", "count": 250},
        ],
        clinical_interpretation="氯氮平相关粒细胞缺乏是严重且需常规血常规监测的经典 ADR。",
        limitations=["需结合中性粒细胞绝对计数、感染表现和用药时程判断。"],
    ),
    "acetaminophen|liver injury": OpenFDASignal(
        drug="acetaminophen",
        adr="liver injury",
        report_count=11860,
        serious_count=9460,
        death_count=1580,
        hospitalization_count=5020,
        ror=7.1,
        prr=5.2,
        signal_level="strong",
        yearly_trend=[
            {"year": 2020, "reports": 1540},
            {"year": 2021, "reports": 1690},
            {"year": 2022, "reports": 1880},
            {"year": 2023, "reports": 2050},
            {"year": 2024, "reports": 2260},
            {"year": 2025, "reports": 2440},
        ],
        sex_distribution=[{"label": "男", "count": 5480}, {"label": "女", "count": 6380}],
        age_distribution=[
            {"label": "<45", "count": 3920},
            {"label": "45-64", "count": 3860},
            {"label": "65-79", "count": 2840},
            {"label": "80+", "count": 1240},
        ],
        clinical_interpretation="对乙酰氨基酚过量或高风险人群可发生严重肝损伤，应关注剂量和 ALT/AST。",
        limitations=["需区分治疗剂量、过量、自伤摄入和合并饮酒等因素。"],
    ),
    "lisinopril|acute kidney injury": OpenFDASignal(
        drug="lisinopril",
        adr="acute kidney injury",
        report_count=6840,
        serious_count=5120,
        death_count=390,
        hospitalization_count=3180,
        ror=4.7,
        prr=3.5,
        signal_level="moderate",
        yearly_trend=[
            {"year": 2020, "reports": 920},
            {"year": 2021, "reports": 980},
            {"year": 2022, "reports": 1080},
            {"year": 2023, "reports": 1170},
            {"year": 2024, "reports": 1290},
            {"year": 2025, "reports": 1400},
        ],
        sex_distribution=[{"label": "男", "count": 3440}, {"label": "女", "count": 3400}],
        age_distribution=[
            {"label": "<45", "count": 480},
            {"label": "45-64", "count": 1640},
            {"label": "65-79", "count": 3040},
            {"label": "80+", "count": 1680},
        ],
        clinical_interpretation="ACEI/ARB 在 CKD、利尿剂和 NSAID 合用背景下可增加急性肾损伤风险。",
        limitations=["肾损伤风险高度依赖容量状态、基础肾功能和合并用药。"],
    ),
}


def get_demo_examples() -> list[ADRExample]:
    return ADR_DEMO_EXAMPLES


def find_demo_by_text(case_text: str) -> ADRExample | None:
    normalized = case_text.lower()
    for example in ADR_DEMO_EXAMPLES:
        if example.id in normalized or example.drug.lower() in normalized or example.adr.lower() in normalized:
            return example
    chinese_keys = {
        "华法林": "warfarin_ibuprofen_bleeding",
        "二甲双胍": "metformin_ckd_lactic_acidosis",
        "阿托伐他汀": "statin_rhabdomyolysis",
        "胺碘酮": "amiodarone_thyroid",
        "环丙沙星": "ciprofloxacin_tendon",
        "氯氮平": "clozapine_agranulocytosis",
        "对乙酰氨基酚": "acetaminophen_liver_injury",
        "赖诺普利": "acei_nsaid_ckd_aki",
    }
    for key, example_id in chinese_keys.items():
        if key in case_text:
            return next((ex for ex in ADR_DEMO_EXAMPLES if ex.id == example_id), None)
    return None


def get_local_signal(drug: str, adr: str) -> OpenFDASignal:
    key = f"{drug.lower()}|{adr.lower()}"
    if key in LOCAL_FAERS_SIGNALS:
        return LOCAL_FAERS_SIGNALS[key]
    for signal_key, signal in LOCAL_FAERS_SIGNALS.items():
        signal_drug, signal_adr = signal_key.split("|", 1)
        if drug.lower() in signal_drug or signal_drug in drug.lower():
            return signal
        if adr.lower() in signal_adr or signal_adr in adr.lower():
            return signal
    return OpenFDASignal(
        drug=drug,
        adr=adr,
        source_mode="local_demo",
        signal_level="weak",
        clinical_interpretation="未命中预置强信号案例，当前返回弱信号占位结果。",
        limitations=["本结果来自本地演示数据，建议启用实时 openFDA 查询进一步确认。"],
    )

