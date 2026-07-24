"""Build offline SIDER/MedDRA artifacts for RAG and Neo4j import."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

DEFAULT_OUTPUT_DIR = Path("data/processed/sider_meddra")
REQUIRED_FILES = ("drug_names.tsv", "meddra_all_se.tsv.gz", "meddra_freq.tsv.gz")


@dataclass(frozen=True)
class SiderIndexManifest:
    """Summary of generated offline artifacts."""

    source_zip: str
    output_dir: str
    drug_count: int
    side_effect_count: int
    relationship_count: int
    normalization_count: int
    rag_document_count: int
    files: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_zip": self.source_zip,
            "output_dir": self.output_dir,
            "drug_count": self.drug_count,
            "side_effect_count": self.side_effect_count,
            "relationship_count": self.relationship_count,
            "normalization_count": self.normalization_count,
            "rag_document_count": self.rag_document_count,
            "files": self.files,
        }


def build_sider_meddra_index(
    zip_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    max_drugs: int | None = None,
    max_relationships: int | None = None,
) -> SiderIndexManifest:
    """Generate RAG JSONL, Neo4j CSV import files, Cypher, and a manifest.

    The builder only materializes data already present in the local SIDER/MedDRA zip.
    It does not fetch, infer, or fabricate external evidence.
    """

    source = Path(zip_path)
    if not source.exists():
        raise FileNotFoundError(f"SIDER/MedDRA zip not found: {source}")

    out = Path(output_dir)
    neo4j_dir = out / "neo4j"
    neo4j_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source) as zf:
        names = zf.namelist()
        drug_file = _find_required(names, "drug_names.tsv")
        all_se_file = _find_required(names, "meddra_all_se.tsv.gz")
        freq_file = _find_required(names, "meddra_freq.tsv.gz")

        drug_names = _read_drug_names(zf, drug_file, max_drugs=max_drugs)
        terms, normalizations = _read_meddra_terms(zf, all_se_file, drug_names)
        edges = _read_frequency_edges(
            zf,
            freq_file,
            drug_names,
            max_relationships=max_relationships,
        )

    for edge in edges:
        terms.setdefault(
            edge["meddra_cui"],
            {"cui": edge["meddra_cui"], "term": edge["term"], "level": edge["meddra_level"]},
        )

    rag_documents = _build_rag_documents(drug_names, edges)
    files = {
        "rag_documents": str(out / "rag_documents.jsonl"),
        "drugs_csv": str(neo4j_dir / "drugs.csv"),
        "meddra_terms_csv": str(neo4j_dir / "meddra_terms.csv"),
        "side_effect_edges_csv": str(neo4j_dir / "drug_side_effect_edges.csv"),
        "normalization_edges_csv": str(neo4j_dir / "meddra_normalization_edges.csv"),
        "cypher": str(neo4j_dir / "import.cypher"),
        "manifest": str(out / "manifest.json"),
    }

    _write_rag_documents(Path(files["rag_documents"]), rag_documents)
    _write_csv(Path(files["drugs_csv"]), ["cid", "name"], drug_names.values())
    _write_csv(Path(files["meddra_terms_csv"]), ["cui", "term", "level"], terms.values())
    _write_csv(
        Path(files["side_effect_edges_csv"]),
        ["drug_cid", "meddra_cui", "frequency", "frequency_label", "source"],
        (
            {
                "drug_cid": edge["drug_cid"],
                "meddra_cui": edge["meddra_cui"],
                "frequency": edge["frequency"],
                "frequency_label": edge["frequency_label"],
                "source": edge["source"],
            }
            for edge in edges
        ),
    )
    _write_csv(
        Path(files["normalization_edges_csv"]),
        ["source_cui", "target_cui", "source_level", "target_level", "source_file"],
        normalizations.values(),
    )
    Path(files["cypher"]).write_text(_cypher_script(), encoding="utf-8")

    manifest = SiderIndexManifest(
        source_zip=str(source),
        output_dir=str(out),
        drug_count=len(drug_names),
        side_effect_count=len(terms),
        relationship_count=len(edges),
        normalization_count=len(normalizations),
        rag_document_count=len(rag_documents),
        files=files,
    )
    Path(files["manifest"]).write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def load_index_manifest(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, object] | None:
    manifest_path = Path(output_dir) / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build SIDER/MedDRA RAG and Neo4j artifacts.")
    parser.add_argument("--zip", default="data/incoming/adr_data.zip", help="Path to adr_data.zip")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--max-drugs", type=int, default=None, help="Optional development cap")
    parser.add_argument("--max-relationships", type=int, default=None, help="Optional development cap")
    args = parser.parse_args(argv)

    manifest = build_sider_meddra_index(
        args.zip,
        args.out,
        max_drugs=args.max_drugs,
        max_relationships=args.max_relationships,
    )
    print(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _find_required(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix) and not name.endswith("/")]
    if not matches:
        raise FileNotFoundError(f"Required SIDER/MedDRA member missing: {suffix}")
    return matches[0]


def _read_drug_names(
    zf: zipfile.ZipFile,
    name: str,
    *,
    max_drugs: int | None,
) -> dict[str, dict[str, str]]:
    drugs: dict[str, dict[str, str]] = {}
    with _open_text(zf, name) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            cid, drug_name = parts[0].strip(), parts[1].strip()
            if not cid or not drug_name:
                continue
            drugs.setdefault(cid, {"cid": cid, "name": drug_name})
            if max_drugs and len(drugs) >= max_drugs:
                break
    return drugs


def _read_meddra_terms(
    zf: zipfile.ZipFile,
    name: str,
    drugs: dict[str, dict[str, str]],
) -> tuple[dict[str, dict[str, str]], dict[tuple[str, str], dict[str, str]]]:
    terms: dict[str, dict[str, str]] = {}
    normalizations: dict[tuple[str, str], dict[str, str]] = {}
    with _open_text(zf, name) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6 or parts[0] not in drugs:
                continue
            _, _, umls_cui, level, meddra_cui, term = parts[:6]
            terms.setdefault(meddra_cui, {"cui": meddra_cui, "term": term, "level": level})
            if umls_cui and meddra_cui and umls_cui != meddra_cui:
                normalizations[(umls_cui, meddra_cui)] = {
                    "source_cui": umls_cui,
                    "target_cui": meddra_cui,
                    "source_level": "UMLS",
                    "target_level": level,
                    "source_file": "meddra_all_se.tsv.gz",
                }
    return terms, normalizations


def _read_frequency_edges(
    zf: zipfile.ZipFile,
    name: str,
    drugs: dict[str, dict[str, str]],
    *,
    max_relationships: int | None,
) -> list[dict[str, str | float | None]]:
    seen: set[tuple[str, str, str]] = set()
    edges: list[dict[str, str | float | None]] = []
    with _open_text(zf, name) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 10:
                continue
            drug_cid = parts[0].strip()
            if drug_cid not in drugs:
                continue
            frequency_label = parts[4].strip()
            frequency = _to_float(parts[6])
            meddra_level = parts[7].strip()
            meddra_cui = parts[8].strip()
            term = parts[9].strip()
            key = (drug_cid, meddra_cui, frequency_label)
            if not meddra_cui or key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "drug_cid": drug_cid,
                    "drug_name": drugs[drug_cid]["name"],
                    "meddra_cui": meddra_cui,
                    "meddra_level": meddra_level,
                    "term": term,
                    "frequency": frequency,
                    "frequency_label": frequency_label,
                    "source": "meddra_freq.tsv.gz",
                }
            )
            if max_relationships and len(edges) >= max_relationships:
                break
    return edges


def _build_rag_documents(
    drugs: dict[str, dict[str, str]],
    edges: list[dict[str, str | float | None]],
) -> list[dict[str, object]]:
    by_drug: dict[str, list[dict[str, str | float | None]]] = defaultdict(list)
    for edge in edges:
        by_drug[str(edge["drug_cid"])].append(edge)

    documents: list[dict[str, object]] = []
    for drug_cid, drug in drugs.items():
        drug_edges = by_drug.get(drug_cid, [])
        if not drug_edges:
            continue
        top_edges = sorted(
            drug_edges,
            key=lambda item: item["frequency"] if isinstance(item["frequency"], float) else -1.0,
            reverse=True,
        )
        side_effects = [
            {
                "term": edge["term"],
                "meddra_cui": edge["meddra_cui"],
                "level": edge["meddra_level"],
                "frequency": edge["frequency"],
                "frequency_label": edge["frequency_label"],
                "source_file": edge["source"],
            }
            for edge in top_edges
        ]
        text_terms = ", ".join(str(item["term"]) for item in side_effects[:12])
        documents.append(
            {
                "id": f"sider::{drug_cid}",
                "source": "SIDER/MedDRA local dataset",
                "source_type": "offline_real_dataset",
                "drug_cid": drug_cid,
                "drug_name": drug["name"],
                "side_effects": side_effects,
                "text": (
                    f"Drug {drug['name']} ({drug_cid}) has SIDER/MedDRA side-effect "
                    f"associations including: {text_terms}."
                ),
            }
        )
    return documents


def _write_rag_documents(path: Path, documents: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for doc in documents:
            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")


def _write_csv(path: Path, fieldnames: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _cypher_script() -> str:
    return """// Import from Neo4j import directory after copying generated CSV files there.
