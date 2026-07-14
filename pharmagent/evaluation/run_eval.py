"""Run RAGAS evaluation on the golden query set."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pharmagent.agent.graph import graph
from pharmagent.agent.state import AgentState
from pharmagent.evaluation.golden_set import GOLDEN_QUERIES
from pharmagent.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def run_evaluation() -> list[dict]:
    """Run all golden queries through the agent and collect results."""
    results = []

    for i, gq in enumerate(GOLDEN_QUERIES):
        query = gq["query"]
        print(f"\n[{i+1}/{len(GOLDEN_QUERIES)}] {query[:60]}...")

        try:
            initial_state: AgentState = {"query": query}
            final_state = graph.invoke(initial_state)

            assessment = final_state.get("assessment")
            graded_docs = final_state.get("graded_docs", [])
            relevant_docs = [g for g in graded_docs if g.is_relevant]

            # Compute basic metrics
            keyword_hits = 0
            if assessment:
                assessment_text = (
                    f"{assessment.summary} "
                    f"{' '.join(assessment.contraindications)} "
                    f"{' '.join(str(e) for e in assessment.evidence)}"
                ).lower()
                for kw in gq["expected_keywords"]:
                    if kw.lower() in assessment_text:
                        keyword_hits += 1

            expected = gq["expected_keywords"]
            keyword_coverage = keyword_hits / len(expected) if expected else 0

            result = {
                "query": query,
                "query_type": gq["query_type"],
                "risk_level": assessment.risk_level if assessment else "failed",
                "confidence": assessment.confidence if assessment else 0.0,
                "faithfulness_score": final_state.get("faithfulness_score", 0.0),
                "hallucination_passed": final_state.get("hallucination_passed", False),
                "keyword_coverage": round(keyword_coverage, 2),
                "relevant_docs_count": len(relevant_docs),
                "total_docs_retrieved": len(graded_docs),
                "rewrite_count": final_state.get("rewrite_count", 0),
                "generation_count": final_state.get("generation_count", 0),
            }
            results.append(result)
            print(f"  Risk: {result['risk_level']} | Confidence: {result['confidence']:.0%} | "
                  f"Keywords: {keyword_coverage:.0%} | Faith: {result['faithfulness_score']:.2f}")

        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append({
                "query": query,
                "query_type": gq["query_type"],
                "error": str(exc),
            })

    return results


def generate_report(results: list[dict]) -> str:
    """Generate a markdown evaluation report."""
    lines = [
        "# PharmAgent Evaluation Results",
        f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Queries evaluated: {len(results)}",
        "",
        "| # | Query | Type | Risk | Conf. | Faith. | Keywords | Docs |",
        "|---|-------|------|------|-------|--------|----------|------|",
    ]

    for i, r in enumerate(results):
        if "error" in r:
            lines.append(
                f"| {i+1} | {r['query'][:40]}... "
                f"| {r['query_type']} | ERROR | - | - | - | - |"
            )
            continue
        lines.append(
            f"| {i+1} | {r['query'][:40]}... | {r['query_type']} | "
            f"{r['risk_level']} | {r['confidence']:.0%} | "
            f"{r['faithfulness_score']:.2f} | {r['keyword_coverage']:.0%} | "
            f"{r['relevant_docs_count']}/{r['total_docs_retrieved']} |"
        )

    # Summary stats
    valid = [r for r in results if "error" not in r]
    if valid:
        avg_confidence = sum(r["confidence"] for r in valid) / len(valid)
        avg_faithfulness = sum(r["faithfulness_score"] for r in valid) / len(valid)
        avg_keywords = sum(r["keyword_coverage"] for r in valid) / len(valid)
        pass_rate = sum(1 for r in valid if r["hallucination_passed"]) / len(valid)

        lines.extend([
            "",
            "## Summary Metrics",
            f"- **Average Confidence:** {avg_confidence:.0%}",
            f"- **Average Faithfulness:** {avg_faithfulness:.2f}",
            f"- **Average Keyword Coverage:** {avg_keywords:.0%}",
            f"- **Hallucination Check Pass Rate:** {pass_rate:.0%}",
            f"- **Queries with Errors:** {len(results) - len(valid)}/{len(results)}",
        ])

    return "\n".join(lines)


def main() -> None:
    setup_logging("INFO")
    print("=" * 60)
    print("PharmAgent Evaluation")
    print("=" * 60)

    results = run_evaluation()

    # Save raw results
    os.makedirs("data", exist_ok=True)
    with open("data/eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Generate and save report
    report = generate_report(results)
    with open("evaluation_results.md", "w") as f:
        f.write(report)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)
    print("\nResults saved to: data/eval_results.json")
    print("Report saved to: evaluation_results.md")


if __name__ == "__main__":
    main()
