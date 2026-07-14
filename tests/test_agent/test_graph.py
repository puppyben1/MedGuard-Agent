"""End-to-end smoke test for the PharmAgent graph."""

import pytest

from pharmagent.agent.graph import run_agent


def _can_run_agent() -> bool:
    """Check if the agent can run (data + API key)."""
    try:
        from pharmagent.config import settings
        from pharmagent.core.vectorstore import get_collection

        if not settings.groq_api_key:
            return False
        collection = get_collection("drug_labels")
        return collection.count() > 0
    except Exception:
        return False


@pytest.mark.skipif(
    not _can_run_agent(),
    reason="ChromaDB not populated or Groq key not set",
)
def test_agent_produces_assessment():
    """Run a simple query and verify the agent produces a structured assessment."""
    assessment = run_agent("What are the contraindications for warfarin?")
    assert assessment.risk_level in ("low", "moderate", "high", "critical", "unknown")
    assert len(assessment.summary) > 0
    assert assessment.confidence >= 0.0
