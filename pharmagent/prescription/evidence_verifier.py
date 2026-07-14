"""Verify that each PrescriptionFinding is grounded in retrieved evidence.

For every finding produced by the prescription_checker, this module:
  1. Looks for source documents that explicitly support the finding.
  2. If the checker already attached evidence_doc_ids, confirms the linkage.
  3. Otherwise runs an LLM check across all graded docs to find a supporter.
  4. Marks the finding as verified=True/False and writes a verification reason.

Verification policy:
- Critical/high findings MUST be verified; if not, they are flagged as
  hallucination candidates and surfaced in the final report.
- Deterministic-rule findings that cannot be matched to a retrieved doc
  are kept (the rule is authoritative) but flagged as 'rule-based — no
  source doc' so the pharmacist knows where the assertion came from.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from pharmagent.core.schemas import GradedDoc
from pharmagent.logging_config import get_logger
from pharmagent.prescription.schemas import (
    PrescriptionFinding,
    VerificationResult,
)

logger = get_logger(__name__)


VERIFIER_SYSTEM_PROMPT = """You are an evidence auditor for a clinical prescription review system.

You are given:
1. A single risk finding (description + drugs involved + severity).
2. A pool of retrieved source documents, each with a stable doc id.

Your job: decide whether AT LEAST ONE of the documents explicitly supports the finding.

A document SUPPORTS the finding if it contains language that, read by a pharmacist,
would justify the finding as written. Generic background that does not address the
specific risk does NOT count.

Return JSON:
{
  "verified": true | false,
  "supporting_doc_ids": ["doc-1", ...],
  "reason": "1 sentence explaining the decision, citing the supporting doc(s) or stating the gap."
}

Respond ONLY with the JSON object."""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _doc_pool(graded_docs: list[GradedDoc]) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Return ([(doc_id, content_excerpt), ...], id -> metadata string)."""
    relevant = [d for d in graded_docs if d.is_relevant] or graded_docs[:5]
    pool: list[tuple[str, str]] = []
    meta_map: dict[str, str] = {}
    for i, gd in enumerate(relevant, start=1):
        doc_id = f"doc-{i}"
        meta = gd.doc.metadata
        source = meta.get("source", "unknown")
        drug = meta.get("drug_name", "")
        section = meta.get("section", "")
        meta_map[doc_id] = f"{source} | {drug} | {section}"
        pool.append((doc_id, gd.doc.content[:1500]))
    return pool, meta_map


def _verify_with_llm(
    finding: PrescriptionFinding,
    pool: list[tuple[str, str]],
    llm: Any,
) -> tuple[bool, list[str], str]:
    """Ask the LLM whether any doc in the pool supports the finding."""
    if not pool:
        return False, [], "No documents available to verify against."

    docs_block = "\n\n".join(f"[{doc_id}]\n{content}" for doc_id, content in pool)
    user_content = (
        f"Finding:\n"
        f"- type: {finding.finding_type}\n"
        f"- severity: {finding.severity}\n"
        f"- drugs: {', '.join(finding.drugs_involved)}\n"
        f"- description: {finding.description}\n\n"
        f"Source documents:\n\n{docs_block}"
    )

    try:
        response = llm.invoke([
            SystemMessage(content=VERIFIER_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ])
        data = json.loads(_strip_code_fence(response.content))
        verified = bool(data.get("verified", False))
        doc_ids = [d for d in data.get("supporting_doc_ids", []) if isinstance(d, str)]
        reason = data.get("reason", "")
        return verified, doc_ids, reason
    except Exception as exc:
        logger.warning("verifier_llm_failed", error=str(exc))
        return False, [], f"Verifier call failed: {exc}"


def _keyword_support_check(finding: PrescriptionFinding, pool: list[tuple[str, str]]) -> list[str]:
    """Cheap pre-check: a doc supports if the finding's key drug names + a risk
    keyword both appear in the same doc."""
    if not finding.drugs_involved:
        return []
    risk_keywords = [
        "contraindicat", "interact", "avoid", "risk", "bleed", "hepat", "renal",
        "nephrotox", "pregnan", "teratogen", "lactic acid", "black box", "warning",
        "dose adjust", "monitor",
    ]
    supporters: list[str] = []
    for doc_id, content in pool:
        content_low = content.lower()
        drug_hit = any(re.search(rf"\b{re.escape(d.lower())}\b", content_low) for d in finding.drugs_involved)
        risk_hit = any(kw in content_low for kw in risk_keywords)
        if drug_hit and risk_hit:
            supporters.append(doc_id)
    return supporters


def verify_findings(
    findings: list[PrescriptionFinding],
    graded_docs: list[GradedDoc],
    llm: Any,
) -> list[VerificationResult]:
    """Verify each finding against the graded docs. Mutates findings in place.

    Returns a VerificationResult for each finding (by index).
    """
    pool, _meta_map = _doc_pool(graded_docs)
    results: list[VerificationResult] = []

    for i, finding in enumerate(findings):
        # Path A: checker already provided doc ids → confirm via keyword pre-check
        if finding.evidence_doc_ids:
            existing = set(finding.evidence_doc_ids)
            pool_ids = {doc_id for doc_id, _ in pool}
            confirmed = sorted(existing & pool_ids)
            if confirmed:
                finding.verified = True
                finding.verification_reason = (
                    f"Confirmed by checker-supplied evidence: {', '.join(confirmed)}."
                )
                results.append(VerificationResult(
                    finding_index=i,
                    verified=True,
                    supporting_doc_ids=confirmed,
                    reason=finding.verification_reason,
                ))
                continue

        # Path B: keyword pre-check across the whole pool
        kw_supporters = _keyword_support_check(finding, pool)
        if kw_supporters:
            finding.verified = True
            finding.evidence_doc_ids = kw_supporters
            finding.verification_reason = (
                f"Keyword match in source: {', '.join(kw_supporters)}."
            )
            results.append(VerificationResult(
                finding_index=i,
                verified=True,
                supporting_doc_ids=kw_supporters,
                reason=finding.verification_reason,
            ))
            continue

        # Path C: LLM verifier as the final authority
        verified, doc_ids, reason = _verify_with_llm(finding, pool, llm)
        if verified and doc_ids:
            finding.verified = True
            finding.evidence_doc_ids = doc_ids
            finding.verification_reason = reason or "LLM-verified."
        else:
            finding.verified = False
            finding.verification_reason = reason or "No supporting document found."
        results.append(VerificationResult(
            finding_index=i,
            verified=finding.verified,
            supporting_doc_ids=finding.evidence_doc_ids,
            reason=finding.verification_reason,
        ))

    verified_count = sum(1 for r in results if r.verified)
    logger.info(
        "evidence_verification_done",
        total=len(findings),
        verified=verified_count,
        unverified=len(findings) - verified_count,
    )
    return results
