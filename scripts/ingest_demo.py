#!/usr/bin/env python3
"""Ingest demo data into ChromaDB + BM25 indexes.

Covers the common outpatient drugs used by the prescription review golden
cases and example UI cases, plus a broader set of cardiovascular/diabetes/
NSAID/antibiotic agents so the agent has evidence for a wider range of
reviews.
"""

import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pharmagent.ingestion.build_index import build_all_indexes
from pharmagent.logging_config import setup_logging

# Original 5 target drugs + extensions for golden cases and common combos.
# - amoxicillin / penicillin: case_05 青霉素过敏交叉反应
# - glipizide, glyburide: 磺脲类，与 case_08 中文 case 相关
# - clopidogrel: 抗血小板，与 warfarin/aspirin 联用风险
# - apixaban, rivaroxaban: DOAC，常见替代 warfarin
# - hydrochlorothiazide: case_06 triple whammy
# - ibuprofen, naproxen, celecoxib: NSAID 类，出血/肾损风险
# - atorvastatin, simvastatin: 他汀类，常见联合用药
# - digoxin: 窄治疗窗，常见不良反应
# - levothyroxine, amlodipine, metoprolol: 高频门诊药，丰富 QA 覆盖
DEMO_DRUGS = [
    # 原始 5 药物
    "metformin", "warfarin", "lisinopril", "semaglutide", "aspirin",
    # 青霉素类（case 5 过敏交叉）
    "amoxicillin", "penicillin",
    # 磺脲类（case 8 中文）
    "glipizide", "glyburide",
    # 抗血小板/抗凝
    "clopidogrel", "apixaban", "rivaroxaban",
    # 利尿剂 / NSAID（triple whammy）
    "hydrochlorothiazide", "ibuprofen", "naproxen", "celecoxib",
    # 他汀类
    "atorvastatin", "simvastatin",
    # 窄治疗窗 / 高频门诊
    "digoxin", "levothyroxine", "amlodipine", "metoprolol",
]


def main() -> None:
    setup_logging("INFO")
    print(f"Ingesting demo data for: {', '.join(DEMO_DRUGS)}")
    print("This may take 5-10 minutes (streaming from HuggingFace)...\n")

    counts = build_all_indexes(DEMO_DRUGS)

    print("\n=== Ingestion Complete ===")
    for collection, count in counts.items():
        print(f"  {collection}: {count} chunks")
    print(f"\n  Total: {sum(counts.values())} chunks indexed")


if __name__ == "__main__":
    main()
