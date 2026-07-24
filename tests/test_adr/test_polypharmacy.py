from __future__ import annotations

import pytest

from pharmagent.adr.interaction_evidence import interaction_evidence_status
from pharmagent.adr.polypharmacy import analyze_polypharmacy
from pharmagent.adr.schemas import PolypharmacyAnalyzeRequest, PolypharmacyPatient


def test_polypharmacy_detects_higher_order_bleeding_risk() -> None:
    report = analyze_polypharmacy(
        PolypharmacyAnalyzeRequest(
            drugs=["warfarin", "ibuprofen", "omeprazole"],
            patient=PolypharmacyPatient(age=78, diagnoses=["atrial fibrillation"]),
        )
    )

    assert report.overall_risk_level == "critical"
    assert any(item.risk == "major bleeding" for item in report.pairwise_interactions)
    assert any(item.risk == "higher-order bleeding vulnerability" for item in report.higher_order_risks)
    assert report.mechanism_graph.nodes
    assert report.recommendations[0].priority == "immediate"
    assert any("不证明个体因果关系" in item for item in report.limitations)


def test_polypharmacy_requires_at_least_two_drugs() -> None:
    with pytest.raises(ValueError, match="至少需要输入 2 个药物"):
        analyze_polypharmacy(PolypharmacyAnalyzeRequest(drugs=["warfarin"]))


def test_polypharmacy_merges_external_interaction_evidence(tmp_path) -> None:
    evidence_path = tmp_path / "drug_interactions.csv"
    evidence_path.write_text(
        "drug_a,drug_b,risk,severity,mechanism,evidence_source,recommendation\n"
        "warfarin,amiodarone,bleeding,high,CYP interaction may increase anticoagulant exposure,DrugBank-style unit file,Monitor INR closely\n",
        encoding="utf-8",
    )

    report = analyze_polypharmacy(
        PolypharmacyAnalyzeRequest(
            drugs=["warfarin", "amiodarone"],
            external_evidence_path=str(evidence_path),
        )
    )

    assert report.source_type == "rules_rag_faers_graph_external_interactions"
    assert any(item.evidence_source.startswith("DrugBank-style unit file") for item in report.pairwise_interactions)
    assert any(item.risk == "bleeding" for item in report.pairwise_interactions)

    status = interaction_evidence_status(str(evidence_path))
    assert status.available is True
    assert status.record_count == 1
