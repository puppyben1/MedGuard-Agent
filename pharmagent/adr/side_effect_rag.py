"""Searchable SIDER/MedDRA side-effect RAG index."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pickle
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from pharmagent.adr.sider_index import DEFAULT_OUTPUT_DIR, build_sider_meddra_index
from pharmagent.runtime_config import load_runtime_config

RAG_DIR = Path("data/side_effect_rag")
DOCUMENTS_PATH = RAG_DIR / "documents.jsonl"
BM25_DIR = RAG_DIR / "bm25"
CHROMA_DIR = RAG_DIR / "chroma"
MANIFEST_PATH = RAG_DIR / "manifest.json"
COLLECTION_NAME = "sider_meddra_side_effects"
EMBEDDING_DIM = 256


class SideEffectRAGStatus(BaseModel):
    available: bool
    source_type: str = "offline_real_dataset"
    documents_path: str = str(DOCUMENTS_PATH)
    bm25_path: str = str(BM25_DIR)
    chroma_path: str = str(CHROMA_DIR)
    document_count: int = 0
    bm25_available: bool = False
    chroma_available: bool = False
    chroma_error: str = ""
    manifest: dict[str, object] = Field(default_factory=dict)


class SideEffectSearchRequest(BaseModel):
    query: str = ""
    drug: str = ""
    adr: str = ""
    top_k: int = 8


class SideEffectHit(BaseModel):
    doc_id: str
    drug_cid: str
    drug_name: str
    matched_side_effects: list[dict[str, str | float | None]] = Field(default_factory=list)
    source: str = "SIDER/MedDRA"
    source_type: str = "offline_real_dataset"
    score: float = 0.0
    retrieval_method: str = "hybrid_bm25_vector"
    text: str = ""


class SideEffectSearchResponse(BaseModel):
    query: str
    source_type: str = "offline_real_dataset"
    hits: list[SideEffectHit] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _IndexedDocument:
    doc_id: str
    drug_cid: str
    drug_name: str
    side_effects: list[dict[str, str | float | None]]
    text: str
    source: str
    source_type: str


def build_side_effect_rag(
    source_documents: str | Path | None = None,
    output_dir: str | Path = RAG_DIR,
    *,
    build_chroma: bool = True,
) -> SideEffectRAGStatus:
    """Build a local BM25 + Chroma side-effect index from SIDER/MedDRA documents."""

    out = Path(output_dir)
    docs_path = out / "documents.jsonl"
    bm25_dir = out / "bm25"
    chroma_dir = out / "chroma"
    out.mkdir(parents=True, exist_ok=True)
    bm25_dir.mkdir(parents=True, exist_ok=True)

    source_path = _ensure_source_documents(source_documents)
    documents = [_convert_document(doc) for doc in _read_jsonl(source_path)]
    _write_jsonl(docs_path, (_document_to_output(doc) for doc in documents))
    _build_bm25(documents, bm25_dir)

    chroma_error = ""
    chroma_available = False
    if build_chroma:
        try:
            _build_chroma(documents, chroma_dir)
            chroma_available = True
        except Exception as exc:  # noqa: BLE001
            chroma_error = str(exc)

    manifest = {
        "source_documents": str(source_path),
        "source_type": "offline_real_dataset",
        "documents_path": str(docs_path),
        "bm25_path": str(bm25_dir),
        "chroma_path": str(chroma_dir),
        "document_count": len(documents),
        "bm25_available": True,
        "chroma_available": chroma_available,
        "chroma_error": chroma_error,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return _status_from_manifest(out / "manifest.json", manifest)


def side_effect_rag_status(output_dir: str | Path = RAG_DIR) -> SideEffectRAGStatus:
    manifest_path = Path(output_dir) / "manifest.json"
    if not manifest_path.exists():
        return SideEffectRAGStatus(
            available=False,
            documents_path=str(Path(output_dir) / "documents.jsonl"),
            bm25_path=str(Path(output_dir) / "bm25"),
            chroma_path=str(Path(output_dir) / "chroma"),
            manifest={},
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return SideEffectRAGStatus(available=False, manifest={})
    return _status_from_manifest(manifest_path, manifest)


def search_side_effects(
    req: SideEffectSearchRequest,
    output_dir: str | Path = RAG_DIR,
) -> SideEffectSearchResponse:
    query = _compose_query(req)
    if not query:
        raise ValueError("query、drug 或 adr 至少需要提供一个")

    status = side_effect_rag_status(output_dir)
    if not status.available:
        return SideEffectSearchResponse(
            query=query,
            hits=[],
            limitations=["SIDER/MedDRA RAG 索引尚未构建，请先运行 python scripts/build_side_effect_rag.py。"],
        )

    docs = _load_documents(Path(status.documents_path))
    exact_hits = _query_exact(docs.values(), req)
    bm25_hits = _query_bm25(query, Path(status.bm25_path), top_k=max(req.top_k * 2, 10))
    vector_hits = _query_chroma(query, Path(status.chroma_path), top_k=max(req.top_k * 2, 10))
    ranked_ids = _rrf([exact_hits, exact_hits, exact_hits, bm25_hits, vector_hits])

    hits: list[SideEffectHit] = []
    for doc_id, score in ranked_ids[: max(req.top_k, 1)]:
        doc = docs.get(doc_id)
        if not doc:
            continue
        hits.append(_to_hit(doc, query, score))

    limitations = [
        "SIDER/MedDRA 离线索引表示药物-不良反应报告/说明书关联，不等同于临床因果证明。",
        "该检索不包含未接入的 PubMed、DrugBank 或 FAERS 官方季度实时结果。",
    ]
    if not status.chroma_available:
        limitations.append("向量索引不可用，本次仅使用 BM25 稀疏检索。")
    return SideEffectSearchResponse(query=query, hits=hits, limitations=limitations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build SIDER/MedDRA side-effect RAG index.")
    parser.add_argument("--source-documents", default=None, help="Existing SIDER JSONL documents")
    parser.add_argument("--out", default=str(RAG_DIR), help="Output directory")
    parser.add_argument("--no-chroma", action="store_true", help="Skip Chroma vector index")
    args = parser.parse_args(argv)
    status = build_side_effect_rag(
        args.source_documents,
        args.out,
        build_chroma=not args.no_chroma,
    )
    print(json.dumps(status.model_dump(), ensure_ascii=False, indent=2))
    return 0


def _ensure_source_documents(source_documents: str | Path | None) -> Path:
    if source_documents:
        source = Path(source_documents)
        if not source.exists():
            raise FileNotFoundError(f"source documents not found: {source}")
        return source

    generated = DEFAULT_OUTPUT_DIR / "rag_documents.jsonl"
    if generated.exists():
        return generated

    runtime = load_runtime_config()
    build_sider_meddra_index(runtime.rag.side_effect_zip_path, DEFAULT_OUTPUT_DIR)
    return generated


def _convert_document(raw: dict[str, object]) -> _IndexedDocument:
    doc_id = str(raw.get("doc_id") or raw.get("id") or f"sider::{raw.get('drug_cid', '')}")
    side_effects = raw.get("side_effects")
    return _IndexedDocument(
        doc_id=doc_id,
        drug_cid=str(raw.get("drug_cid") or ""),
        drug_name=str(raw.get("drug_name") or ""),
        side_effects=side_effects if isinstance(side_effects, list) else [],
        text=str(raw.get("text") or _compose_document_text(raw)),
        source=str(raw.get("source") or "SIDER/MedDRA"),
        source_type=str(raw.get("source_type") or "offline_real_dataset"),
    )


def _compose_document_text(raw: dict[str, object]) -> str:
    terms = []
    for item in raw.get("side_effects", []):
        if isinstance(item, dict) and item.get("term"):
            terms.append(str(item["term"]))
    return f"Drug {raw.get('drug_name', '')} ({raw.get('drug_cid', '')}) side effects: {', '.join(terms[:20])}."


def _document_to_output(doc: _IndexedDocument) -> dict[str, object]:
    return {
        "doc_id": doc.doc_id,
        "drug_cid": doc.drug_cid,
        "drug_name": doc.drug_name,
        "side_effects": doc.side_effects,
        "source": "SIDER/MedDRA",
        "source_type": doc.source_type,
        "text": doc.text,
    }


def _build_bm25(documents: list[_IndexedDocument], bm25_dir: Path) -> None:
    corpus = [doc.text for doc in documents]
    tokenized = [_tokenize(doc.text) for doc in documents]
    bm25 = BM25Okapi(tokenized)
    metadata = [
        {
            "doc_id": doc.doc_id,
            "drug_cid": doc.drug_cid,
            "drug_name": doc.drug_name,
            "search_text": doc.text,
            "source": doc.source,
            "source_type": doc.source_type,
        }
        for doc in documents
    ]
    with (bm25_dir / "index.pkl").open("wb") as fh:
        pickle.dump(bm25, fh)
    with (bm25_dir / "corpus.pkl").open("wb") as fh:
        pickle.dump(corpus, fh)
    with (bm25_dir / "meta.pkl").open("wb") as fh:
        pickle.dump(metadata, fh)


def _build_chroma(documents: list[_IndexedDocument], chroma_dir: Path) -> None:
    import chromadb

    if chroma_dir.exists():
        shutil.rmtree(chroma_dir)
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "source_type": "offline_real_dataset"},
    )
    batch_size = 100
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        collection.add(
            ids=[doc.doc_id for doc in batch],
            documents=[doc.text for doc in batch],
            embeddings=[_hash_embedding(doc.text) for doc in batch],
            metadatas=[
                {
                    "drug_cid": doc.drug_cid,
                    "drug_name": doc.drug_name,
                    "source": doc.source,
                    "source_type": doc.source_type,
                }
                for doc in batch
            ],
        )


def _query_bm25(query: str, bm25_dir: Path, *, top_k: int) -> list[str]:
    paths = [bm25_dir / "index.pkl", bm25_dir / "meta.pkl"]
    if not all(path.exists() for path in paths):
        return []
    with (bm25_dir / "index.pkl").open("rb") as fh:
        bm25 = pickle.load(fh)
    with (bm25_dir / "meta.pkl").open("rb") as fh:
        meta = pickle.load(fh)
    query_tokens = set(_tokenize(query))
    scores = bm25.get_scores(list(query_tokens))
    ranked = sorted(
        range(len(scores)),
        key=lambda idx: (scores[idx], _token_overlap(query_tokens, str(meta[idx].get("drug_name", "")))),
        reverse=True,
    )
    hits: list[str] = []
    for idx in ranked[:top_k]:
        overlap = _token_overlap(query_tokens, meta[idx].get("search_text", ""))
        if scores[idx] <= 0 and overlap <= 0:
            continue
        hits.append(str(meta[idx]["doc_id"]))
    return hits


def _query_chroma(query: str, chroma_dir: Path, *, top_k: int) -> list[str]:
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection(COLLECTION_NAME)
        result = collection.query(query_embeddings=[_hash_embedding(query)], n_results=top_k)
        return [str(item) for item in (result.get("ids") or [[]])[0]]
    except Exception:
        return []


def _query_exact(documents: Iterable[_IndexedDocument], req: SideEffectSearchRequest) -> list[str]:
    drug = req.drug.strip().lower()
    adr_tokens = set(_tokenize(req.adr))
    ranked: list[tuple[str, int]] = []
    for doc in documents:
        score = 0
        if drug:
            if drug not in doc.drug_name.lower():
                continue
            score += 4
        if adr_tokens:
            for item in doc.side_effects:
                score += _token_overlap(adr_tokens, item.get("term", ""))
                if score >= 6:
                    break
        if score > 0:
            ranked.append((doc.doc_id, score))
    return [doc_id for doc_id, _ in sorted(ranked, key=lambda item: item[1], reverse=True)]


def _rrf(result_sets: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for results in result_sets:
        for rank, doc_id in enumerate(results, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _to_hit(doc: _IndexedDocument, query: str, score: float) -> SideEffectHit:
    query_tokens = set(_tokenize(query))
    matched = []
    fallback = []
    for item in doc.side_effects:
        term = str(item.get("term", ""))
        haystack = set(_tokenize(term))
        formatted = {
            "term": term,
            "meddra_cui": item.get("meddra_cui"),
            "level": item.get("level"),
            "frequency": item.get("frequency"),
            "frequency_label": item.get("frequency_label"),
            "source_file": item.get("source_file"),
        }
        if query_tokens & haystack:
            matched.append(formatted)
        elif len(fallback) < 3:
            fallback.append(formatted)
        if len(matched) >= 8:
            break
    if not matched:
        matched = fallback
    return SideEffectHit(
        doc_id=doc.doc_id,
        drug_cid=doc.drug_cid,
        drug_name=doc.drug_name,
        matched_side_effects=matched,
        source=doc.source,
        source_type=doc.source_type,
        score=round(score, 6),
        text=doc.text,
    )


def _compose_query(req: SideEffectSearchRequest) -> str:
    parts = [req.query.strip(), req.drug.strip(), req.adr.strip()]
    return " ".join(part for part in parts if part)


def _load_documents(path: Path) -> dict[str, _IndexedDocument]:
    return {doc.doc_id: doc for doc in (_convert_document(raw) for raw in _read_jsonl(path))}


def _read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower())


def _token_overlap(query_tokens: set[str], text: object) -> int:
    return len(query_tokens & set(_tokenize(str(text))))


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    for token in _tokenize(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _status_from_manifest(manifest_path: Path, manifest: dict[str, object]) -> SideEffectRAGStatus:
    documents_path = str(manifest.get("documents_path") or DOCUMENTS_PATH)
    bm25_path = str(manifest.get("bm25_path") or BM25_DIR)
    chroma_path = str(manifest.get("chroma_path") or CHROMA_DIR)
    bm25_available = all(
        (Path(bm25_path) / filename).exists()
        for filename in ("index.pkl", "corpus.pkl", "meta.pkl")
    )
    chroma_available = bool(manifest.get("chroma_available")) and Path(chroma_path).exists()
    document_count = int(manifest.get("document_count") or _count_jsonl(Path(documents_path)))
    return SideEffectRAGStatus(
        available=Path(documents_path).exists() and bm25_available,
        documents_path=documents_path,
        bm25_path=bm25_path,
        chroma_path=chroma_path,
        document_count=document_count,
        bm25_available=bm25_available,
        chroma_available=chroma_available,
        chroma_error=str(manifest.get("chroma_error") or ""),
        manifest={**manifest, "manifest_path": str(manifest_path)},
    )


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


if __name__ == "__main__":
    raise SystemExit(main())
