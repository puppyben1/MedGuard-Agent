"""BM25 sparse retrieval with pickle persistence."""

from __future__ import annotations

import os
import pickle

import numpy as np
from rank_bm25 import BM25Okapi

from pharmagent.config import settings
from pharmagent.core.schemas import RetrievedDoc


def _bm25_path(name: str) -> str:
    return os.path.join(settings.bm25_persist_dir, f"{name}_bm25.pkl")


def _corpus_path(name: str) -> str:
    return os.path.join(settings.bm25_persist_dir, f"{name}_corpus.pkl")


def _meta_path(name: str) -> str:
    return os.path.join(settings.bm25_persist_dir, f"{name}_meta.pkl")


def load_bm25_index(name: str) -> tuple[BM25Okapi, list[str], list[dict]] | None:
    """Load a persisted BM25 index, corpus, and metadata. Returns None if not found."""
    bp, cp, mp = _bm25_path(name), _corpus_path(name), _meta_path(name)
    if not (os.path.exists(bp) and os.path.exists(cp) and os.path.exists(mp)):
        return None
    with open(bp, "rb") as f:
        bm25 = pickle.load(f)
    with open(cp, "rb") as f:
        corpus = pickle.load(f)
    with open(mp, "rb") as f:
        meta = pickle.load(f)
    return bm25, corpus, meta


def query_bm25(
    name: str,
    query_text: str,
    top_k: int = 20,
) -> list[RetrievedDoc]:
    """Query a BM25 index and return RetrievedDoc objects."""
    loaded = load_bm25_index(name)
    if loaded is None:
        return []
    bm25, corpus, meta = loaded

    tokenized_query = query_text.lower().split()
    scores = bm25.get_scores(tokenized_query)

    top_indices = np.argsort(scores)[::-1][:top_k]

    docs: list[RetrievedDoc] = []
    for idx in top_indices:
        if scores[idx] <= 0:
            break
        docs.append(
            RetrievedDoc(
                content=corpus[idx],
                metadata=meta[idx] if idx < len(meta) else {},
                score=float(scores[idx]),
                source_collection=name,
            )
        )
    return docs
