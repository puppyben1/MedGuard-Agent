"""Rule + evidence scaffold for higher-order polypharmacy risk analysis."""

from __future__ import annotations

from itertools import combinations

from pharmagent.adr.interaction_evidence import match_interaction_evidence
from pharmagent.adr.schemas import (
    HigherOrderRisk,
    Neo4jGraphPreview,
    Neo4jNode,
    Neo4jRelationship,
    PairwiseInteraction,
    PolypharmacyAnalyzeRequest,
    PolypharmacyRecommendation,
    PolypharmacyReport,
    Severity,
    SingleDrugRisk,
)
from pharmagent.adr.side_effect_rag import SideEffectSearchRequest, search_side_effects

RISK_RANK: dict[Severity, int] = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
ANTICOAGULANTS = {"warfarin", "rivaroxaban", "apixaban", "dabigatran", "heparin"}
NSAIDS = {"ibuprofen", "naproxen", "diclofenac", "celecoxib", "aspirin"}
ANTIPLATELETS = {"aspirin", "clopidogrel", "ticagrelor"}
ACE_ARB = {"lisinopril", "enalapril", "losartan", "valsartan"}
DIURETICS = {"hydrochlorothiazide", "furosemide", "spironolactone"}
RENAL_STRESSORS = NSAIDS | ACE_ARB | DIURETICS
PPI = {"omeprazole", "pantoprazole", "esomeprazole"}


def analyze_polypharmacy(req: PolypharmacyAnalyzeRequest) -> PolypharmacyReport:
    drugs = _normalize_drugs(req.drugs)
    if len(drugs) < 2:
        raise ValueError("至少需要输入 2 个药物")

    single = _single_drug_risks(drugs)
    pairwise = _pairwise_interactions(drugs)
    external_pairwise = _external_pairwise_interactions(drugs, req.external_evidence_path)
    pairwise.extend(external_pairwise)
    higher = _higher_order_risks(drugs, req)
    recommendations = _recommendations(pairwise, higher)
    graph = _mechanism_graph(drugs, single, pairwise, higher)
    all_severities = [item.severity for item in single] + [item.severity for item in pairwise] + [item.severity for item in higher]

    return PolypharmacyReport(
        source_type="rules_rag_faers_graph_external_interactions" if external_pairwise else "rules_rag_faers_graph",
        overall_risk_level=max(all_severities or ["low"], key=lambda item: RISK_RANK[item]),
        drugs=drugs,
        patient=req.patient,
        single_drug_risks=single,
        pairwise_interactions=pairwise,
        higher_order_risks=higher,
        mechanism_graph=graph,
        recommendations=recommendations,
        limitations=[
            "该模块为规则 + 本地证据检索的第一版高阶多药分析，不是 HODDI 模型或临床验证风险预测模型。",
            "FAERS/SIDER/MedDRA 证据表示报告关联或已知副作用知识，不证明个体因果关系。",
            "未输出风险增幅百分比；当前只给出分级、机制解释和可审计来源。",
        ],
    )


