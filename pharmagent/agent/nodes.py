"""LangGraph node functions for the PharmAgent agentic workflow."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from pharmagent.agent.llm import budget_tracker, get_generator_llm, get_router_llm
from pharmagent.agent.state import AgentState
from pharmagent.config import settings
from pharmagent.core.document_grader import grade_documents as core_grade
from pharmagent.core.hallucination_checker import check_answer_relevance, check_faithfulness
from pharmagent.core.hybrid_retriever import hybrid_search
from pharmagent.core.query_rewriter import rewrite_query as core_rewrite
from pharmagent.core.safety_guardrails import (
    enforce_safety_guardrails,
    extract_drug_names_from_query,
    get_indexed_drugs,
    is_query_valid,
)
from pharmagent.core.synthesizer import synthesize_safety_assessment
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

ROUTER_SYSTEM_PROMPT = """You are a drug safety query classifier. Classify the query into one of:
- "single_drug": about a single drug's safety, side effects, dosing, or contraindications
- "multi_drug_interaction": about interactions between 2+ drugs
- "patient_specific": about drug safety for a specific patient profile (age, conditions, medications)

Also determine which knowledge sources to search:
- "drug_labels": FDA drug label information (warnings, interactions, dosing)
- "pubmed_literature": biomedical research literature
- "clinical_guidelines": clinical practice guidelines

And extract ALL pharmaceutical drug names mentioned in the user query. Include generic and brand names.

Respond with JSON:
{
  "query_type": "single_drug" | "multi_drug_interaction" | "patient_specific",
  "target_collections": ["drug_labels", "pubmed_literature", "clinical_guidelines"],
  "drugs_mentioned": ["list of exact drug names mentioned"]
}

