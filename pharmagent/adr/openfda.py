"""FAERS/openFDA signal detection with local-demo-first behavior."""

from __future__ import annotations

import httpx

from pharmagent.adr.demo_data import get_local_signal
from pharmagent.adr.faers_cache import query_faers_signal
from pharmagent.adr.schemas import OpenFDASignal
from pharmagent.config import settings
from pharmagent.runtime_config import load_runtime_config

OPENFDA_EVENT_URL = "https://api.fda.gov/drug/event.json"


def detect_signal(drug: str, adr: str, realtime: bool = False) -> OpenFDASignal:
    """Return a FAERS-like signal; use local demo data unless realtime is requested."""
    local = get_local_signal(drug, adr)
    runtime = load_runtime_config()
    try:
        return query_faers_signal(drug, adr)
    except FileNotFoundError:
        pass
    except Exception:
        if runtime.openfda.strict_real_data:
            raise

    if not realtime and not runtime.openfda.strict_real_data:
        return local

    try:
        realtime_signal = query_openfda_realtime(drug, adr)
        realtime_signal.source_mode = "realtime_openfda"
        realtime_signal.clinical_interpretation = (
            f"实时 openFDA 查询发现 {drug} 与 {adr} 相关报告 {realtime_signal.report_count} 例。"
            "该结果提示报告关联，仍需结合病例时间关系和替代原因判断。"
        )
        return realtime_signal
    except Exception:
        if runtime.openfda.strict_real_data:
            raise
        local.source_mode = "fallback_demo"
        local.limitations = [
            "实时 openFDA 查询失败，当前回退到本地演示数据。",
            *local.limitations,
        ]
        return local


def query_openfda_realtime(drug: str, adr: str) -> OpenFDASignal:
    """Query openFDA for a lightweight realtime count.

    The realtime endpoint intentionally computes a compact signal for UI display.
    Full disproportionality analysis should be done offline with deduplicated FAERS.
    """
    drug_query = drug.replace('"', "")
    adr_query = adr.replace('"', "")
    combined_search = (
        f'patient.drug.medicinalproduct:"{drug_query}"'
        f'+AND+patient.reaction.reactionmeddrapt:"{adr_query}"'
    )
    drug_search = f'patient.drug.medicinalproduct:"{drug_query}"'
    adr_search = f'patient.reaction.reactionmeddrapt:"{adr_query}"'

    runtime = load_runtime_config()
    api_key = runtime.openfda.api_key or settings.openfda_api_key

    with httpx.Client(timeout=8.0) as client:
        combined = _count(client, combined_search, api_key)
        drug_total = _count(client, drug_search, api_key)
        adr_total = _count(client, adr_search, api_key)

    a = max(combined, 0)
    b = max(drug_total - a, 1)
    c = max(adr_total - a, 1)
    # openFDA does not expose the total database count cheaply here; use a stable
    # denominator only for a display-level disproportionality estimate.
    d = 2_000_000

    ror = round((a / b) / (c / d), 2) if a else 0.0
    prr = round((a / (a + b)) / (c / (c + d)), 2) if a else 0.0
    signal_level = "strong" if ror >= 4 and a >= 20 else "moderate" if ror >= 2 and a >= 10 else "weak"

    return OpenFDASignal(
        drug=drug,
        adr=adr,
        source_mode="realtime_openfda",
        source="openFDA drug/event.json",
        source_type="realtime_openfda_api",
        deduplicated=False,
        report_count=a,
        serious_count=0,
        death_count=0,
        hospitalization_count=0,
        ror=ror,
        prr=prr,
        contingency_table={"a": a, "b": b, "c": c, "d": d},
        serious_ratio=0.0,
        signal_level=signal_level,
        yearly_trend=[],
        sex_distribution=[],
        age_distribution=[],
        limitations=[
            "实时查询为轻量估算，未进行完整 FAERS 去重和混杂校正。",
            "FAERS 自发报告只能提示报告关联，不能证明因果关系。",
        ],
    )


def _count(client: httpx.Client, search: str, api_key: str = "") -> int:
    params: dict[str, str | int] = {"search": search, "limit": 1}
    if api_key:
        params["api_key"] = api_key
    res = client.get(OPENFDA_EVENT_URL, params=params)
    if res.status_code == 404:
        return 0
    res.raise_for_status()
    return int(res.json().get("meta", {}).get("results", {}).get("total", 0))

