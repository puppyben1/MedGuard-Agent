"""Runtime loader for SIDER/MedDRA side-effect data used by RAG and graph demos."""

from __future__ import annotations

import gzip
import io
import zipfile
from functools import lru_cache
from pathlib import Path

from pharmagent.adr.schemas import (
    Neo4jGraphPreview,
    Neo4jNode,
    Neo4jRelationship,
    SideEffectDatasetSummary,
)
from pharmagent.adr.sider_index import DEFAULT_OUTPUT_DIR, load_index_manifest

DEFAULT_ZIP = Path("data/incoming/adr_data.zip")


@lru_cache(maxsize=1)
def summarize_side_effect_dataset(zip_path: str = str(DEFAULT_ZIP)) -> SideEffectDatasetSummary:
    """Inspect the local side-effect dataset without materializing it into git-tracked files."""
    path = Path(zip_path)
    manifest = load_index_manifest(DEFAULT_OUTPUT_DIR)
    if not path.exists():
        return SideEffectDatasetSummary(
            dataset_name="SIDER/MedDRA side-effect dataset",
            available=False,
            source_path=str(path),
            index_available=bool(manifest),
            index_manifest=manifest or {},
            notes=[
                "未发现本地数据包。请将数据.zip 复制为 data/incoming/adr_data.zip 后再构建 RAG/Neo4j 图谱。",
            ],
        )

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        drug_file = _find(names, "drug_names.tsv")
        all_se_file = _find(names, "meddra_all_se.tsv.gz")
        freq_file = _find(names, "meddra_freq.tsv.gz")

        preview = _build_preview(zf, drug_file, freq_file)

    return SideEffectDatasetSummary(
        dataset_name="SIDER/MedDRA drug side-effect dataset",
        available=True,
        source_path=str(path),
        files=[drug_file, all_se_file, freq_file],
        row_counts={
            "drug_names_bytes": zf.getinfo(drug_file).file_size,
            "meddra_all_side_effects_bytes": zf.getinfo(all_se_file).file_size,
            "meddra_frequency_bytes": zf.getinfo(freq_file).file_size,
        },
        index_available=bool(manifest),
        index_manifest=manifest or {},
        rag_strategy=[
            "按 drug CID 聚合药物名称、MedDRA PT/LLT 不良反应和频率，生成每药一个 RAG 文档块。",
            "文档块包含 drug_name、side_effect_term、meddra_concept_id、frequency、source_file，便于证据溯源。",
            "问答时先做药名标准化，再检索相关药物块，最后由 LLM 生成带来源的解释。",
        ],
        neo4j_schema=[
            "(:Drug {cid, name})",
            "(:MedDRATerm {cui, term, level})",
            "(:SideEffect {name, meddra_cui})",
            "(:Drug)-[:HAS_NAME]->(:DrugName)",
            "(:Drug)-[:HAS_SIDE_EFFECT {frequency, frequency_label, source}]->(:MedDRATerm)",
            "(:MedDRATerm)-[:NORMALIZED_TO]->(:MedDRATerm)",
        ],
        graph_preview=preview,
        notes=[
            "该数据适合作为 SIDER 风格药物副作用知识库，用于 RAG 检索和 Neo4j 图谱展示。",
            "频率字段可作为 Neo4j 边权重，也可映射到 3D 图谱节点大小或边粗细。",
            "如需生成离线索引产物，请运行 python scripts/build_sider_meddra_index.py。",
        ],
    )


def _find(names: list[str], suffix: str) -> str:
    return next(name for name in names if name.endswith(suffix))


def _build_preview(zf: zipfile.ZipFile, drug_file: str, freq_file: str) -> Neo4jGraphPreview:
    cid_to_name: dict[str, str] = {}
    with _open_text(zf, drug_file) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                cid_to_name[parts[0]] = parts[1]
            if len(cid_to_name) >= 200:
                break

    nodes: dict[str, Neo4jNode] = {}
    relationships: list[Neo4jRelationship] = []

    with _open_text(zf, freq_file) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 10:
                continue
            drug_cid, _stitch_id, _umls, freq_label, _lower, freq_value, meddra_level, meddra_cui, term = (
                parts[0],
                parts[1],
                parts[2],
                parts[4],
                parts[5],
                parts[6],
                parts[7],
                parts[8],
                parts[9],
            )
            drug_name = cid_to_name.get(drug_cid)
            if not drug_name:
                continue
            drug_id = f"Drug:{drug_cid}"
            se_id = f"MedDRA:{meddra_cui}"
            nodes.setdefault(
                drug_id,
                Neo4jNode(id=drug_id, labels=["Drug"], properties={"cid": drug_cid, "name": drug_name}),
            )
            nodes.setdefault(
                se_id,
                Neo4jNode(
                    id=se_id,
                    labels=["MedDRATerm", "SideEffect"],
                    properties={"cui": meddra_cui, "term": term, "level": meddra_level},
                ),
            )
            relationships.append(
                Neo4jRelationship(
                    source=drug_id,
                    target=se_id,
                    type="HAS_SIDE_EFFECT",
                    properties={
                        "frequency": _to_float(freq_value),
                        "frequency_label": freq_label,
                        "source": "meddra_freq.tsv.gz",
                    },
                )
            )
            if len(relationships) >= 8:
                break

    return Neo4jGraphPreview(
        nodes=list(nodes.values()),
        relationships=relationships,
        cypher_examples=[
            "MATCH (d:Drug)-[r:HAS_SIDE_EFFECT]->(s:SideEffect) WHERE toLower(d.name) CONTAINS 'warfarin' RETURN d,r,s LIMIT 25;",
            "MATCH p=(d:Drug)-[:HAS_SIDE_EFFECT]->(s:SideEffect) WHERE s.term CONTAINS 'Bleeding' RETURN p LIMIT 25;",
            "MATCH (d:Drug)-[r:HAS_SIDE_EFFECT]->(s:SideEffect) WHERE r.frequency >= 0.05 RETURN d.name, s.term, r.frequency ORDER BY r.frequency DESC LIMIT 20;",
        ],
    )


def _open_text(zf: zipfile.ZipFile, name: str):
    raw = zf.open(name)
    if name.endswith(".gz"):
        return io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding="utf-8", errors="replace")
    return io.TextIOWrapper(raw, encoding="utf-8", errors="replace")


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
