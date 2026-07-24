"""CLI wrapper for building the offline FAERS cache.

Example:
    python scripts/build_faers_cache.py --source data/incoming/faers/2025q4 --source-label "FAERS 2025Q4"
"""

from pharmagent.adr.faers_cache import main


if __name__ == "__main__":
    main()
