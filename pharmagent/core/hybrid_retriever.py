"""Hybrid retrieval: dense (ChromaDB) + sparse (BM25) via RRF, with cross-encoder reranking."""

from __future__ import annotations

from sentence_transformers import CrossEncoder

from pharmagent.config import settings
from pharmagent.core.bm25_store import query_bm25
from pharmagent.core.schemas import RetrievedDoc
from pharmagent.core.vectorstore import query_collection
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

_cross_encoder: CrossEncoder | None = None


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


def _reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedDoc]],
    k: int = 60,
) -> list[RetrievedDoc]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion."""
    doc_scores: dict[str, float] = {}
    doc_map: dict[str, RetrievedDoc] = {}

    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list):
            doc_key = f"{doc.source_collection}::{doc.content[:100]}"
            rrf_score = 1.0 / (k + rank + 1)
            doc_scores[doc_key] = doc_scores.get(doc_key, 0.0) + rrf_score
            if doc_key not in doc_map:
                doc_map[doc_key] = doc

    sorted_keys = sorted(doc_scores, key=lambda x: doc_scores[x], reverse=True)
    return [doc_map[k] for k in sorted_keys]


def _rerank(
    query: str,
    docs: list[RetrievedDoc],
    top_k: int,
) -> list[RetrievedDoc]:
    """Rerank documents using a cross-encoder model."""
    if not docs:
        return []
    encoder = _get_cross_encoder()
    pairs = [[query, doc.content] for doc in docs]
    scores = encoder.predict(pairs)

    scored_docs = list(zip(docs, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)

    return [
        RetrievedDoc(
            content=doc.content,
            metadata=doc.metadata,
            score=float(score),
            source_collection=doc.source_collection,
        )
        for doc, score in scored_docs[:top_k]
    ]


def hybrid_search(
    query: str,
    collections: list[str],
    top_k: int | None = None,
    rerank_top_k: int | None = None,
) -> list[RetrievedDoc]:
    """Run hybrid search across multiple collections with RRF fusion and cross-encoder reranking."""
    top_k = top_k or settings.hybrid_search_top_k
    rerank_top_k = rerank_top_k or settings.rerank_top_k

    all_ranked_lists: list[list[RetrievedDoc]] = []

    for collection_name in collections:
        # Dense retrieval
        dense_results = query_collection(collection_name, query, top_k=top_k)
        if dense_results:
            all_ranked_lists.append(dense_results)

        # Sparse retrieval
        sparse_results = query_bm25(collection_name, query, top_k=top_k)
        if sparse_results:
            all_ranked_lists.append(sparse_results)

    if not all_ranked_lists:
        logger.warning("no_retrieval_results", query=query, collections=collections)
        return []

    # Fuse with RRF
    fused = _reciprocal_rank_fusion(all_ranked_lists, k=settings.rrf_k)
    logger.info(
        "rrf_fusion_done",
        query=query[:50],
        total_fused=len(fused),
        collections=collections,
    )

    # Rerank with cross-encoder
    reranked = _rerank(query, fused[:top_k], rerank_top_k)
    logger.info("reranking_done", top_docs=len(reranked))

    return reranked
