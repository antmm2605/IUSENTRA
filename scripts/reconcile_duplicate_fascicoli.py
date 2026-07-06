from __future__ import annotations

import argparse
import json
from pathlib import Path

from pct.fascicoli import GestioneFascicoli


def _studio_db(path: str | None):
    if not path:
        return None
    from pct.storage import StudioDB

    db = StudioDB.get(str(Path(path)))
    db.ensure_schema()
    return db


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Riconcilia fascicoli doppi con stesso cliente e numero RG."
    )
    parser.add_argument("--db-path", required=True, help="Percorso fascicoli.json tenant-aware.")
    parser.add_argument("--documents-dir", required=True, help="Directory documenti fascicoli.")
    parser.add_argument("--studio-db", default="", help="Percorso studio.db, fonte SQL se presente.")
    parser.add_argument("--apply", action="store_true", help="Applica la riconciliazione. Senza flag esegue solo dry-run.")
    args = parser.parse_args()

    repo = GestioneFascicoli(
        db_path=args.db_path,
        documents_dir=args.documents_dir,
        studio_db=_studio_db(args.studio_db),
    )
    report = repo.riconcilia_doppioni_cliente_rg(dry_run=not args.apply)
    report["source_of_truth"] = "sqlite" if args.studio_db else "json"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
