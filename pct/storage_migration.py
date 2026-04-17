"""Migrazione ufficiale core storage: JSON -> SQLite -> PostgreSQL.

La migrazione e' tenant-aware e produce sempre un report di consistenza
persistito sotto la directory backup del tenant.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pct.auth import GestioneUtenti
from pct.database import GestioneDatabase
from pct.fascicoli import GestioneFascicoli
from pct.scadenziario import GestioneScadenziario
from pct.storage import StudioDB
from pct.core_storage_backend import build_postgres_backend

_CORE_TABLES = {
    "clienti": "clienti",
    "fascicoli": "fascicoli",
    "appuntamenti": "appuntamenti",
    "scadenze": "scadenze",
    "utenti": "utenti",
    "audit": "audit_log",
}


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row or {})


def _payload_cliente(row: Any) -> dict[str, Any]:
    raw = _row_dict(row)
    payload = {}
    try:
        if raw.get("dati_json"):
            payload = json.loads(raw["dati_json"])
    except Exception:
        payload = {}
    payload.setdefault("id", raw.get("id", ""))
    payload.setdefault("tipo", raw.get("tipo") or "PERSONA_FISICA")
    payload.setdefault("stato", raw.get("stato") or "ATTIVO")
    payload.setdefault("nome", raw.get("nome") or "")
    payload.setdefault("cognome", raw.get("cognome") or "")
    payload.setdefault("ragione_sociale", raw.get("ragione_sociale") or "")
    payload.setdefault("codice_fiscale", raw.get("codice_fiscale") or "")
    payload.setdefault("partita_iva", raw.get("partita_iva") or "")
    recapiti = payload.get("recapiti") if isinstance(payload.get("recapiti"), dict) else {}
    recapiti.setdefault("email_principale", raw.get("email") or payload.get("email") or "")
    recapiti.setdefault("telefono_principale", raw.get("telefono") or "")
    payload["recapiti"] = recapiti
    payload.setdefault("note", raw.get("note") or "")
    payload.setdefault("creato_il", raw.get("creato_il") or datetime.now().isoformat())
    payload.setdefault("modificato_il", raw.get("modificato_il") or payload["creato_il"])
    return payload


def _payload_appuntamento(row: Any) -> dict[str, Any]:
    raw = _row_dict(row)
    payload = {}
    try:
        if raw.get("dati_json"):
            payload = json.loads(raw["dati_json"])
    except Exception:
        payload = {}
    payload.setdefault("id", raw.get("id", ""))
    payload.setdefault("titolo", raw.get("titolo") or "")
    payload.setdefault("tipo", raw.get("tipo") or "ALTRO")
    payload.setdefault("stato", raw.get("stato") or "PROGRAMMATO")
    payload.setdefault("data_ora", raw.get("data_ora") or datetime.now().isoformat())
    payload.setdefault("durata_minuti", int(raw.get("durata_minuti") or 60))
    payload.setdefault("luogo", raw.get("luogo") or "")
    payload.setdefault("note", raw.get("note") or raw.get("descrizione") or "")
    payload.setdefault("cliente", raw.get("cliente") or "")
    payload.setdefault("cf_cliente", raw.get("cf_cliente") or "")
    payload.setdefault("procedimento", raw.get("procedimento") or "")
    payload.setdefault("tribunale", raw.get("tribunale") or "")
    payload.setdefault("creato_il", raw.get("creato_il") or datetime.now().isoformat())
    return payload


def _copy_clienti(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM clienti").fetchall()

    def _insert(conn, row):
        payload = _payload_cliente(row)
        recapiti = payload.get("recapiti") if isinstance(payload.get("recapiti"), dict) else {}
        conn.execute(
            """
            INSERT INTO clienti
            (id, tipo, stato, cognome, nome, ragione_sociale,
             codice_fiscale, partita_iva, email, telefono, note,
             creato_il, modificato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payload.get("id", ""),
                payload.get("tipo", "PERSONA_FISICA"),
                payload.get("stato", "ATTIVO"),
                payload.get("cognome", ""),
                payload.get("nome", ""),
                payload.get("ragione_sociale", ""),
                payload.get("codice_fiscale", ""),
                payload.get("partita_iva", ""),
                recapiti.get("email_principale", ""),
                recapiti.get("telefono_principale", ""),
                payload.get("note", ""),
                payload.get("creato_il", datetime.now().isoformat()),
                payload.get("modificato_il", datetime.now().isoformat()),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    target_backend.salva_tabella("clienti", list(rows), _insert)


def _copy_appuntamenti(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM appuntamenti").fetchall()

    def _insert(conn, row):
        payload = _payload_appuntamento(row)
        conn.execute(
            """
            INSERT INTO appuntamenti
            (id, tipo, stato, titolo, data_ora, durata_minuti, luogo,
             descrizione, cliente, cf_cliente, procedimento, tribunale,
             note, creato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payload.get("id", ""),
                payload.get("tipo", "ALTRO"),
                payload.get("stato", "PROGRAMMATO"),
                payload.get("titolo", ""),
                payload.get("data_ora", datetime.now().isoformat()),
                int(payload.get("durata_minuti", 60) or 60),
                payload.get("luogo", ""),
                payload.get("note", ""),
                payload.get("cliente", ""),
                payload.get("cf_cliente", ""),
                payload.get("procedimento", ""),
                payload.get("tribunale", ""),
                payload.get("note", ""),
                payload.get("creato_il", datetime.now().isoformat()),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    target_backend.salva_tabella("appuntamenti", list(rows), _insert)


def _json_record_count(path: str) -> int:
    file_path = Path(str(path or "").strip())
    if not file_path.exists() or file_path.suffix.lower() != ".json":
        return 0
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 1 if payload else 0


def _count_rows(backend: Any, table: str) -> int:
    try:
        row = backend.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    except Exception:
        return 0
    if row is None:
        return 0
    if isinstance(row, dict):
        return int(row.get("n", 0) or 0)
    return int(row[0] or 0)


class _TimespanEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "isoformat"):
            try:
                return obj.isoformat()
            except Exception:
                return str(obj)
        return super().default(obj)


def _build_json_to_sqlite_sources(paths: dict[str, str]) -> dict[str, str]:
    return {
        "clienti": paths.get("CLIENTI_DB", ""),
        "fascicoli": paths.get("FASCICOLI_DB", ""),
        "appuntamenti": paths.get("AGENDA_DB", ""),
        "scadenze": paths.get("SCADENZIARIO_DB", ""),
        "messaggi": paths.get("MESSAGGI_DB", ""),
        "utenti": paths.get("AUTH_DB", ""),
        "audit": paths.get("AUDIT_DB", ""),
        "privacy": paths.get("PRIVACY_DB", ""),
        "notifiche": paths.get("NOTIFICHE_LOG", ""),
        "backup": str(Path(paths.get("BACKUP_DIR", "./backup")) / "registro.json"),
        "search_index": paths.get("SEARCH_INDEX", ""),
    }


def _ensure_sqlite_stage(paths: dict[str, str]) -> dict[str, Any]:
    migratore = GestioneDatabase(_build_json_to_sqlite_sources(paths))
    risultato = migratore.migra_verso_sqlite(paths["STUDIO_DB"])
    return risultato.to_dict()


def _copy_core_state_to_target(
    *,
    sqlite_backend,
    target_backend,
    paths: dict[str, str],
    secret_key: str,
) -> None:
    _copy_clienti(sqlite_backend, target_backend)

    fascicoli_src = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
        studio_db=sqlite_backend,
    )
    fascicoli_dst = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
        studio_db=target_backend,
    )
    fascicoli_dst._fascicoli = {fascicolo.id: fascicolo for fascicolo in fascicoli_src.tutti(archiviati=True)}
    fascicoli_dst._salva()

    _copy_appuntamenti(sqlite_backend, target_backend)

    scadenziario_src = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"], studio_db=sqlite_backend)
    scadenziario_dst = GestioneScadenziario(db_path=paths["SCADENZIARIO_DB"], studio_db=target_backend)
    scadenziario_dst._scadenze = {row.id: row for row in scadenziario_src.tutte()}
    scadenziario_dst._salva()

    auth_src = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=secret_key,
        crea_admin_se_vuoto=False,
        studio_db=sqlite_backend,
    )
    auth_dst = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=secret_key,
        crea_admin_se_vuoto=False,
        studio_db=target_backend,
    )
    auth_dst._utenti = {utente.id: utente for utente in auth_src.lista()}
    auth_dst._audit = list(auth_src.audit_log(limit=10000))
    auth_dst._salva_utenti()
    auth_dst._salva_audit()


def migrate_core_storage_to_postgres(
    *,
    paths: dict[str, str],
    database_config: Any,
    secret_key: str,
    tenant_slug: str,
) -> dict[str, Any]:
    stage_sqlite = _ensure_sqlite_stage(paths)
    sqlite_backend = StudioDB.get(paths["STUDIO_DB"])
    postgres_backend = build_postgres_backend(database_config)
    if postgres_backend is None:
        raise ValueError("Configurazione PostgreSQL incompleta o non disponibile per il backend core")

    json_counts = {
        "clienti": _json_record_count(paths.get("CLIENTI_DB", "")),
        "fascicoli": _json_record_count(paths.get("FASCICOLI_DB", "")),
        "appuntamenti": _json_record_count(paths.get("AGENDA_DB", "")),
        "scadenze": _json_record_count(paths.get("SCADENZIARIO_DB", "")),
        "utenti": _json_record_count(paths.get("AUTH_DB", "")),
        "audit": _json_record_count(paths.get("AUDIT_DB", "")),
    }
    sqlite_counts_before = {
        key: _count_rows(sqlite_backend, table_name)
        for key, table_name in _CORE_TABLES.items()
    }

    _copy_core_state_to_target(
        sqlite_backend=sqlite_backend,
        target_backend=postgres_backend,
        paths=paths,
        secret_key=secret_key,
    )

    postgres_counts = {
        key: _count_rows(postgres_backend, table_name)
        for key, table_name in _CORE_TABLES.items()
    }
    consistency = {
        key: {
            "sqlite": sqlite_counts_before.get(key, 0),
            "postgres": postgres_counts.get(key, 0),
            "json": json_counts.get(key, 0),
            "ok": sqlite_counts_before.get(key, 0) == postgres_counts.get(key, 0),
        }
        for key in _CORE_TABLES
    }
    report = {
        "generated_at": datetime.now().isoformat(),
        "tenant_slug": tenant_slug,
        "selected_backend": "postgresql",
        "json_to_sqlite": stage_sqlite,
        "counts": {
            "json": json_counts,
            "sqlite": sqlite_counts_before,
            "postgres": postgres_counts,
        },
        "consistency": consistency,
        "success": all(item["ok"] for item in consistency.values()),
    }

    backup_dir = Path(paths.get("BACKUP_DIR", "./backup"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = backup_dir / f"storage_migration_postgresql_{stamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, cls=_TimespanEncoder),
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    return report
