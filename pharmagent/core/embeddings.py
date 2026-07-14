"""Singleton SentenceTransformer embedding model loader."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

from pharmagent.config import settings

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Return a cached SentenceTransformer instance."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model