CREATE CONSTRAINT drug_cid IF NOT EXISTS FOR (d:Drug) REQUIRE d.cid IS UNIQUE;
CREATE CONSTRAINT meddra_cui IF NOT EXISTS FOR (m:MedDRATerm) REQUIRE m.cui IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///drugs.csv' AS row
MERGE (:Drug {cid: row.cid, name: row.name});

LOAD CSV WITH HEADERS FROM 'file:///meddra_terms.csv' AS row
MERGE (m:MedDRATerm {cui: row.cui})
SET m.term = row.term, m.level = row.level
WITH m
SET m:SideEffect;

LOAD CSV WITH HEADERS FROM 'file:///drug_side_effect_edges.csv' AS row
MATCH (d:Drug {cid: row.drug_cid})
MATCH (m:MedDRATerm {cui: row.meddra_cui})
MERGE (d)-[r:HAS_SIDE_EFFECT]->(m)
SET r.frequency = CASE row.frequency WHEN '' THEN null ELSE toFloat(row.frequency) END,
    r.frequency_label = row.frequency_label,
    r.source = row.source;

LOAD CSV WITH HEADERS FROM 'file:///meddra_normalization_edges.csv' AS row
MATCH (source:MedDRATerm {cui: row.source_cui})
MATCH (target:MedDRATerm {cui: row.target_cui})
MERGE (source)-[r:NORMALIZED_TO]->(target)
SET r.source_file = row.source_file,
    r.source_level = row.source_level,
    r.target_level = row.target_level;
"""


def _open_text(zf: zipfile.ZipFile, name: str) -> TextIO:
    raw = zf.open(name)
    if name.endswith(".gz"):
        return io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding="utf-8", errors="replace")
    return io.TextIOWrapper(raw, encoding="utf-8", errors="replace")


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
