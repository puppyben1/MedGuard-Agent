"""Text chunking with metadata preservation."""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_documents(
    docs: list[dict],
    text_key: str = "text",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[dict]:
    """Split documents into chunks while preserving metadata.

    Each input dict must have a `text_key` field and any additional metadata.
    Returns a list of dicts with the same metadata plus chunked text and chunk_id.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunked: list[dict] = []
    global_idx = 0
    for doc in docs:
        text = doc.get(text_key, "")
        if not text or len(text.strip()) < 20:
            continue
        metadata = {k: v for k, v in doc.items() if k != text_key}
        chunks = splitter.split_text(text)
        for chunk in chunks:
            chunked.append(
                {
                    "text": chunk,
                    "chunk_id": (
                        f"{metadata.get('source', 'unknown')}"
                        f"_{metadata.get('drug_name', 'unknown')}_{global_idx}"
                    ),
                    **metadata,
                }
            )
            global_idx += 1

    return chunked
