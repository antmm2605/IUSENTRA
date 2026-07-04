from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pct.agenda import Agenda
from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli
from pct.soggetti import GestioneSoggetti
from pct.storage import StudioDB
from web.services.quickorganizer_import import (
    audit_quickorganizer_import,
    import_quickorganizer_package,
    load_staged_package,
)


def _tenant_repositories(tenant_root: Path) -> tuple[GestioneFascicoli, GestioneClienti, GestioneSoggetti, Agenda]:
    studio_db_path = tenant_root / "studio.db"
    studio_db = StudioDB.get(str(studio_db_path)) if studio_db_path.exists() else None
    fascicoli = GestioneFascicoli(
        db_path=str(tenant_root / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tenant_root / "fascicoli" / "documenti"),
        archive_dir=str(tenant_root / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )
    clienti = GestioneClienti(
        db_path=str(tenant_root / "clienti" / "anagrafica.json"),
        studio_db=studio_db,
    )
    soggetti = GestioneSoggetti(
        str(tenant_root / "soggetti" / "anagrafica.json"),
        str(tenant_root / "soggetti" / "parti.json"),
        studio_db=studio_db,
    )
    agenda = Agenda(
        db_path=str(tenant_root / "agenda" / "appuntamenti.json"),
        studio_db=studio_db,
    )
    return fascicoli, clienti, soggetti, agenda


def _storage_counts(tenant_root: Path) -> dict[str, Any]:
    studio_db_path = tenant_root / "studio.db"
    output: dict[str, Any] = {
        "studioDbExists": studio_db_path.exists(),
        "studioDbPath": str(studio_db_path),
        "tables": {},
    }
    if not studio_db_path.exists():
        return output
    studio_db = StudioDB.get(str(studio_db_path))
    for table in ("clienti", "fascicoli", "soggetti", "soggetti_parti", "appuntamenti"):
        try:
            row = studio_db.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            output["tables"][table] = int(row["n"] if isinstance(row, dict) else row[0])
        except Exception:
            output["tables"][table] = None
    return output


def _counts(tenant_root: Path) -> dict[str, int]:
    fascicoli, clienti, soggetti, agenda = _tenant_repositories(tenant_root)
    return {
        "fascicoli": len(fascicoli.tutti(stato=None, archiviati=True)),
        "clienti": len(clienti.tutti()),
        "soggetti": len(soggetti.tutti()),
        "parti_fascicolo": sum(len(soggetti.parti_fascicolo(f.id)) for f in fascicoli.tutti(stato=None, archiviati=True)),
        "documenti": sum(len(getattr(f, "documenti", []) or []) for f in fascicoli.tutti(stato=None, archiviati=True)),
        "attivita": sum(len(getattr(f, "attivita", []) or []) for f in fascicoli.tutti(stato=None, archiviati=True)),
        "appuntamenti": len(agenda.tutti()),
        "udienze_agenda": sum(1 for item in agenda.tutti() if str(getattr(getattr(item, "tipo", ""), "value", getattr(item, "tipo", ""))) == "UDIENZA"),
        "contesti_economici": sum(1 for f in fascicoli.tutti(stato=None, archiviati=True) if (getattr(f, "pagamenti", {}) or {}).get("contesto_economico")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importa e verifica un pacchetto Studio Telematico gia' in staging tenant-aware.",
    )
    parser.add_argument("--tenant-root", required=True, help="Root dati del tenant IUSENTRA.")
    parser.add_argument("--stage-root", required=True, help="Cartella importazioni/quickorganizer del tenant.")
    parser.add_argument("--import-id", required=True, help="Identificativo stage.json da importare o auditare.")
    parser.add_argument("--execute", action="store_true", help="Esegue l'import prima dell'audit.")
    parser.add_argument("--allow-partial", action="store_true", help="Ripara dati gia' importati anche se il pacchetto non contiene tutti i file fisici.")
    parser.add_argument("--actor", default="SUPERADMIN", help="Operatore registrato sui documenti importati.")
    args = parser.parse_args(argv)

    tenant_root = Path(args.tenant_root).resolve()
    stage_root = Path(args.stage_root).resolve()
    package, stage = load_staged_package(stage_root, args.import_id)
    output: dict[str, Any] = {
        "ok": False,
        "tenantRoot": str(tenant_root),
        "importId": args.import_id,
        "sourceName": stage.get("sourceName", ""),
        "stageSummary": (stage.get("analysis") or {}).get("summary", {}),
        "storage": _storage_counts(tenant_root),
        "before": _counts(tenant_root),
    }

    if args.execute:
        fascicoli, clienti, soggetti, agenda = _tenant_repositories(tenant_root)
        output["import"] = import_quickorganizer_package(
            package,
            fascicoli=fascicoli,
            clienti=clienti,
            soggetti=soggetti,
            agenda_repo=agenda,
            actor=args.actor,
            allow_partial=args.allow_partial,
        )

    fascicoli, clienti, soggetti, agenda = _tenant_repositories(tenant_root)
    audit = audit_quickorganizer_import(
        package,
        fascicoli=fascicoli,
        clienti=clienti,
        soggetti=soggetti,
        agenda_repo=agenda,
    )
    output["after"] = _counts(tenant_root)
    output["storage"] = _storage_counts(tenant_root)
    output["audit"] = audit
    output["ok"] = bool(audit.get("ok"))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
