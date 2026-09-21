#!/usr/bin/env python3
"""Dry-run/apply governato per i job OCR legacy privi di tenant."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.ocr_reconciliation import apply, inspect, report


def _default_data_root() -> Path:
    configured = str(os.getenv("IUSENTRA_DATA_ROOT", "") or "").strip()
    if configured:
        return Path(configured)
    for candidate in (Path("/opt/iusentra/data"), Path("/data")):
        if candidate.exists():
            return candidate
    return Path("data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=_default_data_root())
    parser.add_argument("--queue-db", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    queue_db = args.queue_db or args.data_root / "search" / "ocr_jobs.db"
    if args.apply:
        if args.backup_dir is None:
            parser.error("--apply richiede --backup-dir")
        result = apply(queue_db, args.data_root, args.backup_dir)
    else:
        candidates, skipped = inspect(queue_db, args.data_root)
        result = report(candidates, skipped)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result["skipped"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
