from __future__ import annotations

import json
from pathlib import Path

from pharmagent.adr.side_effect_rag import (
    SideEffectSearchRequest,
    build_side_effect_rag,
    search_side_effects,
    side_effect_rag_status,
)


def test_build_and_search_side_effect_rag_without_chroma(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "sider::CID1",
                        "drug_cid": "CID1",
                        "drug_name": "warfarin",
                        "side_effects": [
                            {
                                "term": "gastrointestinal bleeding",
                                "meddra_cui": "C002",
                                "level": "PT",
                                "frequency": 0.21,
                                "frequency_label": "21%",
                                "source_file": "meddra_freq.tsv.gz",
                            }
                        ],
                        "source_type": "offline_real_dataset",
                        "text": "Drug warfarin has SIDER/MedDRA side-effect associations including gastrointestinal bleeding.",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "id": "sider::CID2",
                        "drug_cid": "CID2",
                        "drug_name": "ibuprofen",
                        "side_effects": [
                            {
                                "term": "abdominal pain",
                                "meddra_cui": "C003",
                                "level": "PT",
                                "frequency": 0.05,
                                "frequency_label": "5%",
                                "source_file": "meddra_freq.tsv.gz",
                            }
                        ],
                        "source_type": "offline_real_dataset",
                        "text": "Drug ibuprofen has SIDER/MedDRA side-effect associations including abdominal pain.",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    status = build_side_effect_rag(source, tmp_path / "rag", build_chroma=False)
    assert status.available is True
    assert status.document_count == 2
    assert status.bm25_available is True
    assert status.chroma_available is False

    reloaded = side_effect_rag_status(tmp_path / "rag")
    assert reloaded.available is True

    response = search_side_effects(
        SideEffectSearchRequest(drug="warfarin", adr="bleeding", top_k=1),
        output_dir=tmp_path / "rag",
    )
    assert response.hits
    assert response.hits[0].drug_name == "warfarin"
    assert response.hits[0].source_type == "offline_real_dataset"
