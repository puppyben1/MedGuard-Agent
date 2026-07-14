#!/usr/bin/env python3
"""Ingest demo data for the 5 target drugs into ChromaDB + BM25 indexes."""

import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pharmagent.ingestion.build_index import build_all_indexes
from pharmagent.logging_config import setup_logging

DEMO_DRUGS = ["metformin", "warfarin", "lisinopril", "semaglutide", "aspirin"]


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
