"""LangGraph state graph definition for the PharmAgent agentic workflow."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from pharmagent.agent.nodes import (
    analyze_and_route,
    check_hallucination,
    generate,
    grade_docs,
    reject_query,
    retrieve,
    rewrite_query,
)
from pharmagent.agent.state import AgentState
from pharmagent.config import settings
from pharmagent.core.schemas import SafetyAssessment
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)


def _should_rewrite_or_generate(state: AgentState) -> str:
    """After grading: decide whether to rewrite, or generate with what we have."""
    graded = state.get("graded_docs", [])
    relevant_count = sum(1 for g in graded if g.is_relevant)
    rewrite_count = state.get("rewrite_count", 0)

    if relevant_count >= settings.min_relevant_docs:
        return "generate"
    if rewrite_count < settings.max_rewrite_retries:
        return "rewrite_query"
    # Exhausted retries — generate with whatever we have
    return "generate"


def _should_retry_or_end(state: AgentState) -> str:
    """After hallucination check: decide whether to retry generation or finish."""
    if state.get("hallucination_passed", False):
        return "end"
    generation_count = state.get("generation_count", 0)
    if generation_count < 2:
        return "generate"
    return "end"


def build_graph() -> StateGraph:
    """Build and return the compiled PharmAgent state graph."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("analyze_and_route", analyze_and_route)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade_docs", grade_docs)
    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("generate", generate)
    builder.add_node("check_hallucination", check_hallucination)
    builder.add_node("reject_query", reject_query)

    # Define edges
    builder.set_entry_point("analyze_and_route")
    builder.add_conditional_edges(
        "analyze_and_route",
        lambda state: "reject_query" if state.get("query_type") == "invalid" else "retrieve",
    )
    
    # After reject_query, go to END
    builder.add_edge("reject_query", END)
    
    builder.add_edge("retrieve", "grade_docs")

    # After grading: conditional -> generate or rewrite
    builder.add_conditional_edges(
        "grade_docs",
        _should_rewrite_or_generate,
        {
            "generate": "generate",
            "rewrite_query": "rewrite_query",
        },
    )

    # After rewrite: go back to retrieve
    builder.add_edge("rewrite_query", "retrieve")

    # After generation: check hallucination
    builder.add_edge("generate", "check_hallucination")

    # After hallucination check: end or retry generation
    builder.add_conditional_edges(
        "check_hallucination",
        _should_retry_or_end,
        {
            "end": END,
            "generate": "generate",
        },
    )

    return builder.compile()


# Pre-built graph instance
graph = build_graph()


def run_agent(query: str) -> SafetyAssessment:
    """Run the PharmAgent on a query and return the safety assessment."""
    logger.info("agent_start", query=query[:80])

    initial_state: AgentState = {"query": query}
    final_state = graph.invoke(initial_state)

    assessment = final_state.get("assessment")
    if assessment is None:
        assessment = SafetyAssessment(
            risk_level="unknown",
            summary="Agent could not produce an assessment for this query.",
            confidence=0.0,
        )

    logger.info(
        "agent_complete",
        risk_level=assessment.risk_level,
        confidence=assessment.confidence,
        rewrites=final_state.get("rewrite_count", 0),
        generations=final_state.get("generation_count", 0),
        hallucination_passed=final_state.get("hallucination_passed", False),
    )
    return assessment
