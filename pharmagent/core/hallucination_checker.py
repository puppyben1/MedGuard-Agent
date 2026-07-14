"""LLM-based hallucination and answer relevance checking."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from pharmagent.config import settings
from pharmagent.core.schemas import GradedDoc, SafetyAssessment
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

FAITHFULNESS_SYSTEM_PROMPT = """You are a pharmacovigilance quality auditor. Your job is to verify
that a safety assessment is FULLY grounded in the provided source documents.

Check each claim in the assessment against the source documents. A claim is grounded if
it can be directly supported by or reasonably inferred from the source text.

Respond with a JSON object:
{
  "faithful": true/false,
  "score": 0.0 to 1.0 (fraction of claims that are grounded),
  "ungrounded_claims": ["list of claims not found in sources, if any"],
  "reasoning": "brief explanation"
}

Be strict: in drug safety, ungrounded claims are dangerous.
Respond ONLY with the JSON object."""

RELEVANCE_SYSTEM_PROMPT = """You are a pharmacovigilance quality auditor. Determine whether the
safety assessment actually answers the user's original question.

Respond with a JSON object:
{
  "relevant": true/false,
  "reasoning": "brief explanation of whether the assessment addresses the query"
}

Respond ONLY with the JSON object."""


def check_faithfulness(
    assessment: SafetyAssessment,
    docs: list[GradedDoc],
    llm: ChatGroq,
) -> tuple[bool, float, str]:
    """Verify that the assessment is grounded in source documents.

    Returns (passed, score, reasoning).
    """
    source_texts = []
    for i, gd in enumerate(docs):
        if gd.is_relevant:
            source_texts.append(f"[Source {i+1}]: {gd.doc.content[:500]}")

    messages = [
        SystemMessage(content=FAITHFULNESS_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Assessment:\n{assessment.model_dump_json(indent=2)}\n\n"
                f"Source Documents:\n{''.join(source_texts)}"
            )
        ),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        data = json.loads(content)
        score = float(data.get("score", 0.0))
        passed = score >= settings.faithfulness_threshold
        reasoning = data.get("reasoning", "")
        logger.info("faithfulness_check", score=score, passed=passed)
        return passed, score, reasoning
    except Exception as exc:
        logger.warning("faithfulness_check_failed", error=str(exc))
        return True, 0.0, f"Check failed: {exc}"


def check_answer_relevance(
    query: str,
    assessment: SafetyAssessment,
    llm: ChatGroq,
) -> tuple[bool, str]:
    """Verify that the assessment actually answers the original query.

    Returns (relevant, reasoning).
    """
    messages = [
        SystemMessage(content=RELEVANCE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Original Query: {query}\n\n"
                f"Assessment:\n{assessment.model_dump_json(indent=2)}"
            )
        ),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        data = json.loads(content)
        relevant = data.get("relevant", True)
        reasoning = data.get("reasoning", "")
        logger.info("relevance_check", relevant=relevant)
        return relevant, reasoning
    except Exception as exc:
        logger.warning("relevance_check_failed", error=str(exc))
        return True, f"Check failed: {exc}"
