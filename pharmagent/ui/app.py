"""Streamlit UI for the PharmAgent drug safety intelligence system."""

import streamlit as st

from pharmagent.agent.graph import run_agent
from pharmagent.agent.llm import budget_tracker
from pharmagent.core.schemas import SafetyAssessment
from pharmagent.logging_config import setup_logging

setup_logging("INFO")

RISK_COLORS = {
    "low": "#28a745",
    "moderate": "#ffc107",
    "high": "#fd7e14",
    "critical": "#dc3545",
    "unknown": "#6c757d",
}

EXAMPLE_QUERIES = [
    "What are the contraindications for metformin in patients with renal impairment?",
    "What are the risks of taking warfarin and aspirin together?",
    "Is semaglutide safe for a patient with a history of pancreatitis?",
    "What are the common adverse effects of lisinopril?",
    "Is metformin safe for a 68-year-old patient with stage 3 CKD who is also taking lisinopril and warfarin?",
]

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="PharmAgent — Drug Safety Intelligence",
    page_icon="💊",
    layout="wide",
)

st.title("💊 PharmAgent")
st.caption("Autonomous drug safety intelligence powered by agentic RAG")

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Example Queries")
    for eq in EXAMPLE_QUERIES:
        if st.button(eq, key=eq, use_container_width=True):
            st.session_state["query_input"] = eq

    st.divider()
    st.header("Token Budget")
    gen_remaining = budget_tracker.generator_budget_remaining
    router_remaining = budget_tracker.router_budget_remaining
    st.metric("Generator (70B) calls left", f"{gen_remaining:,}")
    st.metric("Router (8B) calls left", f"{router_remaining:,}")

    if "query_count" in st.session_state:
        st.metric("Queries this session", st.session_state["query_count"])

# ── Main input ────────────────────────────────────────────────────────
query = st.text_area(
    "Enter your drug safety question:",
    value=st.session_state.get("query_input", ""),
    height=80,
    placeholder="e.g., What are the risks of taking warfarin and aspirin together?",
)

run_clicked = st.button("🔍 Analyze", type="primary", use_container_width=True)

if run_clicked and query.strip():
    st.session_state["query_count"] = st.session_state.get("query_count", 0) + 1

    with st.spinner("Running PharmAgent... (querying, grading, synthesizing)"):
        assessment: SafetyAssessment = run_agent(query.strip())

    # ── Results ───────────────────────────────────────────────────
    st.divider()

    # Risk level badge
    color = RISK_COLORS.get(assessment.risk_level, "#6c757d")
    st.markdown(
        f'### Risk Level: <span style="color:{color}; font-weight:bold;">'
        f"{assessment.risk_level.upper()}</span>"
        f" &nbsp; (confidence: {assessment.confidence:.0%})",
        unsafe_allow_html=True,
    )

    # Summary
    st.markdown("#### Summary")
    st.info(assessment.summary)

    # Evidence
    if assessment.evidence:
        st.markdown("#### Evidence")
        for ev in assessment.evidence:
            finding = ev.get("finding", "")
            source = ev.get("source", "")
            st.markdown(f"- **{finding}** — *{source}*")

    # Contraindications
    if assessment.contraindications:
        st.markdown("#### Contraindications")
        for ci in assessment.contraindications:
            st.markdown(f"- {ci}")

    # Monitoring
    if assessment.monitoring:
        st.markdown("#### Recommended Monitoring")
        for mon in assessment.monitoring:
            st.markdown(f"- {mon}")

    # Citations
    if assessment.citations:
        with st.expander("📚 Citations", expanded=False):
            for cit in assessment.citations:
                st.markdown(f"- {cit}")

elif run_clicked:
    st.warning("Please enter a query.")
