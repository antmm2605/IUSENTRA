"""Audit severo JSON -> SQLite per i dati tenant-aware di IUSENTRA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.database import GestioneDatabase


DEFAULT_TENANT_MODULES = {
    "calendar_sync": "agenda/calendar_sync.json",
    "clienti": "clienti/anagrafica.json",
    "condivisioni": "clienti/condivisioni.json",
    "note_faldone": "clienti/note_faldone.json",
    "fascicoli": "fascicoli/fascicoli.json",
    "appuntamenti": "agenda/appuntamenti.json",
    "scadenze": "scadenziario/scadenze.json",
    "timesheet": "timesheet/entries.json",
    "time_tracking": "timesheet/time_tracking.json",
    "preventivi": "preventivi/preventivi.json",
    "conferimenti": "preventivi/conferimenti.json",
    "fatturazione": "fatturazione/parcelle.json",
    "pagamenti_links": "pagamenti/transazioni.json",
    "pagamenti_config": "pagamenti/config.json",
    "messaggi": "messaggi/storico.json",
    "email_casella": "email/casella.json",
    "email_ordinaria": "email/ordinaria.json",
    "utenti": "auth/utenti.json",
    "audit": "auth/audit.json",
    "privacy": "privacy/registro.json",
    "notifiche": "notifiche/log.json",
    "backup": "backup/registro.json",
    "portale": "portale/portali.json",
    "soggetti": "soggetti/anagrafica.json",
    "soggetti_parti": "soggetti/parti.json",
    "wizard_pro": "wizard_pro/sessioni.json",
    "legal_intelligence": "intelligence/motori.json",
    "normative_tables": "intelligence/tabelle_normative.json",
    "giurisprudenza": "intelligence/giurisprudenza.json",
    "workspace_intelligence": "intelligence/workspace_intelligence.json",
    "local_ai": "intelligence/local_ai.json",
    "validation_runs": "intelligence/validation_runs.json",
    "template_atti": "template_atti/templates.json",
    "template_atti_prefs": "template_atti/editor_layout.json",
    "redaction_assistant": "intelligence/assistente_redazionale.json",
    "telematico": "telematico/telematico.json",
    "search_index": "search/index.db",
}


def _module_mapping(data_root: str, explicit_modules: list[str]) -> dict[str, str]:
    modules: dict[str, str] = {}
    if data_root:
        root = Path(data_root)
        modules.update({name: str(root / relative) for name, relative in DEFAULT_TENANT_MODULES.items()})
    for item in explicit_modules:
        if "=" not in item:
            raise SystemExit(f"Modulo non valido: {item}. Usa nome=percorso.")
        name, path = item.split("=", 1)
        name = name.strip()
        path = path.strip()
        if not name or not path:
            raise SystemExit(f"Modulo non valido: {item}. Usa nome=percorso.")
        modules[name] = path
    return modules


def _summarize(report: dict[str, Any]) -> str:
    modules = dict(report.get("modules") or {})
    rows = []
    for name, payload in sorted(modules.items()):
        status = str(payload.get("status") or "ok")
        json_count = int(payload.get("json_count") or 0)
        sqlite_count = int(payload.get("sqlite_count") or 0)
        if status != "ok" or json_count or sqlite_count:
            rows.append(f"- {name}: JSON {json_count}, SQLite {sqlite_count}, stato {status}")
    if not rows:
        return "Nessun modulo con record da confrontare."
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica che una migrazione JSON -> SQLite conservi record, identificativi e payload completi.",
    )
    parser.add_argument("--db", required=True, help="Percorso dello studio.db o dello snapshot SQLite da verificare.")
    parser.add_argument("--data-root", default="", help="Root del tenant, ad esempio /data/tenants/studio.")
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Modulo esplicito nel formato nome=percorso. Ripetibile.",
    )
    parser.add_argument("--report-json", default="", help="Percorso opzionale del report JSON.")
    args = parser.parse_args()

    modules = _module_mapping(args.data_root, args.module)
    if not modules:
        raise SystemExit("Indica --data-root oppure almeno un --module nome=percorso.")

    report = GestioneDatabase(modules).verifica_migrazione_sqlite(args.db)
    if args.report_json:
        output = Path(args.report_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Audit migrazione SQLite")
    print(f"Database: {report.get('db_path')}")
    print(f"Esito: {'OK' if report.get('ok') else 'NON ALLINEATO'}")
    print(_summarize(report))
    for message in report.get("errors") or []:
        print(f"ERRORE: {message}")
    for message in report.get("warnings") or []:
        print(f"AVVISO: {message}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
