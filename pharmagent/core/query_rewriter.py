"""LLM-based query rewriting for failed retrievals."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

REWRITE_SYSTEM_PROMPT = """You are a pharmacovigilance search query optimizer.
The original query failed to retrieve enough relevant documents from drug safety databases.

Your task: rewrite the query to be more specific and likely to match relevant drug safety
information. Use precise medical terminology, drug generic names, and specific safety terms.

Rules:
- Keep the core intent of the original query
- Use generic drug names (not brand names)
- Add specific medical terms (e.g., "hepatotoxicity" instead of "liver damage")
- If the query is about drug interactions, mention both drugs explicitly
- Output ONLY the rewritten query, nothing else"""


def rewrite_query(
    original_query: str,
    failed_context: str,
    llm: ChatGroq,
) -> str:
    """Rewrite a query that failed to retrieve sufficient relevant documents."""
    messages = [
        SystemMessage(content=REWRITE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Original query: {original_query}\n\n"
                f"Context (why it failed): {failed_context}\n\n"
                "Rewritten query:"
            )
        ),
    ]

    try:
        response = llm.invoke(messages)
        rewritten = response.content.strip().strip('"').strip("'")
        logger.info("query_rewritten", original=original_query[:50], rewritten=rewritten[:50])
        return rewritten
    except Exception as exc:
        logger.warning("rewrite_failed", error=str(exc))
        return original_query
