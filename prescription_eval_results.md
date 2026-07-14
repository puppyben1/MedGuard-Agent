# MedGuard-Agent Prescription Review Evaluation

Date: 2026-07-14 15:18
Cases evaluated: 10 (errors: 0)

## Per-case results

| Case | Expected | Produced | P | R | F1 | Hit | Halluc | Risk | Time(s) |
|------|----------|----------|---|---|----|-----|--------|------|---------|
| case_01_pregnancy_acei | 1 | 2 | 0.50 | 1.00 | 0.67 | 1.00 | 0.00 | critical | 49.7 |
| case_02_metformin_severe_ckd | 1 | 2 | 0.50 | 1.00 | 0.67 | 1.00 | 0.00 | critical | 13.3 |
| case_03_warfarin_aspirin_ibuprofen | 2 | 4 | 0.50 | 1.00 | 0.67 | 1.00 | 0.00 | high | 20.7 |
| case_04_semaglutide_mtc | 1 | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | critical | 8.4 |
| case_05_penicillin_allergy_amoxicillin | 1 | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | critical | 11.1 |
| case_06_triple_whammy_renal | 1 | 2 | 0.50 | 1.00 | 0.67 | 1.00 | 0.00 | high | 15.3 |
| case_07_negative_control | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | low | 6.3 |
| case_08_cn_metformin_ckd4 | 1 | 2 | 0.50 | 1.00 | 0.67 | 1.00 | 0.00 | critical | 14.3 |
| case_09_cn_warfarin_aspirin_ibuprofen | 2 | 4 | 0.50 | 1.00 | 0.67 | 1.00 | 0.00 | high | 19.7 |
| case_10_cn_pregnancy_acei | 1 | 2 | 0.50 | 1.00 | 0.67 | 1.00 | 0.00 | critical | 7.7 |

## Aggregate metrics
- **Micro Precision:** 0.550
- **Micro Recall:** 1.000
- **Micro F1:** 0.710  (TP=11, FP=9, FN=0)
- **Macro Precision:** 0.650
- **Macro Recall:** 1.000
- **Macro F1:** 0.767
- **Evidence hit rate (avg per case):** 1.000
- **Hallucination rate (unverified high/critical / all high/critical):** 0.000
- **Avg hallucination rate per case:** 0.000
- **Average response time:** 16.641 s

## Metric definitions
- **Precision**: TP / (TP + FP) — of findings produced, how many were expected.
- **Recall**: TP / (TP + FN) — of expected findings, how many were produced.
- **F1**: harmonic mean of P and R.
- **Severity match**: a produced finding matches an expected one if type matches, drug sets overlap, and produced severity ≥ expected (we do not penalize the system for being more cautious).
- **Evidence hit rate**: fraction of produced findings with at least one supporting source document.
- **Hallucination rate**: fraction of high/critical produced findings that lack evidence support — these are the dangerous ones.
- **Average response time**: end-to-end graph execution time per case.