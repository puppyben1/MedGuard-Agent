"""Singleton SentenceTransformer embedding model loader."""

from __future__ import annotations

import os

# Force offline mode BEFORE importing sentence_transformers so it never
# tries to phone home to huggingface.co (which times out for ~30s on
# networks without direct access). The model is already cached locally.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from sentence_transformers import SentenceTransformer

from pharmagent.config import settings

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Return a cached SentenceTransformer instance."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model, local_files_only=True)
    return _model
