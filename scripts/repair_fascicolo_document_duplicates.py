from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.fascicoli import GestioneFascicoli
from pct.path_security import resolve_runtime_path
from pct.storage import StudioDB


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Riconcilia i record documento duplicati nei fascicoli di un tenant IUSENTRA."
    )
    parser.add_argument(
        "--tenant-root",
        required=True,
        help="Root del tenant, per esempio /data/tenants/studio-legale-giuseppe-montagnese.",
    )
    parser.add_argument("--fascicolo", default="", help="ID fascicolo da riparare. Se omesso ripara tutto il tenant.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe assorbito senza salvare.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    tenant_root = resolve_runtime_path(
        args.tenant_root,
        extra_roots=(Path("/data/tenants"), Path.cwd() / "data" / "tenants"),
    ).resolve()
    studio_db_path = tenant_root / "studio.db"
    fascicoli_dir = tenant_root / "fascicoli"
    gf = GestioneFascicoli(
        db_path=str(fascicoli_dir / "fascicoli.json"),
        documents_dir=str(fascicoli_dir / "documenti"),
        archive_dir=str(fascicoli_dir / "archivio"),
        studio_db=StudioDB.get(str(studio_db_path)),
    )
    report = gf.riconcilia_documenti_duplicati(args.fascicolo or None, dry_run=bool(args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
