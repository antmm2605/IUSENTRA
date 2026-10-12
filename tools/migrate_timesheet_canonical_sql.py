"""Adozione esplicita del Timesheet SQLite storico nel database dello studio.

Non viene invocata da route, avvio o scheduler. Non legge mirror JSON.
Il chiamante operativo deve drenare i produttori prima dell'applicazione.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from deploy.hetzner.backup_structured import _backup_sqlite


def _read(connection):
    columns = [row[1] for row in connection.execute("PRAGMA table_info(timesheet_entries)")]
    if not columns or not {"id", "dati_json"}.issubset(columns):
        raise ValueError("Schema Timesheet assente: nessuna adozione.")
    rows = {}
    for row in connection.execute("SELECT * FROM timesheet_entries"):
        item = dict(zip(columns, row))
        payload = json.loads(item["dati_json"])
        if not isinstance(payload, dict) or payload.get("id") != item["id"]:
            raise ValueError("Identificativo Timesheet SQL discordante dal contenuto.")
        if any((payload.get(field) or None) != (item.get(field) or None)
               for field in ("id_fascicolo", "id_cliente")):
            raise ValueError("Collegamento Timesheet SQL discordante dal contenuto.")
        rows[item["id"]] = item
    return columns, rows


def migrate(root, backup_dir=None):
    """Senza backup_dir restituisce soltanto il piano, senza creare database."""
    root = Path(root).resolve(strict=True)
    source = (root / "timesheet" / "studio.db").resolve(strict=True)
    target = (root / "studio.db").resolve(strict=True)
    if source.parent != root / "timesheet" or target.parent != root or source == target:
        raise ValueError("Database fuori dal perimetro dello studio.")
    apply = backup_dir is not None
    source_uri = source.as_uri() + "?mode=ro"
    target_uri = target.as_uri() + ("?mode=rw" if apply else "?mode=ro")
    with closing(sqlite3.connect(source_uri, uri=True, timeout=30, isolation_level=None)) as old:
        with closing(sqlite3.connect(target_uri, uri=True, timeout=30, isolation_level=None)) as core:
            core.execute("PRAGMA foreign_keys=ON")
            old.execute("BEGIN")
            core.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
            try:
                columns, original = _read(old)
                target_columns, current = _read(core)
                if columns != target_columns:
                    raise ValueError("Schemi Timesheet discordanti: nessuna adozione.")
                pending = []
                for key, item in original.items():
                    if key in current:
                        if item != current[key]:
                            raise ValueError("Collisione Timesheet: dato canonico preservato.")
                    else:
                        for field, table in (("id_fascicolo", "fascicoli"), ("id_cliente", "clienti")):
                            if item.get(field) and core.execute(
                                f"SELECT 1 FROM {table} WHERE id=?", (item[field],)
                            ).fetchone() is None:
                                raise ValueError("Riferimento Timesheet assente dall'archivio canonico.")
                        pending.append(item)
                result = {"applied": apply, "inserted": len(pending),
                          "already_present": len(original) - len(pending)}
                if apply:
                    destination = Path(backup_dir).resolve()
                    if destination in {root, source.parent} or not destination.is_relative_to(root):
                        raise ValueError("Backup fuori dal perimetro dello studio.")
                    destination.mkdir(parents=True, exist_ok=False)
                    backups = [_backup_sqlite(target, destination / "studio-prima.sqlite"),
                               _backup_sqlite(source, destination / "timesheet-origine.sqlite")]
                    (destination / "manifest.json").write_text(
                        json.dumps({"source": str(source), "target": str(target),
                                    "backups": backups, "plan": result}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
                    names = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
                    statement = f"INSERT INTO timesheet_entries ({names}) VALUES ({','.join('?' for _ in columns)})"
                    for item in pending:
                        core.execute(statement, tuple(item[name] for name in columns))
                    if pending:
                        core.execute(
                            "INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(),
                             "migrazione_sql", "Procedura esplicita", "timesheet.adozione_sql",
                             "timesheet", root.name,
                             json.dumps({**result, "backup_dir": str(destination), "backups": backups}, ensure_ascii=False),
                             "", "SUCCESSO"),
                        )
                    core.execute("COMMIT")
                return result
            finally:
                if core.in_transaction:
                    core.execute("ROLLBACK")
                old.execute("ROLLBACK")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio-root", required=True)
    parser.add_argument("--backup-dir")
    parser.add_argument("--writers-drained", action="store_true")
    args = parser.parse_args()
    if args.backup_dir and not args.writers_drained:
        parser.error("Applicazione sospesa: occorre drenare i produttori Timesheet.")
    print(json.dumps(migrate(args.studio_root, args.backup_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