For single_drug queries, always include drug_labels. For interactions, include all three.
For patient_specific, include all three.
Respond ONLY with the JSON object."""


# ── Node 1: Analyze & Route ──────────────────────────────────────────

def analyze_and_route(state: AgentState) -> dict:
    """Classify the query and determine which knowledge sources to search."""
    query = state["query"]
    llm = get_router_llm()
    budget_tracker.record_router_call()

    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=f"Query: {query}"),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        data = json.loads(content)
        query_type = data.get("query_type", "single_drug")
        target_collections = data.get("target_collections", ["drug_labels"])
        drugs_mentioned = data.get("drugs_mentioned", [])
    except Exception as exc:
        logger.warning("routing_failed", error=str(exc))
        query_type = "patient_specific"
        target_collections = ["drug_labels", "pubmed_literature", "clinical_guidelines"]
        drugs_mentioned = []

    # ── Drug coverage validation ──
    indexed_drugs = get_indexed_drugs()
    detected, missing = extract_drug_names_from_query(query, indexed_drugs)
    
    # Supplement with LLM-extracted drugs to catch rare/made-up drugs bypassing regex
    detected_lower = {d.lower() for d in detected}
    missing_lower = {m.lower() for m in missing}
    for d in drugs_mentioned:
        dl = d.lower()
        if dl not in detected_lower and dl not in missing_lower:
            # We don't want to add broad terms like "drug", "medicine", or class names if they weren't caught
            if len(d) > 3 and not any(w in dl for w in ["inhibitor", "blocker", "nsaid", "agonist"]):
                if dl in indexed_drugs:
                    detected.append(d)
                else:
                    missing.append(d)

    if missing:
        logger.warning(
            "missing_drugs_detected",
            detected=detected,
            missing=missing,
            indexed=sorted(indexed_drugs),
        )

    valid, reject_reason = is_query_valid(query, detected, missing)
    if not valid:
        logger.warning("query_rejected", reason=reject_reason)
        query_type = "invalid"

    logger.info(
        "routed",
        query_type=query_type,
        collections=target_collections,
        detected_drugs=detected,
        missing_drugs=missing,
    )
    return {
        "query_type": query_type,
        "target_collections": target_collections,
        "current_query": query,
        "rewrite_count": 0,
        "generation_count": 0,
        "detected_drugs": detected,
        "missing_drugs": missing,
        "error": reject_reason if not valid else None,
    }


# ── Node 2: Retrieve ─────────────────────────────────────────────────

def retrieve(state: AgentState) -> dict:
    """Run hybrid search across target collections."""
    query = state.get("current_query", state["query"])
    collections = state.get("target_collections", ["drug_labels"])

    docs = hybrid_search(query, collections)
    logger.info("retrieved", count=len(docs), query=query[:50])
    return {"retrieved_docs": docs}


# ── Node 3: Grade Documents ──────────────────────────────────────────

def grade_docs(state: AgentState) -> dict:
    """Grade retrieved documents for relevance."""
    query = state.get("current_query", state["query"])
    docs = state.get("retrieved_docs", [])

    llm = get_router_llm()
    budget_tracker.record_router_call()

    graded = core_grade(query, docs, llm)
    return {"graded_docs": graded}


# ── Node 4: Rewrite Query ────────────────────────────────────────────

def rewrite_query(state: AgentState) -> dict:
    """Rewrite the query for better retrieval."""
    query = state.get("current_query", state["query"])
    rewrite_count = state.get("rewrite_count", 0)

    relevant_count = sum(1 for g in state.get("graded_docs", []) if g.is_relevant)
    context = (
        f"Only {relevant_count} relevant docs found. "
        f"Need at least {settings.min_relevant_docs}."
    )

    llm = get_router_llm()
    budget_tracker.record_router_call()

    new_query = core_rewrite(query, context, llm)
    return {
        "current_query": new_query,
        "rewrite_count": rewrite_count + 1,
    }


# ── Node 5: Generate ─────────────────────────────────────────────────

def generate(state: AgentState) -> dict:
    """Synthesize a safety assessment from graded documents, then enforce safety guardrails."""
    query = state["query"]
    graded_docs = state.get("graded_docs", [])
    generation_count = state.get("generation_count", 0)
    missing_drugs = state.get("missing_drugs", [])
    hallucination_feedback = state.get("hallucination_feedback")

    llm = get_generator_llm()
    budget_tracker.record_generator_call()

    assessment = synthesize_safety_assessment(
        query, graded_docs, llm, missing_drugs, hallucination_feedback
    )

    # Deterministic safety guardrails — overrides LLM when it under-reports risk
    assessment = enforce_safety_guardrails(query, assessment, missing_drugs)

    return {
        "assessment": assessment,
        "generation_count": generation_count + 1,
    }


# ── Node 6: Check Hallucination ──────────────────────────────────────

def check_hallucination(state: AgentState) -> dict:
    """Verify faithfulness and answer relevance."""
    assessment = state.get("assessment")
    graded_docs = state.get("graded_docs", [])
    query = state["query"]

    if assessment is None:
        return {"hallucination_passed": False, "faithfulness_score": 0.0}

    llm = get_router_llm()
    budget_tracker.record_router_call()

    faith_passed, faith_score, faith_reason = check_faithfulness(assessment, graded_docs, llm)

    budget_tracker.record_router_call()
    relevant, rel_reason = check_answer_relevance(query, assessment, llm)

    passed = faith_passed and relevant
    
    feedback_parts = []
    if not faith_passed:
        feedback_parts.append(f"Faithfulness issue: {faith_reason}")
    if not relevant:
        feedback_parts.append(f"Relevance issue: {rel_reason}")
    feedback = " | ".join(feedback_parts) if feedback_parts else ""

    logger.info(
        "hallucination_check",
        faith_score=faith_score,
        faith_passed=faith_passed,
        relevant=relevant,
        overall_passed=passed,
    )
    return {
        "hallucination_passed": passed,
        "faithfulness_score": faith_score,
        "hallucination_feedback": feedback,
    }

# ── Node 7: Reject Query ─────────────────────────────────────────────

def reject_query(state: AgentState) -> dict:
    """Return a deterministic fallback safety assessment for rejected queries."""
    reason = state.get("error", "Query violated safety guardrails.")
    logger.info("reject_node_executed", reason=reason)
    from pharmagent.core.schemas import SafetyAssessment
    return {
        "assessment": SafetyAssessment(
            risk_level="unknown",
            summary=f"QUERY REJECTED: {reason}",
            confidence=0.0,
        )
    }
