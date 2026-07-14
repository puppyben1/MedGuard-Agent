"""LLM-based document relevance grading."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from pharmagent.core.schemas import GradedDoc, RetrievedDoc
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

GRADING_SYSTEM_PROMPT = """You are a pharmacovigilance document relevance grader.
Given a user query and a list of retrieved document chunks, evaluate whether each chunk
is relevant to answering the query.

Respond with a JSON array where each element has:
- "index": the 0-based index of the document
- "relevant": true or false
- "reasoning": a brief explanation (1 sentence)

Be strict: a document is relevant ONLY if it contains specific information that directly
helps answer the query (drug safety data, interaction info, dosing guidance, adverse events,
or clinical recommendations related to the query). General background that doesn't address
the specific question is NOT relevant.

Respond ONLY with the JSON array, no other text."""


def grade_documents(
    query: str,
    docs: list[RetrievedDoc],
    llm: ChatGroq,
) -> list[GradedDoc]:
    """Grade a batch of retrieved documents for relevance to the query.

    All documents are graded in a single LLM call to conserve rate limits.
    """
    if not docs:
        return []

    # Build the batch prompt
    doc_descriptions = []
    for i, doc in enumerate(docs):
        source = doc.metadata.get("source", "unknown")
        drug = doc.metadata.get("drug_name", "unknown")
        section = doc.metadata.get("section", "")
        header = f"[Doc {i}] source={source}, drug={drug}"
        if section:
            header += f", section={section}"
        doc_descriptions.append(f"{header}\n{doc.content[:400]}")

    docs_text = "\n\n---\n\n".join(doc_descriptions)

    messages = [
        SystemMessage(content=GRADING_SYSTEM_PROMPT),
        HumanMessage(content=f"Query: {query}\n\nDocuments:\n\n{docs_text}"),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        grades = json.loads(content)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("grading_parse_failed", error=str(exc))
        # Fallback: mark all as relevant to avoid losing docs
        return [GradedDoc(doc=doc, is_relevant=True, reasoning="grading_failed") for doc in docs]

    # Build GradedDoc list
    graded: list[GradedDoc] = []
    grade_map = {g["index"]: g for g in grades if isinstance(g, dict) and "index" in g}

    for i, doc in enumerate(docs):
        grade_info = grade_map.get(i, {"relevant": True, "reasoning": "not_graded"})
        graded.append(
            GradedDoc(
                doc=doc,
                is_relevant=grade_info.get("relevant", True),
                reasoning=grade_info.get("reasoning", ""),
            )
        )

    relevant_count = sum(1 for g in graded if g.is_relevant)
    logger.info("grading_done", total=len(graded), relevant=relevant_count)
    return graded
