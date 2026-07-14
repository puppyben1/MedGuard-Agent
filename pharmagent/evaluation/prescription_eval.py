"""Prescription review evaluation harness.

Runs each golden case through the MedGuard-Agent prescription graph and
computes:

  - Precision / Recall / F1 (per-case and macro/micro averaged)
  - Evidence hit rate (fraction of produced findings that are verified)
  - Hallucination rate (fraction of high/critical findings unverified)
  - Average response time

Usage:
    python -m pharmagent.evaluation.prescription_eval
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pharmagent.evaluation.prescription_golden_set import PRESCRIPTION_GOLDEN_CASES
from pharmagent.logging_config import get_logger, setup_logging
from pharmagent.prescription.graph import run_prescription_review
from pharmagent.prescription.schemas import PrescriptionFinding, PrescriptionReport

logger = get_logger(__name__)


_RISK_RANK = {"low": 0, "moderate": 1, "high": 2, "critical": 3}


# ── Finding matching ────────────────────────────────────────────────

def _sets_overlap(a: list[str], b: list[str]) -> bool:
    return bool({x.lower() for x in a} & {x.lower() for x in b})


def _severity_ok(produced: str, expected: str) -> bool:
    """Match if produced == expected, or produced is MORE severe (never penalize caution)."""
    return _RISK_RANK.get(produced, -1) >= _RISK_RANK.get(expected, -1)


def _findings_match(produced: PrescriptionFinding, expected: dict) -> bool:
    if produced.finding_type != expected["finding_type"]:
        return False
    if not _sets_overlap(produced.drugs_involved, expected["drugs_involved"]):
        return False
    return _severity_ok(produced.severity, expected["severity"])


def _score_case(
    produced: list[PrescriptionFinding],
    expected: list[dict],
) -> tuple[int, int, int, list[int], list[int]]:
    """Return (tp, fp, fn, matched_produced_idx, matched_expected_idx)."""
    matched_produced: set[int] = set()
    matched_expected: set[int] = set()

    for ei, exp in enumerate(expected):
        for pi, prod in enumerate(produced):
            if pi in matched_produced:
                continue
            if _findings_match(prod, exp):
                matched_produced.add(pi)
                matched_expected.add(ei)
                break

    tp = len(matched_expected)
    fp = len(produced) - len(matched_produced)
    fn = len(expected) - len(matched_expected)
    return tp, fp, fn, sorted(matched_produced), sorted(matched_expected)


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 1.0  # no produced findings = perfect precision if no FP
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


# ── Evidence / hallucination metrics ────────────────────────────────

def _evidence_metrics(report: PrescriptionReport) -> tuple[float, float, int, int]:
    """Return (evidence_hit_rate, hallucination_rate, n_unverified_high_severity, n_high_severity)."""
    findings = report.findings
    if not findings:
        return 1.0, 0.0, 0, 0
    verified = sum(1 for f in findings if f.verified)
    hit_rate = verified / len(findings)

    high_severity = [f for f in findings if f.severity in ("high", "critical")]
    n_high = len(high_severity)
    n_unverified_high = sum(1 for f in high_severity if not f.verified)
    halluc_rate = n_unverified_high / n_high if n_high else 0.0
    return hit_rate, halluc_rate, n_unverified_high, n_high


# ── Runner ──────────────────────────────────────────────────────────

def run_prescription_evaluation(cases: list[dict] | None = None) -> list[dict]:
    """Run all golden cases; return per-case result dicts."""
    cases = cases or PRESCRIPTION_GOLDEN_CASES
    results: list[dict] = []

    for i, case in enumerate(cases):
        case_id = case.get("id", f"case_{i+1}")
        case_text = case["case_text"]
        expected = case.get("expected_findings", [])
        print(f"\n[{i+1}/{len(cases)}] {case_id}: {case_text[:80]}...")

        try:
            report = run_prescription_review(case_text)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append({
                "case_id": case_id,
                "error": str(exc),
                "expected_count": len(expected),
            })
            continue

        tp, fp, fn, matched_p, matched_e = _score_case(report.findings, expected)
        precision, recall, f1 = _prf(tp, fp, fn)
        hit_rate, halluc_rate, n_unv_high, n_high = _evidence_metrics(report)

        result = {
            "case_id": case_id,
            "expected_count": len(expected),
            "produced_count": len(report.findings),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "overall_risk": report.overall_risk_level,
            "evidence_hit_rate": round(hit_rate, 3),
            "hallucination_rate": round(halluc_rate, 3),
            "unverified_high_severity": n_unv_high,
            "total_high_severity": n_high,
            "hallucination_flagged": report.hallucination_flagged,
            "elapsed_seconds": report.elapsed_seconds,
            "findings": [
                {
                    "type": f.finding_type,
                    "severity": f.severity,
                    "drugs": f.drugs_involved,
                    "verified": f.verified,
                    "description": f.description,
                }
                for f in report.findings
            ],
            "matched_produced_idx": matched_p,
            "matched_expected_idx": matched_e,
        }
        results.append(result)
        print(
            f"  P={precision:.2f} R={recall:.2f} F1={f1:.2f} | "
            f"hit={hit_rate:.2f} halluc={halluc_rate:.2f} | "
            f"risk={report.overall_risk_level} | {report.elapsed_seconds:.1f}s"
        )

    return results


# ── Aggregation ─────────────────────────────────────────────────────

def aggregate(results: list[dict]) -> dict:
    valid = [r for r in results if "error" not in r]
    if not valid:
        return {"error": "no valid results"}

    # Micro: sum TP/FP/FN across cases
    sum_tp = sum(r["tp"] for r in valid)
    sum_fp = sum(r["fp"] for r in valid)
    sum_fn = sum(r["fn"] for r in valid)
    micro_p, micro_r, micro_f1 = _prf(sum_tp, sum_fp, sum_fn)

    # Macro: average of per-case metrics
    n = len(valid)
    macro_p = sum(r["precision"] for r in valid) / n
    macro_r = sum(r["recall"] for r in valid) / n
    macro_f1 = sum(r["f1"] for r in valid) / n

    # Evidence / hallucination / latency
    avg_hit = sum(r["evidence_hit_rate"] for r in valid) / n
    avg_halluc = sum(r["hallucination_rate"] for r in valid) / n
    sum_unv_high = sum(r["unverified_high_severity"] for r in valid)
    sum_high = sum(r["total_high_severity"] for r in valid)
    overall_halluc_rate = sum_unv_high / sum_high if sum_high else 0.0
    avg_elapsed = sum(r["elapsed_seconds"] for r in valid) / n

    return {
        "n_cases": n,
        "n_errors": len(results) - len(valid),
        "micro": {"precision": round(micro_p, 3), "recall": round(micro_r, 3), "f1": round(micro_f1, 3),
                  "tp": sum_tp, "fp": sum_fp, "fn": sum_fn},
        "macro": {"precision": round(macro_p, 3), "recall": round(macro_r, 3), "f1": round(macro_f1, 3)},
        "evidence_hit_rate": round(avg_hit, 3),
        "hallucination_rate": round(overall_halluc_rate, 3),
        "avg_hallucination_rate_per_case": round(avg_halluc, 3),
        "avg_response_seconds": round(avg_elapsed, 3),
    }


# ── Report ──────────────────────────────────────────────────────────

def generate_report(results: list[dict], agg: dict) -> str:
    lines = [
        "# MedGuard-Agent Prescription Review Evaluation",
        f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Cases evaluated: {agg.get('n_cases', 0)} (errors: {agg.get('n_errors', 0)})",
        "",
        "## Per-case results",
        "",
        "| Case | Expected | Produced | P | R | F1 | Hit | Halluc | Risk | Time(s) |",
        "|------|----------|----------|---|---|----|-----|--------|------|---------|",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['case_id']} | {r.get('expected_count', '?')} | - | - | - | - | - | - | ERROR | - |")
            continue
        lines.append(
            f"| {r['case_id']} | {r['expected_count']} | {r['produced_count']} | "
            f"{r['precision']:.2f} | {r['recall']:.2f} | {r['f1']:.2f} | "
            f"{r['evidence_hit_rate']:.2f} | {r['hallucination_rate']:.2f} | "
            f"{r['overall_risk']} | {r['elapsed_seconds']:.1f} |"
        )

    lines.extend([
        "",
        "## Aggregate metrics",
        f"- **Micro Precision:** {agg['micro']['precision']:.3f}",
        f"- **Micro Recall:** {agg['micro']['recall']:.3f}",
        f"- **Micro F1:** {agg['micro']['f1']:.3f}  (TP={agg['micro']['tp']}, FP={agg['micro']['fp']}, FN={agg['micro']['fn']})",
        f"- **Macro Precision:** {agg['macro']['precision']:.3f}",
        f"- **Macro Recall:** {agg['macro']['recall']:.3f}",
        f"- **Macro F1:** {agg['macro']['f1']:.3f}",
        f"- **Evidence hit rate (avg per case):** {agg['evidence_hit_rate']:.3f}",
        f"- **Hallucination rate (unverified high/critical / all high/critical):** {agg['hallucination_rate']:.3f}",
        f"- **Avg hallucination rate per case:** {agg['avg_hallucination_rate_per_case']:.3f}",
        f"- **Average response time:** {agg['avg_response_seconds']:.3f} s",
        "",
        "## Metric definitions",
        "- **Precision**: TP / (TP + FP) — of findings produced, how many were expected.",
        "- **Recall**: TP / (TP + FN) — of expected findings, how many were produced.",
        "- **F1**: harmonic mean of P and R.",
        "- **Severity match**: a produced finding matches an expected one if type matches, drug sets overlap, and produced severity ≥ expected (we do not penalize the system for being more cautious).",
        "- **Evidence hit rate**: fraction of produced findings with at least one supporting source document.",
        "- **Hallucination rate**: fraction of high/critical produced findings that lack evidence support — these are the dangerous ones.",
        "- **Average response time**: end-to-end graph execution time per case.",
    ])
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging("INFO")
    print("=" * 70)
    print("MedGuard-Agent — Prescription Review Evaluation")
    print("=" * 70)

    results = run_prescription_evaluation()
    agg = aggregate(results)

    os.makedirs("data", exist_ok=True)
    with open("data/prescription_eval_results.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "aggregate": agg}, f, indent=2, ensure_ascii=False)

    report = generate_report(results, agg)
    with open("prescription_eval_results.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)
    print("\nResults saved to: data/prescription_eval_results.json")
    print("Report saved to: prescription_eval_results.md")


if __name__ == "__main__":
    main()
