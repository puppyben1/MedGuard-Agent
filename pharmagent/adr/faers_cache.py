"""Offline FAERS quarterly cache and disproportionality signal calculation.

This module reads user-provided FAERS quarterly ASCII/CSV exports into a local
SQLite cache. It never downloads data and never fabricates signal metrics when
the cache is missing.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, Field

from pharmagent.adr.schemas import DistributionPoint, OpenFDASignal, TrendPoint

FAERS_DIR = Path("data/faers")
DEFAULT_CACHE_PATH = FAERS_DIR / "faers.sqlite"
DEFAULT_MANIFEST_PATH = FAERS_DIR / "manifest.json"
SERIOUS_OUTCOMES = {"DE", "LT", "HO", "DS", "CA", "RI"}


class FAERSStatus(BaseModel):
    available: bool
    source_type: str = "offline_faers_quarterly"
    cache_path: str = str(DEFAULT_CACHE_PATH)
    manifest_path: str = str(DEFAULT_MANIFEST_PATH)
    source_label: str = ""
    case_count: int = 0
    drug_case_count: int = 0
    reaction_case_count: int = 0
    outcome_case_count: int = 0
    deduplicated: bool = True
    error: str = ""
    manifest: dict[str, object] = Field(default_factory=dict)


class FAERSSignalRequest(BaseModel):
    drug: str
    adr: str


class FAERSSignalResponse(OpenFDASignal):
    source: str = "FAERS offline cache"
    source_type: str = "offline_faers_quarterly"
    deduplicated: bool = True
    contingency_table: dict[str, int] = Field(default_factory=dict)
    serious_ratio: float = 0.0


@dataclass(frozen=True)
class _SourceFiles:
    demo: list[Path]
    drug: list[Path]
    reac: list[Path]
    outc: list[Path]


def faers_status(cache_path: Path = DEFAULT_CACHE_PATH) -> FAERSStatus:
    manifest_path = cache_path.parent / "manifest.json"
    if not cache_path.exists():
        return FAERSStatus(
            available=False,
            cache_path=str(cache_path),
            manifest_path=str(manifest_path),
            error="未找到 FAERS 离线缓存；请先运行 scripts/build_faers_cache.py。",
        )
    try:
        with sqlite3.connect(cache_path) as conn:
            counts = {
                "case_count": _scalar(conn, "SELECT COUNT(*) FROM cases"),
                "drug_case_count": _scalar(conn, "SELECT COUNT(*) FROM drug_case"),
                "reaction_case_count": _scalar(conn, "SELECT COUNT(*) FROM reaction_case"),
                "outcome_case_count": _scalar(conn, "SELECT COUNT(*) FROM outcome_case"),
            }
        manifest = _read_manifest(manifest_path)
        return FAERSStatus(
            available=True,
            cache_path=str(cache_path),
            manifest_path=str(manifest_path),
            source_label=str(manifest.get("source_label", "")),
            manifest=manifest,
            **counts,
        )
    except Exception as exc:  # noqa: BLE001
        return FAERSStatus(
            available=False,
            cache_path=str(cache_path),
            manifest_path=str(manifest_path),
            error=f"FAERS 缓存读取失败：{exc}",
        )


def query_faers_signal(
    drug: str,
    adr: str,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> FAERSSignalResponse:
    drug_norm = _norm(drug)
    adr_norm = _norm(adr)
    if not drug_norm or not adr_norm:
        raise ValueError("drug 和 adr 不能为空")
    if not cache_path.exists():
        raise FileNotFoundError("未找到 FAERS 离线缓存；请先运行 scripts/build_faers_cache.py。")

    with sqlite3.connect(cache_path) as conn:
        total = _scalar(conn, "SELECT COUNT(*) FROM cases")
        drug_total = _count_distinct(
            conn,
            "SELECT case_key FROM drug_case WHERE drug_norm LIKE ?",
            (f"%{drug_norm}%",),
        )
        adr_total = _count_distinct(
            conn,
            "SELECT case_key FROM reaction_case WHERE reaction_norm LIKE ?",
            (f"%{adr_norm}%",),
        )
        pair_cases = _case_keys(
            conn,
            """
            SELECT DISTINCT d.case_key
            FROM drug_case d
            JOIN reaction_case r ON r.case_key = d.case_key
            WHERE d.drug_norm LIKE ? AND r.reaction_norm LIKE ?
            """,
            (f"%{drug_norm}%", f"%{adr_norm}%"),
        )
        a = len(pair_cases)
        b = max(drug_total - a, 0)
        c = max(adr_total - a, 0)
        d = max(total - a - b - c, 0)
        serious_count = _count_serious(conn, pair_cases)
        death_count = _count_outcomes(conn, pair_cases, {"DE"})
        hospitalization_count = _count_outcomes(conn, pair_cases, {"HO"})
        yearly_trend = _yearly_trend(conn, pair_cases)
        sex_distribution = _sex_distribution(conn, pair_cases)

    ror = _safe_ratio(a * d, b * c)
    prr = _safe_ratio(a * (c + d), c * (a + b))
    signal_level = _signal_level(a, ror)
    serious_ratio = round(serious_count / a, 4) if a else 0.0
    manifest = _read_manifest(cache_path.parent / "manifest.json")
    source_label = str(manifest.get("source_label") or "FAERS offline cache")

    return FAERSSignalResponse(
        drug=drug,
        adr=adr,
        source_mode="offline_faers",
        report_count=a,
        serious_count=serious_count,
        death_count=death_count,
        hospitalization_count=hospitalization_count,
        ror=ror,
        prr=prr,
        signal_level=signal_level,
        yearly_trend=yearly_trend,
        sex_distribution=sex_distribution,
        age_distribution=[],
        clinical_interpretation=(
            f"{source_label} 离线缓存中检出 {drug} / {adr} 组合报告 {a} 例；"
            f"ROR={ror if ror is not None else 'NA'}，PRR={prr if prr is not None else 'NA'}。"
            "该结果为自发报告不成比例分析，只提示报告关联，不证明因果关系。"
        ),
        limitations=[
            "FAERS 自发报告存在漏报、重复报告、适应证偏倚和报告刺激等限制，不能直接证明因果关系。",
            "当前第一版缓存按 caseid/primaryid 去重并计算 ROR/PRR，未做混杂校正和用药暴露量校正。",
            "仅统计用户导入到本地缓存的季度数据；未导入的季度不会计入结果。",
        ],
        source=source_label,
        contingency_table={"a": a, "b": b, "c": c, "d": d},
        serious_ratio=serious_ratio,
    )


def build_faers_cache(
    source: Path,
    output: Path = DEFAULT_CACHE_PATH,
    source_label: str = "",
) -> FAERSStatus:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with TemporaryDirectory() as tmp:
        root = _prepare_source(source, Path(tmp))
        files = _discover_files(root)
        if not files.drug or not files.reac:
            raise ValueError("FAERS 数据源至少需要 DRUG 和 REAC 文件。")

        with sqlite3.connect(output) as conn:
            _init_schema(conn)
            case_keys: set[str] = set()
            for row in _iter_rows(files.demo):
                case_key = _case_key(row)
                if not case_key:
                    continue
                case_keys.add(case_key)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO cases(case_key, primaryid, caseid, year, sex, serious)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (
                        case_key,
                        _get(row, "primaryid"),
                        _get(row, "caseid"),
                        _extract_year(_get(row, "fda_dt") or _get(row, "rept_dt") or _get(row, "event_dt")),
                        _get(row, "sex"),
                    ),
                )
            for row in _iter_rows(files.drug):
                case_key = _case_key(row)
                drug_name = _get(row, "drugname") or _get(row, "prod_ai")
                if not case_key or not drug_name:
                    continue
                case_keys.add(case_key)
                _ensure_case(conn, case_key, row)
                conn.execute(
                    "INSERT OR IGNORE INTO drug_case(case_key, drug_name, drug_norm, role_cod) VALUES (?, ?, ?, ?)",
                    (case_key, drug_name, _norm(drug_name), _get(row, "role_cod")),
                )
            for row in _iter_rows(files.reac):
                case_key = _case_key(row)
                reaction = _get(row, "pt") or _get(row, "reactionmeddrapt")
                if not case_key or not reaction:
                    continue
                case_keys.add(case_key)
                _ensure_case(conn, case_key, row)
                conn.execute(
                    "INSERT OR IGNORE INTO reaction_case(case_key, reaction, reaction_norm) VALUES (?, ?, ?)",
                    (case_key, reaction, _norm(reaction)),
                )
            for row in _iter_rows(files.outc):
                case_key = _case_key(row)
                code = (_get(row, "outc_cod") or "").upper()
                if not case_key or not code:
                    continue
                case_keys.add(case_key)
                _ensure_case(conn, case_key, row)
                conn.execute(
                    "INSERT OR IGNORE INTO outcome_case(case_key, outc_cod) VALUES (?, ?)",
                    (case_key, code),
                )
                if code in SERIOUS_OUTCOMES:
                    conn.execute("UPDATE cases SET serious = 1 WHERE case_key = ?", (case_key,))
            conn.commit()
            _create_indexes(conn)

    counts = faers_status(output).model_dump()
    manifest = {
        **counts,
        "source_type": "offline_faers_quarterly",
        "source_label": source_label or source.name,
        "source_path": str(source),
        "cache_path": str(output),
        "deduplicated": True,
        "built_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    manifest_path = output.parent / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return faers_status(output)


def _prepare_source(source: Path, tmp: Path) -> Path:
    if source.is_dir():
        return source
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            zf.extractall(tmp)
        return tmp
    raise ValueError("FAERS source 必须是目录或 zip 文件。")


def _discover_files(root: Path) -> _SourceFiles:
    paths = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".csv", ".tsv"}]
    return _SourceFiles(
        demo=[p for p in paths if _kind(p) == "demo"],
        drug=[p for p in paths if _kind(p) == "drug"],
        reac=[p for p in paths if _kind(p) == "reac"],
        outc=[p for p in paths if _kind(p) == "outc"],
    )


def _kind(path: Path) -> str:
    name = path.name.lower()
    for prefix in ("demo", "drug", "reac", "outc"):
        if name.startswith(prefix):
            return prefix
    return ""


def _iter_rows(files: Iterable[Path]) -> Iterator[dict[str, str]]:
    for path in files:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            sample = handle.readline()
            if not sample:
                continue
            delimiter = "$" if "$" in sample else "\t" if "\t" in sample else ","
            handle.seek(0)
            reader = csv.DictReader(handle, delimiter=delimiter)
            for row in reader:
                yield {_norm_key(key): (value or "").strip() for key, value in row.items() if key}


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE cases (
          case_key TEXT PRIMARY KEY,
          primaryid TEXT,
          caseid TEXT,
          year INTEGER,
          sex TEXT,
          serious INTEGER DEFAULT 0
        );
        CREATE TABLE drug_case (
          case_key TEXT,
          drug_name TEXT,
          drug_norm TEXT,
          role_cod TEXT,
          UNIQUE(case_key, drug_norm)
        );
        CREATE TABLE reaction_case (
          case_key TEXT,
          reaction TEXT,
          reaction_norm TEXT,
          UNIQUE(case_key, reaction_norm)
        );
        CREATE TABLE outcome_case (
          case_key TEXT,
          outc_cod TEXT,
          UNIQUE(case_key, outc_cod)
        );
        """
    )


