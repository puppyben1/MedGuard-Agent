"""LLM-based synthesis of safety assessments from graded documents."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from pharmagent.core.schemas import GradedDoc, SafetyAssessment
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """You are an expert pharmacovigilance analyst. Given a drug safety query
and a set of relevant source documents, synthesize a comprehensive safety assessment.

You MUST respond with a JSON object containing exactly these fields:
{
  "risk_level": "low" | "moderate" | "high" | "critical",
  "summary": "2-4 sentence summary of the key safety findings",
  "evidence": [
    {"finding": "specific finding", "source": "source description"}
  ],
  "contraindications": ["list of specific contraindications found"],
  "monitoring": ["recommended monitoring actions"],
  "citations": ["source references in format: [Source] description"],
  "confidence": 0.0 to 1.0
}

CRITICAL RISK CLASSIFICATION RULES (mandatory — override your own judgment):
- "critical" MUST be used for: FDA black box warnings, pregnancy with teratogenic drugs
  (ACE inhibitors, ARBs, warfarin, methotrexate), absolute contraindications,
  known lethal combinations, and any scenario where proceeding could cause death or
  irreversible harm.
- "high" MUST be used for: significant drug-drug interactions with bleeding or
  organ damage risk, drugs in pregnancy generally, renal/hepatic impairment with
  nephrotoxic/hepatotoxic drugs, supratherapeutic INR scenarios.
- "moderate" is for: dose adjustments needed, monitoring-manageable interactions,
  relative (not absolute) contraindications.
- "low" is ONLY for: well-tolerated drugs with no significant interactions for the
  given patient profile.
- When in doubt between two levels, ALWAYS choose the higher risk level.

Additional rules:
- Every claim MUST be supported by at least one source document. Do not invent information.
- If the evidence is insufficient or conflicting, set risk_level to the higher risk and lower confidence.
- Include specific drug names, dosages, and patient populations when available.
- For drug interactions, describe the mechanism and clinical significance.
- citations should reference the source documents provided (e.g., "[DailyMed - warfarin] warnings section")
- confidence should reflect how well the sources cover the query (1.0 = comprehensive coverage, 0.5 = partial)

Respond ONLY with the JSON object."""


def synthesize_safety_assessment(
    query: str,
    docs: list[GradedDoc],
    llm: ChatGroq,
    missing_drugs: list[str] | None = None,
    hallucination_feedback: str | None = None,
) -> SafetyAssessment:
    """Synthesize a structured safety assessment from graded, relevant documents."""
    # Build context from relevant docs only
    relevant_docs = [d for d in docs if d.is_relevant]
    if not relevant_docs:
        relevant_docs = docs[:3]  # fallback to top docs if none graded relevant

    context_parts = []
    for i, gd in enumerate(relevant_docs):
        source = gd.doc.metadata.get("source", "unknown")
        drug = gd.doc.metadata.get("drug_name", "unknown")
        section = gd.doc.metadata.get("section", "")
        header = f"[Source {i+1}: {source} - {drug}"
        if section:
            header += f" ({section})"
        header += "]"
        context_parts.append(f"{header}\n{gd.doc.content}")

    context = "\n\n---\n\n".join(context_parts)

    # Build the user message with missing-drug context if applicable
    user_content = f"Query: {query}\n\nSource Documents:\n\n{context}"
    if missing_drugs:
        user_content += (
            f"\n\nIMPORTANT: The following drugs mentioned in the query have NO data "
            f"in the knowledge base: {', '.join(missing_drugs)}. You MUST NOT make "
            f"any safety claims about these drugs. State clearly that data is unavailable "
            f"for them and lower your confidence score accordingly."
        )

    if hallucination_feedback:
        user_content += (
            f"\n\nCRITICAL FIX REQUIRED (PREVIOUS ATTEMPT FAILED):\n"
            f"Your previous answer contained ungrounded or irrelevant claims. "
            f"Feedback: {hallucination_feedback}\n"
            f"You MUST fix these issues in your new response by strictly grounding "
            f"your answers in the provided text."
        )

    messages = [
        SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        data = json.loads(content)
        assessment = SafetyAssessment(**data)
        logger.info(
            "synthesis_done",
            risk_level=assessment.risk_level,
            confidence=assessment.confidence,
        )
        return assessment
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("synthesis_parse_failed", error=str(exc))
        return SafetyAssessment(
            risk_level="unknown",
            summary="Failed to synthesize assessment. Please review the source documents directly.",
            confidence=0.0,
        )
