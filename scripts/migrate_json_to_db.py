from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from core.storage.migration_service import migrate_json_directory_to_sqlite


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrazione idempotente JSON -> DB IUSENTRA.")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--database-url", default="sqlite:///data/iusentra.sqlite")
    parser.add_argument("--backup-dir", default="data/backup")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    data_root = Path(args.data_root)
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_target = backup_dir / f"json-pre-migration-{stamp}"
    if data_root.exists():
        shutil.copytree(data_root, backup_target, ignore=shutil.ignore_patterns("backup", "*.sqlite", "*.db"))
    report = migrate_json_directory_to_sqlite(data_root, args.database_url, limit=args.limit)
    report["backup"] = str(backup_target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
