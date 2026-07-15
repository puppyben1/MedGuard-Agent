"""PharmAgent — Autonomous drug safety intelligence system."""

import os

# Force HuggingFace offline mode BEFORE any sentence_transformers / transformers
# import happens (e.g. via hybrid_retriever or embeddings). Without this, the
# library phones home to huggingface.co on every model load and times out for
# ~30s on networks without direct access. Models are already cached locally.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

__version__ = "0.1.0"
