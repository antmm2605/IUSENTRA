#!/usr/bin/env python
"""Audit del contratto dati/tenant/React di IUSENTRA."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.data_flow_contract import audit_data_flow_contract
from pct.database import GestioneDatabase
from pct.tenant import GestioneTenant

_MIRROR_TABLE = "moduli_json_records"
_MIRROR_COLUMNS = {
    "modulo",
    "record_key",
    "record_index",
    "record_kind",
    "payload_json",
}
_CORE_TABLES_FOR_DIAGNOSTICS = (
    "clienti",
    "fascicoli",
    "appuntamenti",
    "scadenze",
    "messaggi",
    "documenti",
    "comunicazioni",
    "moduli_dati",
    "moduli_json_records",
)
_SEARCH_TABLE = "search_documenti"
_SEARCH_SHADOW_PREFIX = "search_documenti_"


def _count_table(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    if not table.replace("_", "").isalnum():
        return {"exists": False, "readable": False, "count": None, "error": "nome tabella non valido"}
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name=?",
            (table,),
        ).fetchone()
        if not row:
            return {"exists": False, "readable": False, "count": None, "error": ""}
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return {"exists": True, "readable": True, "count": int(count or 0), "error": ""}
    except sqlite3.DatabaseError as exc:
        return {
            "exists": True,
            "readable": False,
            "count": None,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def _delete_schema_entries(
    target: Path,
    *,
    table: str,
    like_prefix: str | None = None,
) -> dict[str, Any]:
    """Rimuove dal catalogo SQLite solo oggetti rigenerabili quando DROP fallisce."""

    with sqlite3.connect(str(target)) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA writable_schema=ON")
        if like_prefix:
            cursor = conn.execute(
                """
                DELETE FROM sqlite_schema
                WHERE name = ?
                   OR tbl_name = ?
                   OR name LIKE ?
                """,
                (table, table, f"{like_prefix}%"),
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM sqlite_schema
                WHERE name = ?
                   OR tbl_name = ?
                """,
                (table, table),
            )
        version = int(conn.execute("PRAGMA schema_version").fetchone()[0] or 0)
        conn.execute(f"PRAGMA schema_version={version + 1}")
        conn.execute("PRAGMA writable_schema=OFF")
        conn.commit()
    return {"schema_only": True, "deleted_schema_entries": int(cursor.rowcount or 0)}


def _vacuum_sqlite(target: Path) -> dict[str, Any]:
    before_size = target.stat().st_size if target.exists() else 0
    report: dict[str, Any] = {
        "ok": False,
        "executed": True,
        "bytes_before": before_size,
        "bytes_after": before_size,
        "error": "",
    }
    try:
        with sqlite3.connect(str(target), isolation_level=None) as conn:
            conn.execute("VACUUM")
        report["ok"] = True
        report["bytes_after"] = target.stat().st_size if target.exists() else 0
    except sqlite3.DatabaseError as exc:
        report["error"] = f"{exc.__class__.__name__}: {exc}"
    return report


def _create_json_mirror_schema(target: Path) -> None:
    with sqlite3.connect(str(target)) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS moduli_json_records (
                modulo        TEXT NOT NULL,
                record_key    TEXT NOT NULL,
                record_index  INTEGER NOT NULL DEFAULT 0,
                record_kind   TEXT NOT NULL DEFAULT 'dict',
                payload_json  TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (modulo, record_key),
                FOREIGN KEY (modulo) REFERENCES moduli_dati(nome) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_moduli_json_records_modulo "
            "ON moduli_json_records(modulo)"
        )
        conn.commit()


