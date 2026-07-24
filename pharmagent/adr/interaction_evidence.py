"""Load user-provided DDI/DrugBank-style interaction evidence files."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pharmagent.adr.schemas import InteractionEvidenceRecord, InteractionEvidenceStatus, Severity

DEFAULT_INTERACTION_EVIDENCE_PATH = Path("data/interactions/drug_interactions.csv")


def interaction_evidence_status(source_path: str = "") -> InteractionEvidenceStatus:
    path = _resolve_path(source_path)
    if not path.exists():
        return InteractionEvidenceStatus(available=False, source_path=str(path))
    try:
        records = load_interaction_evidence(str(path))
    except Exception as exc:  # noqa: BLE001
        return InteractionEvidenceStatus(available=False, source_path=str(path), error=str(exc))
    return InteractionEvidenceStatus(available=True, source_path=str(path), record_count=len(records))


def load_interaction_evidence(source_path: str = "") -> list[InteractionEvidenceRecord]:
    path = _resolve_path(source_path)
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        rows = _read_jsonl(path)
    else:
        rows = _read_csv(path)
    records: list[InteractionEvidenceRecord] = []
    for row in rows:
        drugs = _extract_drugs(row)
        risk = _first_value(row, "risk", "adverse_event", "adr", "effect", "outcome")
        if len(drugs) < 2 or not risk:
            continue
        records.append(
            InteractionEvidenceRecord(
                drugs=drugs,
                risk=risk.lower(),
                severity=_severity(_first_value(row, "severity", "level")),
                mechanism=_first_value(row, "mechanism", "description", "evidence", "sentence"),
                evidence_source=_first_value(row, "evidence_source", "source", "database") or "external_interaction_file",
                recommendation=_first_value(row, "recommendation", "management", "action"),
                source_type=_first_value(row, "source_type") or "user_provided_external_evidence",
            )
        )
    return records


def match_interaction_evidence(
    drugs: list[str],
    source_path: str = "",
) -> list[InteractionEvidenceRecord]:
    drug_set = {drug.lower() for drug in drugs}
    records = load_interaction_evidence(source_path)
    return [record for record in records if set(record.drugs).issubset(drug_set)]


def _resolve_path(source_path: str) -> Path:
    return Path(source_path) if source_path else DEFAULT_INTERACTION_EVIDENCE_PATH


def _read_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            if isinstance(raw, dict):
                rows.append(raw)
    return rows


def _extract_drugs(row: dict[str, object]) -> list[str]:
    explicit = _first_value(row, "drugs", "drug_pair")
    if explicit:
        parts = [item.strip().lower() for item in explicit.replace("+", ";").replace("|", ";").split(";")]
        return sorted({item for item in parts if item})
    candidates = [
        _first_value(row, "drug_a", "drug1", "left_drug", "subject"),
        _first_value(row, "drug_b", "drug2", "right_drug", "object"),
        _first_value(row, "drug_c", "drug3"),
    ]
    return sorted({item.strip().lower() for item in candidates if item.strip()})


def _severity(value: str) -> Severity:
    normalized = value.strip().lower()
    if normalized in {"low", "moderate", "high", "critical"}:
        return normalized  # type: ignore[return-value]
    if normalized in {"major", "severe"}:
        return "high"
    if normalized in {"contraindicated", "life-threatening"}:
        return "critical"
    if normalized in {"minor"}:
        return "low"
    return "moderate"


def _first_value(row: dict[str, object], *keys: str) -> str:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
