"""Smoke tests for hybrid retrieval."""

import pytest

from pharmagent.core.hybrid_retriever import hybrid_search


def _chromadb_has_data() -> bool:
    """Check if ChromaDB has been populated."""
    try:
        from pharmagent.core.vectorstore import get_collection

        collection = get_collection("drug_labels")
        return collection.count() > 0
    except Exception:
        return False


@pytest.mark.skipif(
    not _chromadb_has_data(),
    reason="ChromaDB not populated — run scripts/ingest_demo.py first",
)
def test_metformin_retrieval():
    """Verify that querying 'metformin renal dosing' returns results from drug_labels."""
    results = hybrid_search(
        query="metformin renal dosing adjustment",
        collections=["drug_labels"],
        top_k=10,
        rerank_top_k=5,
    )
    assert len(results) >= 1, "Expected at least 1 result for metformin renal dosing"
    contents = " ".join(r.content.lower() for r in results)
    assert "metformin" in contents


@pytest.mark.skipif(
    not _chromadb_has_data(),
    reason="ChromaDB not populated — run scripts/ingest_demo.py first",
)
def test_multi_collection_retrieval():
    """Verify retrieval across multiple collections."""
    results = hybrid_search(
        query="warfarin aspirin interaction bleeding risk",
        collections=["drug_labels", "pubmed_literature", "clinical_guidelines"],
        top_k=10,
        rerank_top_k=5,
    )
    assert len(results) >= 1, "Expected at least 1 result for warfarin-aspirin interaction"
