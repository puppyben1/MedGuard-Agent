from __future__ import annotations

import gzip
import json
import zipfile
from pathlib import Path

from pharmagent.adr.sider_index import build_sider_meddra_index


def test_build_sider_meddra_index_generates_rag_and_neo4j_artifacts(tmp_path: Path) -> None:
    zip_path = tmp_path / "adr_data.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("drug_names.tsv", "CID1\twarfarin\nCID2\tibuprofen\n")
        zf.writestr(
            "meddra_all_se.tsv.gz",
            gzip.compress(
                (
                    "CID1\tSTITCH1\tC001\tLLT\tC001\tBleeding\n"
                    "CID1\tSTITCH1\tC001\tPT\tC002\tGastrointestinal bleeding\n"
                    "CID2\tSTITCH2\tC003\tPT\tC003\tAbdominal pain\n"
                ).encode("utf-8")
            ),
        )
        zf.writestr(
            "meddra_freq.tsv.gz",
            gzip.compress(
                (
                    "CID1\tSTITCH1\tC001\t\t21%\t0.21\t0.21\tPT\tC002\tGastrointestinal bleeding\n"
                    "CID2\tSTITCH2\tC003\t\t5%\t0.05\t0.05\tPT\tC003\tAbdominal pain\n"
                ).encode("utf-8")
            ),
        )

    manifest = build_sider_meddra_index(zip_path, tmp_path / "out")

    assert manifest.drug_count == 2
    assert manifest.side_effect_count == 3
    assert manifest.relationship_count == 2
    assert manifest.rag_document_count == 2

    rag_path = Path(manifest.files["rag_documents"])
    docs = [json.loads(line) for line in rag_path.read_text(encoding="utf-8").splitlines()]
    assert docs[0]["source_type"] == "offline_real_dataset"
    assert docs[0]["drug_name"] == "warfarin"
    assert docs[0]["side_effects"][0]["meddra_cui"] == "C002"

    assert Path(manifest.files["drugs_csv"]).read_text(encoding="utf-8").startswith("cid,name")
    assert "HAS_SIDE_EFFECT" in Path(manifest.files["cypher"]).read_text(encoding="utf-8")
    assert Path(manifest.files["manifest"]).exists()
