#!/usr/bin/env python3
"""Enrich PubMed literature index with more articles per drug (single-pass).

Streams MedRAG/pubmed ONCE and tracks per-drug article counts, stopping when
every drug has reached the target count. Then rebuilds ONLY the
`pubmed_literature` ChromaDB + BM25 collection (drug labels and clinical
guidelines are left untouched).

Usage:
    python -m scripts.enrich_pubmed            # default: 40 articles per drug
    python -m scripts.enrich_pubmed --per-drug 80
"""

from __future__ import annotations

import argparse
import os
import pickle
import re
import sys

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rank_bm25 import BM25Okapi

from pharmagent.config import settings
from pharmagent.ingestion.chunker import chunk_documents
from pharmagent.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


DEMO_DRUGS = [
    "metformin", "warfarin", "lisinopril", "semaglutide", "aspirin",
    "amoxicillin", "penicillin",
    "glipizide", "glyburide",
    "clopidogrel", "apixaban", "rivaroxaban",
    "hydrochlorothiazide", "ibuprofen", "naproxen", "celecoxib",
    "atorvastatin", "simvastatin",
    "digoxin", "levothyroxine", "amlodipine", "metoprolol",
]


def stream_pubmed_per_drug(drugs: list[str], per_drug: int, max_rows: int = 300000) -> list[dict]:
    """Stream PubMed once; collect up to per_drug articles for each drug.

    A single article can count toward multiple drugs if it mentions them.
    Stops early when all drugs have reached the target or max_rows scanned.
    """
    from datasets import load_dataset

    patterns = {d: re.compile(re.escape(d), re.IGNORECASE) for d in drugs}
    counts: dict[str, int] = {d: 0 for d in drugs}
    collected: list[dict] = []
    seen_titles: set[str] = set()
    scanned = 0

    print(f"Streaming MedRAG/pubmed (target {per_drug} articles × {len(drugs)} drugs, max {max_rows} rows)")
    ds = load_dataset("MedRAG/pubmed", split="train", streaming=True)

    for row in ds:
        # Stop when all drugs satisfied or max rows reached
        if all(c >= per_drug for c in counts.values()):
            break
        if scanned >= max_rows:
            print(f"  reached max_rows={max_rows}, stopping early")
            break

        scanned += 1
        content = row.get("content") or row.get("contents") or row.get("text", "")
        title = row.get("title", "")
        combined = f"{title} {content}"

        # Find which drugs this article matches
        matched_drugs = [d for d in drugs if patterns[d].search(combined)]
        if not matched_drugs:
            continue

        # Dedup by title
        title_key = title.strip().lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        # Pick the drug that has the most remaining quota (priority to under-covered)
        remaining = {d: per_drug - counts[d] for d in matched_drugs if counts[d] < per_drug}
        if not remaining:
            continue
        chosen_drug = max(remaining, key=remaining.get)
        counts[chosen_drug] += 1

        collected.append(
            {
                "title": title,
                "text": content,
                "source": "pubmed",
                "drug_name": chosen_drug,
            }
        )

        if scanned % 5000 == 0:
            print(f"  [scanned {scanned}] collected {len(collected)} | "
                  f"min={min(counts.values())} max={max(counts.values())} | "
                    f"missing: {[d for d,c in counts.items() if c < per_drug][:5]}...", flush=True)

    print(f"\nScan complete: {scanned} rows scanned, {len(collected)} unique articles collected")
    print("Per-drug coverage:")
    for d in drugs:
        print(f"  {d}: {counts[d]}")
    return collected


def rebuild_pubmed_index(chunks: list[dict]) -> int:
    """Rebuild only the pubmed_literature ChromaDB collection + BM25 index."""
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)

    # Drop existing collection so we don't duplicate
    try:
        client.delete_collection("pubmed_literature")
        logger.info("dropped_existing_pubmed_collection")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name="pubmed_literature",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        collection.add(
            ids=[c["chunk_id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[
                {k: v for k, v in c.items() if k not in ("text", "chunk_id")}
                for c in batch
            ],
        )

    # Rebuild BM25
    os.makedirs(settings.bm25_persist_dir, exist_ok=True)
    corpus = [c["text"] for c in chunks]
    tokenized = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)

    with open(os.path.join(settings.bm25_persist_dir, "pubmed_literature_bm25.pkl"), "wb") as f:
        pickle.dump(bm25, f)
    with open(os.path.join(settings.bm25_persist_dir, "pubmed_literature_corpus.pkl"), "wb") as f:
        pickle.dump(corpus, f)
    with open(os.path.join(settings.bm25_persist_dir, "pubmed_literature_meta.pkl"), "wb") as f:
        pickle.dump([{k: v for k, v in c.items() if k != "text"} for c in chunks], f)

    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-drug", type=int, default=20,
                        help="Number of PubMed articles per drug (default: 20)")
    parser.add_argument("--max-rows", type=int, default=300000,
                        help="Max PubMed rows to scan (default: 300000)")
    args = parser.parse_args()

    setup_logging("INFO")

    all_raw = stream_pubmed_per_drug(DEMO_DRUGS, args.per_drug, args.max_rows)
    print(f"\nTotal unique PubMed articles collected: {len(all_raw)}")

    print("Chunking...")
    chunks = chunk_documents(all_raw)
    print(f"  → {len(chunks)} chunks")

    print("Rebuilding pubmed_literature indexes (ChromaDB + BM25)...")
    n = rebuild_pubmed_index(chunks)
    print(f"\n✅ Done. Indexed {n} chunks for pubmed_literature.")


if __name__ == "__main__":
    main()
