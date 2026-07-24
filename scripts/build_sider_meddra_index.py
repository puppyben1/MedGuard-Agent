"""CLI wrapper for building SIDER/MedDRA RAG and Neo4j artifacts."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pharmagent.adr.sider_index import main


if __name__ == "__main__":
    raise SystemExit(main())
