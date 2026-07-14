"""Load MedRAG PubMed and StatPearls datasets via HuggingFace streaming."""

from __future__ import annotations

import re

from datasets import load_dataset

from pharmagent.logging_config import get_logger

logger = get_logger(__name__)


def _drug_pattern(drug_names: list[str]) -> re.Pattern:
    """Build a case-insensitive regex matching any of the drug names."""
    escaped = [re.escape(d) for d in drug_names]
    return re.compile("|".join(escaped), re.IGNORECASE)


def load_pubmed_snippets(
    drug_names: list[str],
    max_snippets: int = 500,
) -> list[dict]:
    """Stream MedRAG/pubmed and collect snippets matching the given drugs."""
    pattern = _drug_pattern(drug_names)
    collected: list[dict] = []

    logger.info("loading_pubmed", target_drugs=drug_names, max=max_snippets)
    ds = load_dataset("MedRAG/pubmed", split="train", streaming=True)

    for row in ds:
        if len(collected) >= max_snippets:
            break
        # MedRAG/pubmed fields: title, content (or contents)
        content = row.get("content") or row.get("contents") or row.get("text", "")
        title = row.get("title", "")
        combined = f"{title} {content}"
        if not pattern.search(combined):
            continue
        collected.append(
            {
                "title": title,
                "text": content,
                "source": "pubmed",
                "drug_name": _find_matching_drug(combined, drug_names),
            }
        )
        if len(collected) % 50 == 0:
            logger.info("pubmed_progress", collected=len(collected))

    logger.info("pubmed_done", total=len(collected))
    return collected


def load_statpearls_articles(
    drug_names: list[str],
    max_articles: int = 100,
) -> list[dict]:
    """Stream MedRAG clinical knowledge and collect articles matching the given drugs.

    Tries MedRAG/statpearls first; falls back to MedRAG/textbooks if unavailable.
    """
    pattern = _drug_pattern(drug_names)
    collected: list[dict] = []

    datasets_to_try = [
        ("MedRAG/statpearls", "statpearls"),
        ("MedRAG/textbooks", "textbooks"),
    ]

    for dataset_name, source_label in datasets_to_try:
        try:
            logger.info("loading_clinical", dataset=dataset_name, target_drugs=drug_names, max=max_articles)
            ds = load_dataset(dataset_name, split="train", streaming=True)
            # Verify we can iterate
            first = next(iter(ds))
            # Process first row
            for row in [first]:
                content = row.get("content") or row.get("contents") or row.get("text", "")
                title = row.get("title", "")
                combined = f"{title} {content}"
                if pattern.search(combined):
                    collected.append(
                        {
                            "title": title,
                            "text": content,
                            "source": source_label,
                            "drug_name": _find_matching_drug(combined, drug_names),
                        }
                    )
            # Continue with rest of dataset
            for row in ds:
                if len(collected) >= max_articles:
                    break
                content = row.get("content") or row.get("contents") or row.get("text", "")
                title = row.get("title", "")
                combined = f"{title} {content}"
                if not pattern.search(combined):
                    continue
                collected.append(
                    {
                        "title": title,
                        "text": content,
                        "source": source_label,
                        "drug_name": _find_matching_drug(combined, drug_names),
                    }
                )
            logger.info("clinical_done", dataset=dataset_name, total=len(collected))
            break  # Success — don't try next dataset
        except Exception as e:
            logger.warning("dataset_unavailable", dataset=dataset_name, error=str(e))
            continue

    if not collected:
        logger.warning("no_clinical_data", tried=[d[0] for d in datasets_to_try])
    return collected


def _find_matching_drug(text: str, drug_names: list[str]) -> str:
    """Return the first drug name found in the text."""
    text_lower = text.lower()
    for drug in drug_names:
        if drug.lower() in text_lower:
            return drug
    return "unknown"