def _json_mirror_precheck(studio_db: str | Path) -> dict[str, Any]:
    """Controlla se il mirror SQL rigenerabile e' leggibile e coerente."""

    target = Path(studio_db)
    result: dict[str, Any] = {
        "table": _MIRROR_TABLE,
        "checked": True,
        "exists": False,
        "readable": False,
        "schema_ok": False,
        "reset_executed": False,
        "records_before": None,
        "reason": "",
    }
    if not target.exists():
        result["reason"] = "studio.db mancante"
        return result

    try:
        with sqlite3.connect(str(target)) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (_MIRROR_TABLE,),
            ).fetchone()
            if not row:
                result.update(
                    {
                        "exists": False,
                        "readable": True,
                        "schema_ok": True,
                        "reason": "mirror assente; creazione demandata al sync",
                    }
                )
                return result

            result["exists"] = True
            columns = {str(col[1]) for col in conn.execute(f"PRAGMA table_info({_MIRROR_TABLE})")}
            missing_columns = sorted(_MIRROR_COLUMNS - columns)
            if missing_columns:
                result["reason"] = "colonne mancanti: " + ", ".join(missing_columns)
                return result

            count = conn.execute(f"SELECT COUNT(*) FROM {_MIRROR_TABLE}").fetchone()[0]
            result.update(
                {
                    "readable": True,
                    "schema_ok": True,
                    "records_before": int(count or 0),
                    "reason": "mirror leggibile",
                }
            )
            return result
    except sqlite3.DatabaseError as exc:
        result["reason"] = f"{exc.__class__.__name__}: {exc}"
        return result


def _sqlite_diagnostics(studio_db: str | Path) -> dict[str, Any]:
    """Diagnosi non distruttiva del DB tenant: tabelle core, mirror e ricerca."""

    target = Path(studio_db)
    report: dict[str, Any] = {
        "checked": True,
        "path": str(target),
        "exists": target.exists(),
        "opened": False,
        "quick_check": {"ok": False, "result": "", "error": ""},
        "core_tables": {},
        "json_mirror": None,
        "search_index": {
            "name": "search_documenti",
            "exists": False,
            "readable": False,
            "count": None,
            "error": "",
            "note": "",
        },
    }
    if not target.exists():
        return report

    try:
        with sqlite3.connect(str(target)) as conn:
            report["opened"] = True
            try:
                quick_row = conn.execute("PRAGMA quick_check").fetchone()
                quick_result = str(quick_row[0] if quick_row else "")
                report["quick_check"] = {
                    "ok": quick_result.lower() == "ok",
                    "result": quick_result,
                    "error": "",
                }
            except sqlite3.DatabaseError as exc:
                report["quick_check"] = {
                    "ok": False,
                    "result": "",
                    "error": f"{exc.__class__.__name__}: {exc}",
                }

            report["core_tables"] = {
                table: _count_table(conn, table) for table in _CORE_TABLES_FOR_DIAGNOSTICS
            }
            report["json_mirror"] = _json_mirror_precheck(target)

            search_row = conn.execute(
                "SELECT type, sql FROM sqlite_master WHERE name=?",
                (_SEARCH_TABLE,),
            ).fetchone()
            if search_row:
                search_sql = str(search_row[1] or "")
                schema_ok = (
                    "CREATE VIRTUAL TABLE" in search_sql.upper()
                    and "FTS5" in search_sql.upper()
                )
                search = _count_table(conn, _SEARCH_TABLE)
                search["exists"] = True
                search["schema_ok"] = schema_ok
                search["type"] = str(search_row[0] or "")
                search["readable"] = bool(search.get("readable")) and schema_ok
                if not schema_ok:
                    search["error"] = "schema non FTS5"
                search["note"] = (
                    "Indice di ricerca FTS: se non leggibile, i dati core possono restare "
                    "integri ma la ricerca documenti va ricostruita con procedura dedicata."
                )
                report["search_index"] = search
    except sqlite3.DatabaseError as exc:
        report["open_error"] = f"{exc.__class__.__name__}: {exc}"

    return report


def _reset_json_mirror(studio_db: str | Path) -> dict[str, Any]:
    """Elimina e ricrea solo il mirror SQL dei JSON tenant-aware."""

    target = Path(studio_db)
    reset_mode: dict[str, Any] = {"schema_only": False, "drop_error": ""}
    try:
        with sqlite3.connect(str(target)) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(f"DROP TABLE IF EXISTS {_MIRROR_TABLE}")
            conn.commit()
    except sqlite3.DatabaseError as exc:
        reset_mode = _delete_schema_entries(target, table=_MIRROR_TABLE)
        reset_mode["drop_error"] = f"{exc.__class__.__name__}: {exc}"

    _create_json_mirror_schema(target)

    after = _json_mirror_precheck(target)
    return {
        "ok": bool(after.get("readable") and after.get("schema_ok")),
        "table": _MIRROR_TABLE,
        "reset_executed": True,
        "mode": reset_mode,
        "protected_data": [
            "clienti",
            "fascicoli",
            "agenda",
            "scadenze",
            "documenti",
            "comunicazioni",
        ],
        "after": after,
    }


