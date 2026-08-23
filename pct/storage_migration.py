"""Migrazione ufficiale core storage: JSON -> SQLite -> PostgreSQL.

La migrazione e' tenant-aware e produce sempre un report di consistenza
persistito sotto la directory backup del tenant.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from pct.auth import GestioneUtenti
from pct.database import GestioneDatabase
from pct.fatturazione import GestioneFatturazione
from pct.fascicoli import GestioneFascicoli
from pct.preventivi import GestionePreventivi
from pct.storage import StudioDB
from pct.core_storage_backend import build_postgres_backend
from pct.timesheet import GestioneTimesheet

_CORE_TABLES = {
    "clienti": "clienti",
    "fascicoli": "fascicoli",
    "soggetti": "soggetti",
    "soggetti_parti": "soggetti_parti",
    "appuntamenti": "appuntamenti",
    "scadenze": "scadenze",
    "timesheet": "timesheet_entries",
    "time_tracking": "time_tracking_timers",
    "messaggi": "messaggi",
    "preventivi": "preventivi_records",
    "conferimenti": "conferimenti_records",
    "fatturazione": "parcelle",
    "pagamenti_links": "payment_links",
    "pagamenti_config": "payment_config",
    "impostazioni": "settings_config",
    "utenti": "utenti",
    "audit": "audit_log",
    "privacy": "privacy_trattamenti",
    "notifiche": "notifiche_log",
    "backup_config": "backup_config",
    "backup": "backup_records",
    "moduli_dati": "moduli_dati",
    "moduli_json_records": "moduli_json_records",
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
    recapiti.setdefault("email", raw.get("email") or payload.get("email") or recapiti.get("email_principale") or "")
    recapiti.setdefault("telefono", raw.get("telefono") or recapiti.get("telefono_principale") or "")
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
                recapiti.get("email", "") or recapiti.get("email_principale", ""),
                recapiti.get("telefono", "") or recapiti.get("telefono_principale", ""),
                payload.get("note", ""),
                payload.get("creato_il", datetime.now().isoformat()),
                payload.get("modificato_il", datetime.now().isoformat()),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    target_backend.salva_tabella("clienti", list(rows), _insert)


def _copy_soggetti(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM soggetti").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO soggetti
            (id, tipo, nome, cognome, ragione_sociale, codice_fiscale,
             partita_iva, qualifica, id_cliente, email, telefono,
             creato_il, modificato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("tipo", "PERSONA_FISICA"),
                raw.get("nome", ""),
                raw.get("cognome", ""),
                raw.get("ragione_sociale", ""),
                raw.get("codice_fiscale", ""),
                raw.get("partita_iva", ""),
                raw.get("qualifica", ""),
                raw.get("id_cliente"),
                raw.get("email", ""),
                raw.get("telefono", ""),
                raw.get("creato_il", ""),
                raw.get("modificato_il", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("soggetti", list(rows), _insert)


def _copy_soggetti_parti(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM soggetti_parti").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO soggetti_parti
            (id, id_fascicolo, id_soggetto, ruolo, note, data_aggiunta, dati_json)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("id_fascicolo"),
                raw.get("id_soggetto"),
                raw.get("ruolo", "ALTRO"),
                raw.get("note", ""),
                raw.get("data_aggiunta", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("soggetti_parti", list(rows), _insert)


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


def _copy_scadenze(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM scadenze").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO scadenze
            (id, tipo, stato, titolo, data_scadenza, priorita, perentorio, note,
             id_fascicolo, id_appuntamento, id_utente, giorni_preavviso,
             avvisi_inviati, completata_il, creato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("tipo", "ALTRO"),
                raw.get("stato", "APERTO"),
                raw.get("titolo", ""),
                raw.get("data_scadenza", ""),
                raw.get("priorita", "MEDIA"),
                int(raw.get("perentorio") or 0),
                raw.get("note", ""),
                raw.get("id_fascicolo"),
                raw.get("id_appuntamento"),
                raw.get("id_utente", ""),
                raw.get("giorni_preavviso", "[]"),
                raw.get("avvisi_inviati", "[]"),
                raw.get("completata_il", ""),
                raw.get("creato_il", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("scadenze", list(rows), _insert)


def _copy_time_tracking(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM time_tracking_timers").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO time_tracking_timers
            (id, user_id, username, id_fascicolo, id_cliente, activity_type,
             description, started_at, paused_at, ended_at, elapsed_seconds,
             status, timesheet_entry_id, created_at, updated_at, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("user_id", ""),
                raw.get("username", ""),
                raw.get("id_fascicolo"),
                raw.get("id_cliente"),
                raw.get("activity_type", "other"),
                raw.get("description", ""),
                raw.get("started_at", ""),
                raw.get("paused_at"),
                raw.get("ended_at"),
                int(raw.get("elapsed_seconds") or 0),
                raw.get("status", "running"),
                raw.get("timesheet_entry_id"),
                raw.get("created_at", ""),
                raw.get("updated_at", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("time_tracking_timers", list(rows), _insert)


def _copy_messaggi(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM messaggi").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO messaggi
            (id, canale, stato, oggetto, corpo, email_destinatario,
             telefono_destinatario, id_cliente, id_fascicolo, tipo_automazione,
             inviato_il, errore_invio, creato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("canale", "EMAIL"),
                raw.get("stato", "BOZZA"),
                raw.get("oggetto", ""),
                raw.get("corpo", ""),
                raw.get("email_destinatario", ""),
                raw.get("telefono_destinatario", ""),
                raw.get("id_cliente"),
                raw.get("id_fascicolo"),
                raw.get("tipo_automazione", ""),
                raw.get("inviato_il", ""),
                raw.get("errore_invio", ""),
                raw.get("creato_il", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("messaggi", list(rows), _insert)


def _copy_privacy_trattamenti(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM privacy_trattamenti").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO privacy_trattamenti
            (id, nome, finalita, categoria_dati, base_giuridica,
             soggetti_interessati, destinatari, trasferimento_extra_ue,
             paese_destinazione, termine_conservazione, misure_sicurezza,
             responsabile, attivo, note, creato_il, modificato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("nome", ""),
                raw.get("finalita", ""),
                raw.get("categoria_dati", ""),
                raw.get("base_giuridica", ""),
                raw.get("soggetti_interessati", ""),
                raw.get("destinatari", ""),
                int(raw.get("trasferimento_extra_ue") or 0),
                raw.get("paese_destinazione", ""),
                raw.get("termine_conservazione", ""),
                raw.get("misure_sicurezza", ""),
                raw.get("responsabile", ""),
                int(raw.get("attivo") if raw.get("attivo") is not None else 1),
                raw.get("note", ""),
                raw.get("creato_il", ""),
                raw.get("modificato_il", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("privacy_trattamenti", list(rows), _insert)


def _copy_notifiche_log(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM notifiche_log").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO notifiche_log
            (id, timestamp, tipo, cliente, numero, utente, esito_json, payload_json)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id"),
                raw.get("timestamp", ""),
                raw.get("tipo", ""),
                raw.get("cliente", ""),
                raw.get("numero", ""),
                raw.get("utente", ""),
                raw.get("esito_json", "{}"),
                raw.get("payload_json", "{}"),
            ),
        )

    target_backend.salva_tabella("notifiche_log", list(rows), _insert)


def _copy_backup_config(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM backup_config").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO backup_config
            (chiave, valore, payload_json)
            VALUES (?,?,?)
            """,
            (
                raw.get("chiave", ""),
                raw.get("valore", ""),
                raw.get("payload_json", "{}"),
            ),
        )

    target_backend.salva_tabella("backup_config", list(rows), _insert)