def _create_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_drug_norm ON drug_case(drug_norm);
        CREATE INDEX IF NOT EXISTS idx_reaction_norm ON reaction_case(reaction_norm);
        CREATE INDEX IF NOT EXISTS idx_outcome_case ON outcome_case(case_key);
        """
    )


def _ensure_case(conn: sqlite3.Connection, case_key: str, row: dict[str, str]) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO cases(case_key, primaryid, caseid, serious) VALUES (?, ?, ?, 0)",
        (case_key, _get(row, "primaryid"), _get(row, "caseid")),
    )


def _case_key(row: dict[str, str]) -> str:
    caseid = _get(row, "caseid")
    primaryid = _get(row, "primaryid")
    if caseid:
        return f"case:{caseid}"
    if primaryid:
        return f"primary:{primaryid}"
    return ""


def _get(row: dict[str, str], key: str) -> str:
    return row.get(_norm_key(key), "")


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", key.strip().lower())


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _extract_year(value: str) -> int | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 4:
        year = int(digits[:4])
        if 1960 <= year <= 2100:
            return year
    return None


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0] or 0)


def _case_keys(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> set[str]:
    return {str(row[0]) for row in conn.execute(sql, params).fetchall()}


def _count_distinct(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> int:
    return len(_case_keys(conn, sql, params))


def _count_serious(conn: sqlite3.Connection, cases: set[str]) -> int:
    if not cases:
        return 0
    return _count_in_cases(conn, cases, "SELECT COUNT(*) FROM cases WHERE serious = 1 AND case_key IN ({})")


def _count_outcomes(conn: sqlite3.Connection, cases: set[str], codes: set[str]) -> int:
    if not cases:
        return 0
    placeholders = ",".join("?" for _ in cases)
    code_placeholders = ",".join("?" for _ in codes)
    sql = (
        f"SELECT COUNT(DISTINCT case_key) FROM outcome_case "
        f"WHERE case_key IN ({placeholders}) AND outc_cod IN ({code_placeholders})"
    )
    return int(conn.execute(sql, tuple(cases) + tuple(codes)).fetchone()[0] or 0)


def _count_in_cases(conn: sqlite3.Connection, cases: set[str], sql_template: str) -> int:
    placeholders = ",".join("?" for _ in cases)
    return int(conn.execute(sql_template.format(placeholders), tuple(cases)).fetchone()[0] or 0)


def _yearly_trend(conn: sqlite3.Connection, cases: set[str]) -> list[TrendPoint]:
    if not cases:
        return []
    placeholders = ",".join("?" for _ in cases)
    rows = conn.execute(
        f"SELECT year, COUNT(*) FROM cases WHERE case_key IN ({placeholders}) AND year IS NOT NULL GROUP BY year ORDER BY year",
        tuple(cases),
    ).fetchall()
    return [TrendPoint(year=int(year), reports=int(count)) for year, count in rows]


def _sex_distribution(conn: sqlite3.Connection, cases: set[str]) -> list[DistributionPoint]:
    if not cases:
        return []
    placeholders = ",".join("?" for _ in cases)
    rows = conn.execute(
        f"SELECT COALESCE(NULLIF(sex, ''), 'UNK'), COUNT(*) FROM cases WHERE case_key IN ({placeholders}) GROUP BY sex",
        tuple(cases),
    ).fetchall()
    return [DistributionPoint(label=str(label), count=int(count)) for label, count in rows]


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 2)


def _signal_level(a: int, ror: float | None) -> str:
    if not a:
        return "none"
    if ror is not None and ror >= 4 and a >= 20:
        return "strong"
    if ror is not None and ror >= 2 and a >= 10:
        return "moderate"
    return "weak"


def _read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local FAERS SQLite cache from quarterly ASCII/CSV files.")
    parser.add_argument("--source", required=True, type=Path, help="FAERS quarterly directory or zip file")
    parser.add_argument("--output", default=DEFAULT_CACHE_PATH, type=Path, help="Output SQLite cache path")
    parser.add_argument("--source-label", default="", help="Reader-facing source label, e.g. FAERS 2025Q4")
    args = parser.parse_args()
    status = build_faers_cache(args.source, args.output, args.source_label)
    print(status.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
