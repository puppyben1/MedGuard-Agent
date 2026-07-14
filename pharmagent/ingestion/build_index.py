"""Orchestrate data ingestion: fetch, chunk, embed, and index into ChromaDB + BM25."""

from __future__ import annotations

import os
import pickle

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rank_bm25 import BM25Okapi

from pharmagent.config import settings
from pharmagent.ingestion.chunker import chunk_documents
from pharmagent.ingestion.dailymed import fetch_drug_labels
from pharmagent.ingestion.medrag_loader import load_pubmed_snippets, load_statpearls_articles
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)


def _get_chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def _get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    return SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)


def _build_bm25_index(chunks: list[dict], collection_name: str) -> None:
    """Build and persist a BM25 index for the given chunks."""
    os.makedirs(settings.bm25_persist_dir, exist_ok=True)
    corpus = [c["text"] for c in chunks]
    tokenized = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)

    bm25_path = os.path.join(settings.bm25_persist_dir, f"{collection_name}_bm25.pkl")
    corpus_path = os.path.join(settings.bm25_persist_dir, f"{collection_name}_corpus.pkl")
    meta_path = os.path.join(settings.bm25_persist_dir, f"{collection_name}_meta.pkl")

    with open(bm25_path, "wb") as f:
        pickle.dump(bm25, f)
    with open(corpus_path, "wb") as f:
        pickle.dump(corpus, f)
    with open(meta_path, "wb") as f:
        pickle.dump([{k: v for k, v in c.items() if k != "text"} for c in chunks], f)

    logger.info("bm25_index_built", collection=collection_name, docs=len(corpus))


def _index_to_chromadb(
    chunks: list[dict],
    collection_name: str,
    client: chromadb.ClientAPI,
    embedding_fn: SentenceTransformerEmbeddingFunction,
) -> None:
    """Insert chunks into a ChromaDB collection."""
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # ChromaDB has a batch limit; insert in batches of 100
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
    logger.info("chromadb_indexed", collection=collection_name, docs=len(chunks))


def build_all_indexes(drug_names: list[str]) -> dict[str, int]:
    """Fetch data for the given drugs, chunk, and build all indexes.

    Returns a dict of collection_name -> document_count.
    """
    client = _get_chroma_client()
    embedding_fn = _get_embedding_fn()
    counts: dict[str, int] = {}

    # 1. Drug labels from DailyMed
    logger.info("step", phase="drug_labels")
    raw_labels = fetch_drug_labels(drug_names)
    label_chunks = chunk_documents(raw_labels)
    if label_chunks:
        _index_to_chromadb(label_chunks, "drug_labels", client, embedding_fn)
        _build_bm25_index(label_chunks, "drug_labels")
        counts["drug_labels"] = len(label_chunks)
    else:
        logger.warning("no_label_chunks")
        counts["drug_labels"] = 0

    # 2. PubMed literature from MedRAG
    logger.info("step", phase="pubmed_literature")
    raw_pubmed = load_pubmed_snippets(drug_names, max_snippets=500)
    pubmed_chunks = chunk_documents(raw_pubmed)
    if pubmed_chunks:
        _index_to_chromadb(pubmed_chunks, "pubmed_literature", client, embedding_fn)
        _build_bm25_index(pubmed_chunks, "pubmed_literature")
        counts["pubmed_literature"] = len(pubmed_chunks)
    else:
        logger.warning("no_pubmed_chunks")
        counts["pubmed_literature"] = 0

    # 3. Clinical guidelines from StatPearls
    logger.info("step", phase="clinical_guidelines")
    raw_statpearls = load_statpearls_articles(drug_names, max_articles=100)
    statpearls_chunks = chunk_documents(raw_statpearls)
    if statpearls_chunks:
        _index_to_chromadb(statpearls_chunks, "clinical_guidelines", client, embedding_fn)
        _build_bm25_index(statpearls_chunks, "clinical_guidelines")
        counts["clinical_guidelines"] = len(statpearls_chunks)
    else:
        logger.warning("no_statpearls_chunks")
        counts["clinical_guidelines"] = 0

    logger.info("indexing_complete", counts=counts)
    return counts