def _copy_backup_records(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM backup_records").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO backup_records
            (id, timestamp, tipo, stato, percorso_file, hash_file,
             dimensione_bytes, num_file, componenti_json, cifrato, nota,
             errore, backup_base_id, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("timestamp", ""),
                raw.get("tipo", ""),
                raw.get("stato", ""),
                raw.get("percorso_file", ""),
                raw.get("hash_file", ""),
                int(raw.get("dimensione_bytes") or 0),
                int(raw.get("num_file") or 0),
                raw.get("componenti_json", "[]"),
                int(raw.get("cifrato") or 0),
                raw.get("nota", ""),
                raw.get("errore", ""),
                raw.get("backup_base_id", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("backup_records", list(rows), _insert)


def _copy_payment_config(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM payment_config").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO payment_config
            (config_id, provider_count, updated_at, dati_json)
            VALUES (?,?,?,?)
            """,
            (
                raw.get("config_id", "default"),
                int(raw.get("provider_count") or 0),
                raw.get("updated_at", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("payment_config", list(rows), _insert)


def _copy_payment_links(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM payment_links").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO payment_links
            (id, token, id_parcella, id_cliente, importo, valuta, stato,
             provider_usato, provider_tx_id, creato_il, scade_il, pagato_il, dati_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""),
                raw.get("token", ""),
                raw.get("id_parcella", ""),
                raw.get("id_cliente"),
                float(raw.get("importo") or 0),
                raw.get("valuta", "EUR"),
                raw.get("stato", "ATTESO"),
                raw.get("provider_usato", ""),
                raw.get("provider_tx_id", ""),
                raw.get("creato_il", ""),
                raw.get("scade_il", ""),
                raw.get("pagato_il", ""),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("payment_links", list(rows), _insert)


def _copy_settings_config(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM settings_config").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO settings_config
            (section, updated_at, source, secret_fields_json, dati_json)
            VALUES (?,?,?,?,?)
            """,
            (
                raw.get("section", ""),
                raw.get("updated_at", ""),
                raw.get("source", "config_studio"),
                raw.get("secret_fields_json", "[]"),
                raw.get("dati_json", "{}"),
            ),
        )

    target_backend.salva_tabella("settings_config", list(rows), _insert)


def _copy_moduli_dati(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM moduli_dati").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO moduli_dati
            (nome, percorso, storage_kind, inizializzato_il, payload_json)
            VALUES (?,?,?,?,?)
            """,
            (
                raw.get("nome", ""),
                raw.get("percorso", ""),
                raw.get("storage_kind", "json"),
                raw.get("inizializzato_il", ""),
                raw.get("payload_json", "{}"),
            ),
        )

    target_backend.salva_tabella("moduli_dati", list(rows), _insert)


def _copy_moduli_json_records(sqlite_backend, target_backend) -> None:
    rows = sqlite_backend.conn.execute("SELECT * FROM moduli_json_records").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO moduli_json_records
            (modulo, record_key, record_index, record_kind, payload_json)
            VALUES (?,?,?,?,?)
            """,
            (
                raw.get("modulo", ""),
                raw.get("record_key", ""),
                int(raw.get("record_index") or 0),
                raw.get("record_kind", "dict"),
                raw.get("payload_json", "{}"),
            ),
        )

    target_backend.salva_tabella("moduli_json_records", list(rows), _insert)


def _copy_transactional_outbox(sqlite_backend, target_backend) -> None:
    """Trasferisce gli eventi pendenti senza rigenerarli o cambiarne la chiave."""

    rows = sqlite_backend.conn.execute("SELECT * FROM transactional_outbox").fetchall()

    def _insert(conn, row):
        raw = _row_dict(row)
        conn.execute(
            """
            INSERT INTO transactional_outbox
            (id, tenant_id, aggregate_type, aggregate_id, aggregate_version, event_type,
             idempotency_key, actor_id, correlation_id, causation_id, payload_json, status,
             attempts, available_at, created_at, processed_at, last_error)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                raw.get("id", ""), raw.get("tenant_id", ""), raw.get("aggregate_type", ""),
                raw.get("aggregate_id", ""), int(raw.get("aggregate_version") or 1),
                raw.get("event_type", ""), raw.get("idempotency_key", ""),
                raw.get("actor_id", "sistema"),
                raw.get("correlation_id", ""), raw.get("causation_id", ""),
                raw.get("payload_json", "{}"), raw.get("status", "PENDING"),
                int(raw.get("attempts") or 0), raw.get("available_at", ""),
                raw.get("created_at", ""), raw.get("processed_at"), raw.get("last_error"),
            ),
        )

    target_backend.salva_tabella("transactional_outbox", list(rows), _insert)


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


def _safe_module_suffix(relative: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in relative.lower()).strip("_")
    digest = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:12]
    head = cleaned[:72].strip("_") or "file"
    return f"{head}_{digest}"


def _add_source(
    sources: dict[str, str],
    module: str,
    path: str | Path | None,
    *,
    seen_paths: set[str],
) -> None:
    raw = str(path or "").strip()
    if not raw:
        return
    resolved = str(Path(raw).resolve())
    if resolved in seen_paths:
        return
    sources[module] = raw
    seen_paths.add(resolved)


def _add_recursive_json_sources(
    sources: dict[str, str],
    root: str | Path | None,
    prefix: str,
    *,
    seen_paths: set[str],
) -> None:
    raw = str(root or "").strip()
    if not raw:
        return
    base = Path(raw)
    if not base.exists() or not base.is_dir():
        return
    for path in sorted(base.rglob("*.json")):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(base).as_posix()
        except ValueError:
            relative = path.name
        _add_source(
            sources,
            f"{prefix}_{_safe_module_suffix(relative)}",
            path,
            seen_paths=seen_paths,
        )


def _build_json_to_sqlite_sources(
    paths: dict[str, str],
    *,
    include_recursive: bool = False,
) -> dict[str, str]:
    """Costruisce il catalogo dei mirror JSON governati.

    Il runtime importa soltanto i moduli esplicitamente configurati. Le
    directory ricorsive possono contenere OCR, testi estratti e staging molto
    pesanti: duplicarle in ``studio.db`` rallenta ogni studio e fa crescere il
    WAL senza aggiungere una nuova fonte di verita'. Gli strumenti espliciti di
    audit possono abilitarle per censimento/riparazione controllata.
    """
    preventivi_path = str(paths.get("PREVENTIVI_DB", "") or "").strip()
    conferimenti_path = (
        str(Path(preventivi_path).with_name("conferimenti.json"))
        if preventivi_path
        else ""
    )
    pagamenti_dir = str(paths.get("PAGAMENTI_DIR", "") or "").strip()
    sources: dict[str, str] = {}
    seen_paths: set[str] = set()

    for module, path in {
        "calendar_sync": paths.get("CALENDAR_SYNC_DB", ""),
        "calendar_sync_engine": paths.get("CALENDAR_SYNC_ENGINE_DB", ""),
        "calendar_conflicts": paths.get("CALENDAR_CONFLICTS_DB", ""),
        "calendar_token": paths.get("CALENDAR_TOKEN_DB", ""),
        "clienti": paths.get("CLIENTI_DB", ""),
        "condivisioni": paths.get("CONDIVISIONI_DB", ""),
        "note_faldone": paths.get("NOTE_FALDONE_DB", ""),
        "fascicoli": paths.get("FASCICOLI_DB", ""),
        "practice_engine": paths.get("PRACTICE_ENGINE_DB", ""),
        "appuntamenti": paths.get("AGENDA_DB", ""),
        "scadenze": paths.get("SCADENZIARIO_DB", ""),
        "timesheet": paths.get("TIMESHEET_DB", ""),
        "time_tracking": paths.get("TIME_TRACKING_DB", ""),
        "preventivi": preventivi_path,
        "conferimenti": conferimenti_path,
        "fatturazione": paths.get("FATTURAZIONE_DB", ""),
        "pagamenti_config": str(Path(pagamenti_dir) / "config.json") if pagamenti_dir else "",
        "pagamenti_links": str(Path(pagamenti_dir) / "transazioni.json") if pagamenti_dir else "",
        "impostazioni": paths.get("STUDIO_CONFIG", ""),
        "storage_config": paths.get("STORAGE_CONFIG", ""),
        "studio_local_pack": paths.get("STUDIO_LOCAL_PACK_DB", ""),
        "messaggi": paths.get("MESSAGGI_DB", ""),
        "utenti": paths.get("AUTH_DB", ""),
        "audit": paths.get("AUDIT_DB", ""),
        "email_casella": paths.get("EMAIL_CASELLA_DB", ""),
        "email_ordinaria": paths.get("EMAIL_ORDINARIA_DB", ""),
        "privacy": paths.get("PRIVACY_DB", ""),
        "notifiche": paths.get("NOTIFICHE_LOG", ""),
        "backup_config": str(Path(paths.get("BACKUP_DIR", "./backup")) / "config.json"),
        "backup": str(Path(paths.get("BACKUP_DIR", "./backup")) / "registro.json"),
        "portale": paths.get("PORTALE_DB", ""),
        "soggetti": paths.get("SOGGETTI_DB", ""),
        "soggetti_parti": paths.get("SOGGETTI_PARTI_DB", ""),
        "wizard_pro": paths.get("WIZARD_PRO_DB", ""),
        "documenti_ai": paths.get("DOCUMENTI_AI_DB", ""),
        "editor_ai": paths.get("EDITOR_AI_DB", ""),
        "pec_cancelleria_state": paths.get("PEC_CANCELLERIA_STATE_DB", ""),
        "legal_intelligence": paths.get("LEGAL_INTELLIGENCE_DB", ""),
        "legal_updates_repository": paths.get("LEGAL_UPDATES_JSON", ""),
        "giurisprudenza_repository": paths.get("GIURISPRUDENZA_REPOSITORY_DB", ""),
        "giurisprudenza_sources_repository": paths.get("GIURISPRUDENZA_SOURCES_REPOSITORY_DB", ""),
        "giurisprudenza_sync_registry": paths.get("GIURISPRUDENZA_SYNC_REGISTRY_DB", ""),
        "giurisprudenza_taxonomy_repository": paths.get("GIURISPRUDENZA_TAXONOMY_REPOSITORY_DB", ""),
        "giurisprudenza_usage_policy": paths.get("GIURISPRUDENZA_USAGE_POLICY_DB", ""),
        "legal_engine_source_edges": paths.get("LEGAL_ENGINE_SOURCE_EDGES_DB", ""),
        "legal_engines_repository": paths.get("LEGAL_ENGINES_REPOSITORY_DB", ""),
        "legal_intelligence_repository": paths.get("LEGAL_INTELLIGENCE_REPOSITORY_DB", ""),
        "legal_keyword_to_engine": paths.get("LEGAL_KEYWORD_TO_ENGINE_DB", ""),
        "legal_keyword_to_source": paths.get("LEGAL_KEYWORD_TO_SOURCE_DB", ""),
        "legal_operational_repository": paths.get("LEGAL_OPERATIONAL_REPOSITORY_DB", ""),
        "legal_sources_repository": paths.get("LEGAL_SOURCES_REPOSITORY_DB", ""),
        "telematico_actions_repository": paths.get("TELEMATICO_ACTIONS_REPOSITORY_DB", ""),
        "telematico_capabilities_repository": paths.get("TELEMATICO_CAPABILITIES_REPOSITORY_DB", ""),
        "telematico_catalog_snapshot": paths.get("TELEMATICO_CATALOG_SNAPSHOT_DB", ""),
        "telematico_catalog_sources_repository": paths.get("TELEMATICO_CATALOG_SOURCES_REPOSITORY_DB", ""),
        "telematico_methods_repository": paths.get("TELEMATICO_METHODS_REPOSITORY_DB", ""),
        "telematico_monitoring_repository": paths.get("TELEMATICO_MONITORING_REPOSITORY_DB", ""),
        "telematico_repository": paths.get("TELEMATICO_REPOSITORY_JSON", ""),
        "telematico_rules_repository": paths.get("TELEMATICO_RULES_REPOSITORY_DB", ""),
        "telematico_sources_repository": paths.get("TELEMATICO_SOURCES_REPOSITORY_DB", ""),
        "telematico_wizard_sections_repository": paths.get("TELEMATICO_WIZARD_SECTIONS_REPOSITORY_DB", ""),
        "telematico_wsdl_modules_repository": paths.get("TELEMATICO_WSDL_MODULES_REPOSITORY_DB", ""),
        "telematico_xsd_channels_repository": paths.get("TELEMATICO_XSD_CHANNELS_REPOSITORY_DB", ""),
        "legal_skills_profile": paths.get("LEGAL_SKILLS_PROFILE_DB", ""),
        "legal_skills_runs": paths.get("LEGAL_SKILLS_RUNS_DB", ""),
        "legal_skills_scheduled": paths.get("LEGAL_SKILLS_SCHEDULED_DB", ""),
        "normative_tables": paths.get("NORMATIVE_TABLES_DB", ""),
        "giurisprudenza": paths.get("GIURISPRUDENZA_DB", ""),
        "workspace_intelligence": paths.get("WORKSPACE_INTELLIGENCE_DB", ""),
        "workflow_agents_runs": paths.get("WORKFLOW_AGENTS_RUNS_DB", ""),
        "workflow_agents_metrics": paths.get("WORKFLOW_AGENTS_METRICS_DB", ""),
        "workflow_agents_actions": paths.get("WORKFLOW_AGENTS_ACTIONS_DB", ""),
        "local_ai": paths.get("LOCAL_AI_DB", ""),
        "validation_runs": paths.get("VALIDATION_RUNS_DB", ""),
        "template_atti": paths.get("TEMPLATE_ATTI_DB", ""),
        "template_repository": paths.get("TEMPLATE_REPOSITORY_DB", ""),
        "template_atti_prefs": paths.get("TEMPLATE_ATTI_PREFS_DB", ""),
        "redaction_assistant": paths.get("REDACTION_ASSISTANT_DB", ""),
        "preventivi_repository": paths.get("PREVENTIVI_REPOSITORY_DB", ""),
        "preventivi_workflow_states": paths.get("PREVENTIVI_WORKFLOW_STATES_DB", ""),
        "preventivi_field_map": paths.get("PREVENTIVI_FIELD_MAP_DB", ""),
        "preventivi_rules": paths.get("PREVENTIVI_RULES_DB", ""),
        "termini_processuali": paths.get("TERMINI_PROCESSUALI_DB", ""),
        "telematico": paths.get("TELEMATICO_DB", ""),
        "search_index": paths.get("SEARCH_INDEX", ""),
    }.items():
        _add_source(sources, module, path, seen_paths=seen_paths)

    if include_recursive:
        _add_recursive_json_sources(
            sources,
            paths.get("DOCUMENTI_AI_DIR") or (
                str(Path(paths.get("FASCICOLI_DB", "")).resolve().parent / "documenti_ai")
                if paths.get("FASCICOLI_DB")
                else ""
            ),
            "documenti_ai_file",
            seen_paths=seen_paths,
        )
        _add_recursive_json_sources(
            sources,
            paths.get("FASCICOLI_IMPORTAZIONI_DIR") or (
                str(Path(paths.get("FASCICOLI_DB", "")).resolve().parent / "importazioni")
                if paths.get("FASCICOLI_DB")
                else ""
            ),
            "fascicoli_importazione",
            seen_paths=seen_paths,
        )
        _add_recursive_json_sources(
            sources,
            paths.get("LEX_DATASET_DIR") or (
                str(Path(paths.get("LEGAL_INTELLIGENCE_DB", "")).resolve().parent / "lex_dataset")
                if paths.get("LEGAL_INTELLIGENCE_DB")
                else ""
            ),
            "lex_dataset",
            seen_paths=seen_paths,
        )
    return sources


def _ensure_sqlite_stage(paths: dict[str, str], *, stage_path: str = "") -> dict[str, Any]:
    target_path = str(stage_path or paths["STUDIO_DB"]).strip()
    if not target_path:
        raise ValueError("Percorso SQLite di staging non configurato.")
    if not stage_path:
        try:
            StudioDB.get(paths["STUDIO_DB"]).chiudi()
        except Exception:
            pass
    migratore = GestioneDatabase(_build_json_to_sqlite_sources(paths))
    risultato = migratore.migra_verso_sqlite(target_path)
    payload = risultato.to_dict()
    payload["stage_db_path"] = target_path
    return payload


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

    _copy_soggetti(sqlite_backend, target_backend)
    _copy_soggetti_parti(sqlite_backend, target_backend)

    _copy_appuntamenti(sqlite_backend, target_backend)
    _copy_scadenze(sqlite_backend, target_backend)

    timesheet_path = paths.get("TIMESHEET_DB")
    if timesheet_path:
        timesheet_src = GestioneTimesheet(db_path=timesheet_path, studio_db=sqlite_backend)
        timesheet_dst = GestioneTimesheet(db_path=timesheet_path, studio_db=target_backend)
        timesheet_dst._entries = {row.id: row for row in timesheet_src.tutte()}
        timesheet_dst._salva()

    _copy_time_tracking(sqlite_backend, target_backend)
    _copy_messaggi(sqlite_backend, target_backend)
    _copy_privacy_trattamenti(sqlite_backend, target_backend)
    _copy_notifiche_log(sqlite_backend, target_backend)
    _copy_backup_config(sqlite_backend, target_backend)
    _copy_backup_records(sqlite_backend, target_backend)

    preventivi_path = paths.get("PREVENTIVI_DB", "")
    if preventivi_path:
        preventivi_src = GestionePreventivi(db_path=preventivi_path, studio_db=sqlite_backend)
        preventivi_dst = GestionePreventivi(db_path=preventivi_path, studio_db=target_backend)
        preventivi_dst._preventivi = {
            row.id: row for row in preventivi_src.tutti_preventivi()
        }
        preventivi_dst._conferimenti = {
            row.id: row for row in preventivi_src.tutti_conferimenti()
        }
        preventivi_dst._salva_preventivi()
        preventivi_dst._salva_conferimenti()

    fatturazione_path = paths.get("FATTURAZIONE_DB", "")
    if fatturazione_path:
        fatturazione_src = GestioneFatturazione(db_path=fatturazione_path, studio_db=sqlite_backend)
        fatturazione_dst = GestioneFatturazione(db_path=fatturazione_path, studio_db=target_backend)
        fatturazione_dst._parcelle = {
            row.id: row for row in fatturazione_src.tutte()
        }
        fatturazione_dst._salva()

    pagamenti_dir = paths.get("PAGAMENTI_DIR", "")
    if pagamenti_dir:
        _copy_payment_config(sqlite_backend, target_backend)
        _copy_payment_links(sqlite_backend, target_backend)

    _copy_settings_config(sqlite_backend, target_backend)

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

    _copy_moduli_dati(sqlite_backend, target_backend)
    _copy_moduli_json_records(sqlite_backend, target_backend)
    _copy_transactional_outbox(sqlite_backend, target_backend)


def migrate_core_storage_to_postgres(
    *,
    paths: dict[str, str],
    database_config: Any,
    secret_key: str,
    tenant_slug: str,
) -> dict[str, Any]:
    stage_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stage_db_path = str(
        Path(paths.get("BACKUP_DIR", "./backup")) / f"sqlite_stage_{tenant_slug}_{stage_stamp}.db"
    )
    stage_sqlite = _ensure_sqlite_stage(paths, stage_path=stage_db_path)
    sqlite_backend = StudioDB.get(stage_sqlite["stage_db_path"])
    sqlite_backend.ensure_schema()
    postgres_backend = build_postgres_backend(database_config)
    if postgres_backend is None:
        raise ValueError("Configurazione PostgreSQL incompleta o non disponibile per il backend core")

    json_counts = {
        "clienti": _json_record_count(paths.get("CLIENTI_DB", "")),
        "fascicoli": _json_record_count(paths.get("FASCICOLI_DB", "")),
        "appuntamenti": _json_record_count(paths.get("AGENDA_DB", "")),
        "scadenze": _json_record_count(paths.get("SCADENZIARIO_DB", "")),
        "timesheet": _json_record_count(paths.get("TIMESHEET_DB", "")),
        "time_tracking": _json_record_count(paths.get("TIME_TRACKING_DB", "")),
        "messaggi": _json_record_count(paths.get("MESSAGGI_DB", "")),
        "preventivi": _json_record_count(paths.get("PREVENTIVI_DB", "")),
        "conferimenti": _json_record_count(
            str(Path(paths.get("PREVENTIVI_DB", "")).with_name("conferimenti.json"))
            if paths.get("PREVENTIVI_DB")
            else ""
        ),
        "fatturazione": _json_record_count(paths.get("FATTURAZIONE_DB", "")),
        "pagamenti_links": _json_record_count(
            str(Path(paths.get("PAGAMENTI_DIR", "")) / "transazioni.json")
            if paths.get("PAGAMENTI_DIR")
            else ""
        ),
        "pagamenti_config": 1
        if Path(str(Path(paths.get("PAGAMENTI_DIR", "")) / "config.json")).exists()
        else 0,
        "utenti": _json_record_count(paths.get("AUTH_DB", "")),
        "audit": _json_record_count(paths.get("AUDIT_DB", "")),
        "privacy": _json_record_count(paths.get("PRIVACY_DB", "")),
        "notifiche": _json_record_count(paths.get("NOTIFICHE_LOG", "")),
        "backup_config": 1
        if Path(str(Path(paths.get("BACKUP_DIR", "")) / "config.json")).exists()
        else 0,
        "backup": _json_record_count(
            str(Path(paths.get("BACKUP_DIR", "")) / "registro.json")
            if paths.get("BACKUP_DIR")
            else ""
        ),
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
        "stage_db_path": stage_sqlite.get("stage_db_path", ""),
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