def _prepare_json_mirror_for_repair(studio_db: str | Path) -> dict[str, Any]:
    """Resetta il mirror solo quando il repair esplicito trova una tabella non usabile."""

    before = _json_mirror_precheck(studio_db)
    needs_reset = bool(before.get("exists")) and not (
        before.get("readable") and before.get("schema_ok")
    )
    report: dict[str, Any] = {
        "ok": True,
        "table": _MIRROR_TABLE,
        "checked": True,
        "reset_executed": False,
        "before": before,
        "reset": None,
    }
    if not needs_reset:
        return report

    try:
        reset = _reset_json_mirror(studio_db)
        report["reset"] = reset
        report["reset_executed"] = True
        report["ok"] = bool(reset.get("ok"))
        return report
    except sqlite3.DatabaseError as exc:
        report["ok"] = False
        report["reset"] = {
            "ok": False,
            "reset_executed": False,
            "error": f"{exc.__class__.__name__}: {exc}",
        }
        return report


def _create_search_index_schema(target: Path) -> None:
    with sqlite3.connect(str(target)) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS search_documenti USING fts5(
                tipo UNINDEXED,
                entity_id UNINDEXED,
                titolo,
                corpo,
                meta UNINDEXED,
                tokenize = 'unicode61 remove_diacritics 1'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_meta_indice (
                chiave TEXT PRIMARY KEY,
                valore TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_ocr_cache (
                hash_sha256  TEXT PRIMARY KEY,
                testo        TEXT,
                elaborato_il TEXT
            )
            """
        )
        conn.commit()


def _copy_search_index_source(
    *,
    target_db: Path,
    source_db: str | Path,
) -> dict[str, Any]:
    source = Path(source_db)
    report: dict[str, Any] = {
        "path": str(source),
        "exists": source.exists(),
        "documenti": 0,
        "meta_indice": 0,
        "ocr_cache": 0,
        "errors": [],
    }
    if not source.exists():
        return report

    try:
        with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target_db)) as dst:
            src.row_factory = sqlite3.Row
            dst.execute(f"DELETE FROM {_SEARCH_TABLE}")
            if _count_table(src, "documenti").get("exists"):
                for row in src.execute(
                    "SELECT tipo, entity_id, titolo, corpo, meta FROM documenti"
                ).fetchall():
                    dst.execute(
                        """
                        INSERT INTO search_documenti(tipo, entity_id, titolo, corpo, meta)
                        VALUES (?,?,?,?,?)
                        """,
                        (
                            row["tipo"],
                            row["entity_id"],
                            row["titolo"],
                            row["corpo"],
                            row["meta"],
                        ),
                    )
                    report["documenti"] += 1
            if _count_table(src, "meta_indice").get("exists"):
                dst.execute("DELETE FROM search_meta_indice")
                for row in src.execute("SELECT chiave, valore FROM meta_indice").fetchall():
                    dst.execute(
                        "INSERT OR REPLACE INTO search_meta_indice(chiave, valore) VALUES (?,?)",
                        (row["chiave"], row["valore"]),
                    )
                    report["meta_indice"] += 1
            if _count_table(src, "ocr_cache").get("exists"):
                dst.execute("DELETE FROM search_ocr_cache")
                for row in src.execute(
                    "SELECT hash_sha256, testo, elaborato_il FROM ocr_cache"
                ).fetchall():
                    dst.execute(
                        """
                        INSERT OR REPLACE INTO search_ocr_cache(hash_sha256, testo, elaborato_il)
                        VALUES (?,?,?)
                        """,
                        (row["hash_sha256"], row["testo"], row["elaborato_il"]),
                    )
                    report["ocr_cache"] += 1
            dst.commit()
    except sqlite3.DatabaseError as exc:
        report["errors"].append(f"{exc.__class__.__name__}: {exc}")
    return report


def _repair_search_index(studio_db: str | Path, source_search_db: str | Path) -> dict[str, Any]:
    """Ricostruisce solo l'indice FTS5 rigenerabile `search_documenti`."""

    target = Path(studio_db)
    before = _sqlite_diagnostics(target).get("search_index") or {}
    needs_reset = bool(before.get("exists")) and not bool(before.get("readable"))
    if not before.get("exists"):
        needs_reset = True
    report: dict[str, Any] = {
        "ok": True,
        "table": _SEARCH_TABLE,
        "checked": True,
        "reset_executed": False,
        "before": before,
        "reset": None,
        "source": None,
        "vacuum": None,
    }
    if not needs_reset:
        return report

    reset_mode: dict[str, Any] = {"schema_only": False, "drop_error": ""}
    try:
        with sqlite3.connect(str(target)) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(f"DROP TABLE IF EXISTS {_SEARCH_TABLE}")
            conn.commit()
    except sqlite3.DatabaseError as exc:
        reset_mode = _delete_schema_entries(
            target,
            table=_SEARCH_TABLE,
            like_prefix=_SEARCH_SHADOW_PREFIX,
        )
        reset_mode["drop_error"] = f"{exc.__class__.__name__}: {exc}"

    try:
        _create_search_index_schema(target)
    except sqlite3.DatabaseError as exc:
        if "malformed" not in str(exc).lower():
            report.update(
                {
                    "ok": False,
                    "reset_executed": False,
                    "reset": {
                        "mode": reset_mode,
                        "error": f"{exc.__class__.__name__}: {exc}",
                    },
                }
            )
            return report
        vacuum_report = _vacuum_sqlite(target)
        report["vacuum"] = vacuum_report
        if not vacuum_report.get("ok"):
            report.update(
                {
                    "ok": False,
                    "reset_executed": False,
                    "reset": {
                        "mode": reset_mode,
                        "error": f"{exc.__class__.__name__}: {exc}",
                    },
                }
            )
            return report
        try:
            _create_search_index_schema(target)
        except sqlite3.DatabaseError as retry_exc:
            report.update(
                {
                    "ok": False,
                    "reset_executed": False,
                    "reset": {
                        "mode": reset_mode,
                        "error": f"{retry_exc.__class__.__name__}: {retry_exc}",
                    },
                }
            )
            return report
    source_report = _copy_search_index_source(target_db=target, source_db=source_search_db)
    after = _sqlite_diagnostics(target).get("search_index") or {}
    report.update(
        {
            "ok": bool(after.get("readable")) and not bool(source_report.get("errors")),
            "reset_executed": True,
            "reset": {
                "mode": reset_mode,
                "after": after,
                "protected_data": [
                    "clienti",
                    "fascicoli",
                    "agenda",
                    "scadenze",
                    "documenti originali",
                    "comunicazioni",
                ],
            },
            "source": source_report,
        }
    )
    return report


def _json_sources(paths: dict[str, str]) -> dict[str, str]:
    backup_dir = Path(paths.get("BACKUP_DIR", ""))
    return {
        "clienti": paths.get("CLIENTI_DB", ""),
        "fascicoli": paths.get("FASCICOLI_DB", ""),
        "soggetti": paths.get("SOGGETTI_DB", ""),
        "soggetti_parti": paths.get("SOGGETTI_PARTI_DB", ""),
        "appuntamenti": paths.get("AGENDA_DB", ""),
        "scadenze": paths.get("SCADENZIARIO_DB", ""),
        "timesheet": paths.get("TIMESHEET_DB", ""),
        "time_tracking": paths.get("TIME_TRACKING_DB", ""),
        "messaggi": paths.get("MESSAGGI_DB", ""),
        "preventivi": paths.get("PREVENTIVI_DB", ""),
        "fatturazione": paths.get("FATTURAZIONE_DB", ""),
        "email_casella": paths.get("EMAIL_CASELLA_DB", ""),
        "email_ordinaria": paths.get("EMAIL_ORDINARIA_DB", ""),
        "notifiche": paths.get("NOTIFICHE_LOG", ""),
        "privacy": paths.get("PRIVACY_DB", ""),
        "impostazioni": paths.get("CONFIG_STUDIO_DB", ""),
        "portale": paths.get("PORTALE_DB", ""),
        "backup": str(backup_dir / "registro.json") if backup_dir else "",
        "backup_config": str(backup_dir / "config.json") if backup_dir else "",
        "utenti": paths.get("AUTH_DB", ""),
        "audit": paths.get("AUDIT_DB", ""),
    }


def _audit_tenant(
    manager: GestioneTenant,
    slug: str,
    *,
    repair_json_mirror: bool,
    repair_search_index: bool,
) -> dict[str, Any]:
    paths = manager.percorsi_dati(slug, reconcile_aliases=False, ensure_baseline=False)
    repair_report: dict[str, Any] | None = None
    search_repair_report: dict[str, Any] | None = None
    if repair_json_mirror:
        sources = {key: value for key, value in _json_sources(paths).items() if value}
        mirror_report = _prepare_json_mirror_for_repair(paths["STUDIO_DB"])
        try:
            sync_report = GestioneDatabase(sources).sincronizza_moduli_json_sqlite(
                paths["STUDIO_DB"],
                include_structured=True,
            )
        except sqlite3.DatabaseError as exc:
            sync_report = {
                "ok": False,
                "percorso_db": paths["STUDIO_DB"],
                "error": f"{exc.__class__.__name__}: {exc}",
                "moduli_dati": 0,
                "moduli_json_records": 0,
                "modules": {},
                "errors": [f"{exc.__class__.__name__}: {exc}"],
            }
        repair_report = {
            "ok": bool(mirror_report.get("ok")) and bool(sync_report.get("ok")),
            "mirror": mirror_report,
            "sync": sync_report,
        }
    if repair_search_index:
        search_repair_report = _repair_search_index(
            paths["STUDIO_DB"],
            paths.get("SEARCH_INDEX", ""),
        )
    audit = audit_data_flow_contract(
        paths=paths,
        tenant_root=Path(paths["STUDIO_DB"]).parent,
    )
    return {
        "tenant": slug,
        "studio_db": paths.get("STUDIO_DB", ""),
        "sqlite_diagnostics": _sqlite_diagnostics(paths["STUDIO_DB"]),
        "repair_json_mirror": repair_report,
        "repair_search_index": search_repair_report,
        "audit": audit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica contratto dati/SQLite/PostgreSQL/tenant/route React."
    )
    parser.add_argument("--registry", default="data/tenants.json")
    parser.add_argument("--tenant", action="append", default=[])
    parser.add_argument("--repair-json-mirror", action="store_true")
    parser.add_argument("--repair-search-index", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    manager = GestioneTenant(args.registry)
    selected = list(args.tenant or [])
    if not selected:
        selected = [studio.slug for studio in manager.lista()]

    reports: list[dict[str, Any]] = []
    if selected:
        for slug in selected:
            reports.append(
                _audit_tenant(
                    manager,
                    slug,
                    repair_json_mirror=bool(args.repair_json_mirror),
                    repair_search_index=bool(args.repair_search_index),
                )
            )
    else:
        reports.append(
            {
                "tenant": None,
                "studio_db": None,
                "repair_json_mirror": None,
                "repair_search_index": None,
                "audit": audit_data_flow_contract(),
            }
        )

    ok = all(
        bool((report.get("audit") or {}).get("ok"))
        and bool((report.get("repair_json_mirror") or {"ok": True}).get("ok"))
        and bool((report.get("repair_search_index") or {"ok": True}).get("ok"))
        for report in reports
    )
    payload = {
        "ok": ok,
        "registry": args.registry,
        "tenants": reports,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Contratto dati/React: {'OK' if ok else 'ERRORE'}")
        for report in reports:
            tenant = report.get("tenant") or "schema"
            audit = report.get("audit") or {}
            print(f"- {tenant}: {'OK' if audit.get('ok') else 'ERRORE'}")
            for error in audit.get("errors") or []:
                print(f"  * {error}")
            for warning in audit.get("warnings") or []:
                print(f"  - Avviso: {warning}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
