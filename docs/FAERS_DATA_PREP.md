# FAERS Official Quarterly Data Preparation

This guide explains how to prepare official FAERS quarterly files for the MedGuard-Agent offline cache. The system does not ship official FAERS data and does not invent quarterly metrics when the cache is missing.

## Expected Source

Download FAERS quarterly ASCII or CSV files from the FDA FAERS public dashboard/download page. Keep the original package outside git, for example:

```text
data/incoming/faers/2025q4/
```

Expected tables include:

```text
DEMO
DRUG
REAC
OUTC
```

ZIP files and extracted directories are both supported by the cache builder.

## Build Cache

```powershell
.\.venv\Scripts\python.exe scripts\build_faers_cache.py --source data\incoming\faers\2025q4 --source-label "FAERS 2025Q4"
```

Generated artifacts:

```text
data/faers/faers.sqlite
data/faers/manifest.json
```

## Calculation Boundary

The first offline cache version:

- deduplicates by `caseid` when available, with `primaryid` fallback;
- builds the drug / ADR two-by-two table;
- calculates ROR and PRR;
- reports serious, death, hospitalization, yearly trend, and sex distribution when source tables contain those fields.

It does not perform exposure adjustment, confounder correction, indication-bias control, or causal inference.

## Runtime Diagnostics

Use:

```text
GET  /api/faers/status
POST /api/faers/signal
```

When `available=false`, ADR analysis can still use realtime openFDA or labeled fallback/demo sources depending on configuration. The UI must show the active source type.