def _normalize_drugs(drugs: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for drug in drugs:
        item = " ".join(drug.strip().lower().split())
        if item and item not in seen:
            seen.add(item)
            normalized.append(item)
    return normalized


def _single_drug_risks(drugs: list[str]) -> list[SingleDrugRisk]:
    risks: list[SingleDrugRisk] = []
    for drug in drugs:
        if drug in ANTICOAGULANTS:
            risks.append(_single(drug, "bleeding", "high", "抗凝药存在出血风险，合并 NSAID/抗血小板药时风险更突出。"))
        elif drug in NSAIDS:
            risks.append(_single(drug, "gastrointestinal bleeding / acute kidney injury", "moderate", "NSAID 可增加胃肠道出血和肾损伤风险。"))
        elif drug == "metformin":
            risks.append(_single(drug, "lactic acidosis", "moderate", "肾功能下降时二甲双胍相关乳酸酸中毒风险升高。"))
        elif drug in PPI:
            risks.append(_single(drug, "gastroprotection context", "low", "PPI 可降低部分上消化道损伤风险，但不抵消抗凝相关系统性出血风险。"))

        rag_hit = _rag_single_risk(drug)
        if rag_hit:
            risks.append(rag_hit)
    return _dedupe_single(risks)


def _single(drug: str, risk: str, severity: Severity, rationale: str) -> SingleDrugRisk:
    return SingleDrugRisk(drug=drug, risk=risk, severity=severity, evidence_source="clinical_rule", rationale=rationale)


def _rag_single_risk(drug: str) -> SingleDrugRisk | None:
    try:
        result = search_side_effects(SideEffectSearchRequest(drug=drug, top_k=1))
    except Exception:  # noqa: BLE001
        return None
    if not result.hits:
        return None
    effect = result.hits[0].matched_side_effects[0] if result.hits[0].matched_side_effects else {}
    term = str(effect.get("term") or "SIDER/MedDRA side-effect association")
    return SingleDrugRisk(
        drug=drug,
        risk=term,
        severity="low",
        evidence_source="SIDER/MedDRA offline RAG",
        rationale=f"本地 SIDER/MedDRA 命中 {drug} 与 {term} 的副作用关联；该证据不代表个体因果关系。",
    )


def _dedupe_single(risks: list[SingleDrugRisk]) -> list[SingleDrugRisk]:
    deduped: dict[tuple[str, str], SingleDrugRisk] = {}
    for risk in risks:
        key = (risk.drug, risk.risk)
        current = deduped.get(key)
        if current is None or RISK_RANK[risk.severity] > RISK_RANK[current.severity]:
            deduped[key] = risk
    return list(deduped.values())


def _pairwise_interactions(drugs: list[str]) -> list[PairwiseInteraction]:
    interactions: list[PairwiseInteraction] = []
    for left, right in combinations(drugs, 2):
        pair = {left, right}
        if pair & ANTICOAGULANTS and pair & (NSAIDS | ANTIPLATELETS):
            interactions.append(
                PairwiseInteraction(
                    drugs=[left, right],
                    risk="major bleeding",
                    severity="high",
                    mechanism="抗凝效应叠加血小板/胃黏膜损伤，增加胃肠道或全身出血报告关联。",
                    evidence_source="clinical_rule + optional FAERS offline signal",
                    recommendation="避免非必要合用；如必须使用，评估替代镇痛方案并加强 INR/出血监测。",
                )
            )
        if pair <= RENAL_STRESSORS and len(pair & NSAIDS) == 1 and len(pair & (ACE_ARB | DIURETICS)) == 1:
            interactions.append(
                PairwiseInteraction(
                    drugs=[left, right],
                    risk="acute kidney injury",
                    severity="moderate",
                    mechanism="NSAID 影响入球小动脉，ACEI/ARB 或利尿剂改变肾灌注储备。",
                    evidence_source="clinical_rule",
                    recommendation="检查基线 eGFR/肌酐，避免脱水状态合用并安排复查。",
                )
            )
    return interactions


def _external_pairwise_interactions(drugs: list[str], source_path: str = "") -> list[PairwiseInteraction]:
    interactions: list[PairwiseInteraction] = []
    for record in match_interaction_evidence(drugs, source_path):
        interactions.append(
            PairwiseInteraction(
                drugs=record.drugs,
                risk=record.risk,
                severity=record.severity,
                mechanism=record.mechanism or "User-provided external interaction evidence.",
                evidence_source=f"{record.evidence_source} ({record.source_type})",
                recommendation=record.recommendation
                or "Review this interaction against patient-specific dose, indication, labs, and alternatives.",
            )
        )
    return interactions


def _higher_order_risks(drugs: list[str], req: PolypharmacyAnalyzeRequest) -> list[HigherOrderRisk]:
    drug_set = set(drugs)
    risks: list[HigherOrderRisk] = []
    age = req.patient.age or 0
    egfr = req.patient.eGFR
    diagnoses = " ".join(req.patient.diagnoses).lower()

    if drug_set & ANTICOAGULANTS and drug_set & NSAIDS and (age >= 65 or "atrial fibrillation" in diagnoses or "房颤" in diagnoses):
        severity: Severity = "critical" if age >= 75 else "high"
        risks.append(
            HigherOrderRisk(
                drugs=sorted(drug_set & (ANTICOAGULANTS | NSAIDS | PPI)),
                risk="higher-order bleeding vulnerability",
                severity=severity,
                mechanism="抗凝暴露 + NSAID 胃黏膜/血小板效应 + 高龄/房颤抗凝背景共同形成出血脆弱性。",
                evidence_level="rule_supported",
                rationale="规则证据支持高阶风险；PPI 只能部分保护上消化道，不消除抗凝相关出血。",
            )
        )

    if drug_set & NSAIDS and drug_set & ACE_ARB and drug_set & DIURETICS:
        severity = "critical" if egfr is not None and egfr < 60 else "high"
        risks.append(
            HigherOrderRisk(
                drugs=sorted(drug_set & (NSAIDS | ACE_ARB | DIURETICS)),
                risk="triple whammy acute kidney injury",
                severity=severity,
                mechanism="NSAID + ACEI/ARB + 利尿剂同时削弱肾灌注调节和容量稳定性。",
                evidence_level="rule_supported",
                rationale="三联用药满足经典 AKI 高阶风险模式；肾功能下降时进一步升级。",
            )
        )

    if "metformin" in drug_set and (egfr is not None and egfr < 30):
        risks.append(
            HigherOrderRisk(
                drugs=["metformin", *sorted(drug_set & RENAL_STRESSORS)],
                risk="metformin-associated lactic acidosis vulnerability",
                severity="critical",
                mechanism="严重肾功能下降降低二甲双胍清除；若合并肾灌注受损药物，乳酸酸中毒风险更需警惕。",
                evidence_level="rule_supported",
                rationale="患者 eGFR < 30，符合高危/禁忌场景；需结合临床状态立即评估。",
            )
        )

    return risks


def _recommendations(
    pairwise: list[PairwiseInteraction],
    higher: list[HigherOrderRisk],
) -> list[PolypharmacyRecommendation]:
    recommendations: list[PolypharmacyRecommendation] = []
    if any(item.severity == "critical" for item in higher):
        recommendations.append(
            PolypharmacyRecommendation(
                priority="immediate",
                text="立即进行药师/医生复核，优先处理 critical 高阶联用风险。",
                rationale="存在三联或患者因素叠加的严重风险模式。",
            )
        )
    if any(item.risk == "major bleeding" for item in pairwise):
        recommendations.append(
            PolypharmacyRecommendation(
                priority="soon",
                text="评估 NSAID/抗血小板药替代方案，并设置出血症状、血红蛋白和 INR 监测。",
                rationale="抗凝相关出血风险是当前组合中最明确的可干预风险。",
            )
        )
    if any("kidney" in item.risk or "renal" in item.risk for item in pairwise):
        recommendations.append(
            PolypharmacyRecommendation(
                priority="monitor",
                text="安排肌酐/eGFR 和容量状态复查，避免脱水、感染或造影剂暴露时继续高风险组合。",
                rationale="AKI 风险依赖患者状态，监测能尽早发现损害。",
            )
        )
    if not recommendations:
        recommendations.append(
            PolypharmacyRecommendation(
                priority="inform",
                text="未命中内置高阶风险规则；仍需结合适应证、剂量、肝肾功能和真实证据进一步评估。",
                rationale="未命中规则不代表无风险。",
            )
        )
    return recommendations


def _mechanism_graph(
    drugs: list[str],
    single: list[SingleDrugRisk],
    pairwise: list[PairwiseInteraction],
    higher: list[HigherOrderRisk],
) -> Neo4jGraphPreview:
    nodes: dict[str, Neo4jNode] = {}
    relationships: list[Neo4jRelationship] = []
    for drug in drugs:
        nodes[f"Drug:{drug}"] = Neo4jNode(id=f"Drug:{drug}", labels=["Drug"], properties={"name": drug})
    for risk in single:
        risk_id = f"ADR:{risk.risk}"
        nodes.setdefault(risk_id, Neo4jNode(id=risk_id, labels=["SideEffect"], properties={"term": risk.risk, "severity": risk.severity}))
        relationships.append(Neo4jRelationship(source=f"Drug:{risk.drug}", target=risk_id, type="HAS_SIDE_EFFECT", properties={"source": risk.evidence_source}))
    for item in pairwise:
        mechanism_id = f"Mechanism:{item.risk}"
        nodes[mechanism_id] = Neo4jNode(id=mechanism_id, labels=["Mechanism"], properties={"name": item.risk, "severity": item.severity})
        for drug in item.drugs:
            relationships.append(Neo4jRelationship(source=f"Drug:{drug}", target=mechanism_id, type="INCREASES_RISK", properties={"mechanism": item.mechanism}))
    for item in higher:
        risk_id = f"HigherOrder:{item.risk}"
        nodes[risk_id] = Neo4jNode(id=risk_id, labels=["Mechanism", "HigherOrderRisk"], properties={"name": item.risk, "severity": item.severity})
        for drug in item.drugs:
            if f"Drug:{drug}" in nodes:
                relationships.append(Neo4jRelationship(source=f"Drug:{drug}", target=risk_id, type="CONTRIBUTES_TO", properties={"evidence_level": item.evidence_level}))
    return Neo4jGraphPreview(nodes=list(nodes.values()), relationships=relationships, cypher_examples=[
        "MATCH p=(d:Drug)-[:CONTRIBUTES_TO|INCREASES_RISK]->(m:Mechanism) RETURN p;",
    ])
