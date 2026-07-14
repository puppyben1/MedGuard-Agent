"""ChromaDB vector store operations."""

from __future__ import annotations

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from pharmagent.config import settings
from pharmagent.core.schemas import RetrievedDoc

_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def _get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    return SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)


def get_collection(name: str) -> chromadb.Collection:
    """Return a persistent ChromaDB collection by name."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        embedding_function=_get_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def query_collection(
    name: str,
    query_text: str,
    top_k: int = 20,
) -> list[RetrievedDoc]:
    """Query a ChromaDB collection and return RetrievedDoc objects."""
    collection = get_collection(name)
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    docs: list[RetrievedDoc] = []
    for i in range(len(results["ids"][0])):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # Convert to similarity score: 1 - (distance / 2)
        distance = results["distances"][0][i]
        score = 1.0 - (distance / 2.0)
        docs.append(
            RetrievedDoc(
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
                score=score,
                source_collection=name,
            )
        )
    return docs
