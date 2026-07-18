from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.soggetti import GestioneSoggetti
from pct.storage import StudioDB
from web.services.quickorganizer_import import (
    audit_quickorganizer_notification_recipients,
    load_quickorganizer_package,
    reconcile_quickorganizer_notification_recipients,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica che la rubrica destinatari IUSENTRA copra tutte le PEC dell'archivio autorizzato.",
    )
    parser.add_argument("--source", required=True, help="Archivio MDB, ZIP o JSON autorizzato.")
    parser.add_argument("--tenant-root", required=True, help="Root dati del tenant IUSENTRA.")
    parser.add_argument("--repair", action="store_true", help="Inserisce o riallinea i destinatari mancanti prima dell'audit.")
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser().resolve()
    tenant_root = Path(args.tenant_root).expanduser().resolve()
    studio_db_path = tenant_root / "studio.db"
    if not studio_db_path.is_file():
        print(json.dumps({"ok": False, "sourceOfTruth": "sqlite", "error": "studio.db non disponibile"}))
        return 2

    existing_roots = str(os.environ.get("IUSENTRA_STUDIO_TELEMATICO_LOCAL_ROOTS", "") or "")
    roots = [item for item in existing_roots.split(os.pathsep) if item]
    if str(source.parent) not in roots:
        roots.append(str(source.parent))
    os.environ["IUSENTRA_STUDIO_TELEMATICO_LOCAL_ROOTS"] = os.pathsep.join(roots)

    package = load_quickorganizer_package(source, local_source=True)
    studio_db = StudioDB.get(str(studio_db_path))
    soggetti = GestioneSoggetti(
        str(tenant_root / "soggetti" / "anagrafica.json"),
        str(tenant_root / "soggetti" / "parti.json"),
        studio_db=studio_db,
    )
    rows = package.table("NOMI")
    if args.repair:
        result = reconcile_quickorganizer_notification_recipients(rows, soggetti=soggetti)
    else:
        result = audit_quickorganizer_notification_recipients(rows, soggetti=soggetti)
    output = {
        "sourceOfTruth": "sqlite",
        "sourceKind": package.source_kind,
        "repairRequested": bool(args.repair),
        **result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
