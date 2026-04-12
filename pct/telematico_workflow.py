"""
Repository SQLite comune per i workflow telematici.

Affianca i moduli esistenti e offre un core unico per:
    - casi telematici
    - timeline eventi
    - documenti raggruppabili per busta (`id_deposito`, `tipo_atto`)
    - trasmissioni / import
    - task operativi
    - estensioni leggere per PDP, PAT e PTT
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Mapping


SCHEMA_SQL_TELEMATICO = """
CREATE TABLE IF NOT EXISTS telematic_cases (
    id TEXT PRIMARY KEY,
    practice_id TEXT NOT NULL,
    channel_family TEXT NOT NULL CHECK (channel_family IN ('ministero', 'amministrativo', 'tributario')),
    service_code TEXT NOT NULL CHECK (service_code IN ('polisweb_consultazione', 'pdp_penale', 'pat_siga', 'ptt_sigit')),
    office_name TEXT NOT NULL,
    office_type TEXT,
    district TEXT,
    register_type TEXT,
    register_number TEXT,
    register_year INTEGER,
    subject_name TEXT NOT NULL,
    subject_cf TEXT,
    counterparty_name TEXT,
    counsel_name TEXT NOT NULL,
    counsel_cf TEXT NOT NULL,
    portal_case_ref TEXT,
    portal_case_url TEXT,
    workflow_url TEXT,
    internal_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (internal_status IN ('draft', 'ready_for_filing', 'opened_official_portal', 'submitted', 'in_review', 'accepted', 'rejected', 'technical_error', 'integration_requested', 'download_available', 'download_completed', 'import_completed', 'manual_review_required', 'closed')),
    native_status TEXT,
    import_log_id TEXT,
    notes TEXT,
    last_sync_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_telematic_cases_practice ON telematic_cases(practice_id);
CREATE INDEX IF NOT EXISTS idx_telematic_cases_service ON telematic_cases(service_code, last_sync_at DESC);
CREATE INDEX IF NOT EXISTS idx_telematic_cases_register ON telematic_cases(register_type, register_number, register_year);

CREATE TABLE IF NOT EXISTS telematic_events (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_source TEXT NOT NULL DEFAULT 'system'
        CHECK (event_source IN ('system', 'user', 'portal', 'pec', 'import', 'manual')),
    title TEXT NOT NULL,
    description TEXT,
    payload_json TEXT,
    created_by_user_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_telematic_events_case ON telematic_events(telematic_case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS telematic_documents (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT NOT NULL,
    document_role TEXT NOT NULL
        CHECK (document_role IN ('main_act', 'attachment', 'receipt', 'outcome_notice', 'payment_receipt', 'pec_message', 'download_package', 'imported_case_file', 'judicial_order', 'judgment', 'hearing_minutes', 'cover_sheet', 'signature_report', 'other')),
    document_category TEXT,
    title TEXT NOT NULL,
    original_filename TEXT,
    file_path TEXT,
    file_size_bytes INTEGER,
    sha256 TEXT,
    source_type TEXT NOT NULL DEFAULT 'manual'
        CHECK (source_type IN ('manual', 'generated', 'portal', 'pec', 'download', 'import', 'system')),
    signed INTEGER NOT NULL DEFAULT 0 CHECK (signed IN (0,1)),
    signature_type TEXT,
    pdfa INTEGER NOT NULL DEFAULT 0 CHECK (pdfa IN (0,1)),
    verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0,1)),
    portal_document_ref TEXT,
    portal_document_date TEXT,
    id_deposito TEXT NOT NULL DEFAULT '',
    tipo_atto TEXT NOT NULL DEFAULT '',
    data_deposito TEXT,
    mittente TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_telematic_documents_case ON telematic_documents(telematic_case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_telematic_documents_portal_ref ON telematic_documents(portal_document_ref);
CREATE INDEX IF NOT EXISTS idx_telematic_documents_busta ON telematic_documents(telematic_case_id, id_deposito);

CREATE TABLE IF NOT EXISTS telematic_transmissions (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT NOT NULL,
    transmission_type TEXT NOT NULL
        CHECK (transmission_type IN ('filing', 'access_request', 'integration', 'appeal', 'instance', 'copy_request', 'temporary_access_request', 'case_import', 'other')),
    act_type TEXT,
    portal_reference TEXT,
    internal_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (internal_status IN ('draft', 'prepared', 'submitted', 'in_review', 'accepted', 'rejected', 'technical_error', 'closed')),
    native_status TEXT,
    submitted_at TEXT,
    outcome_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_telematic_transmissions_case ON telematic_transmissions(telematic_case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_telematic_transmissions_ref ON telematic_transmissions(portal_reference);

CREATE TABLE IF NOT EXISTS telematic_tasks (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT NOT NULL,
    task_type TEXT NOT NULL
        CHECK (task_type IN ('prepare_filing', 'check_documents', 'sign_documents', 'open_portal', 'register_outcome', 'check_pec', 'download_case_file', 'import_documents', 'manual_review', 'other')),
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'done', 'cancelled')),
    assigned_user_id TEXT,
    due_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_telematic_tasks_case ON telematic_tasks(telematic_case_id, status, due_at);

CREATE TABLE IF NOT EXISTS telematic_document_links (
    id TEXT PRIMARY KEY,
    transmission_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'attachment'
        CHECK (relation_type IN ('main_act', 'attachment', 'receipt', 'outcome', 'download', 'import')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (transmission_id) REFERENCES telematic_transmissions(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES telematic_documents(id) ON DELETE CASCADE,
    UNIQUE (transmission_id, document_id, relation_type)
);

CREATE TABLE IF NOT EXISTS pdp_access_requests (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT NOT NULL,
    request_type TEXT NOT NULL DEFAULT 'access_to_case_file',
    request_status TEXT NOT NULL DEFAULT 'draft',
    submitted_at TEXT,
    authorized_at TEXT,
    denied_at TEXT,
    pec_password_received INTEGER NOT NULL DEFAULT 0 CHECK (pec_password_received IN (0,1)),
    pec_password_received_at TEXT,
    download_available_until TEXT,
    downloaded_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pdp_access_requests_case ON pdp_access_requests(telematic_case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS telematic_pec_messages (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT,
    mailbox TEXT NOT NULL,
    sender TEXT,
    recipient TEXT,
    subject TEXT NOT NULL,
    message_date TEXT,
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_id_header TEXT,
    body_text TEXT,
    matched INTEGER NOT NULL DEFAULT 0 CHECK (matched IN (0,1)),
    contains_password INTEGER NOT NULL DEFAULT 0 CHECK (contains_password IN (0,1)),
    extracted_password TEXT,
    contains_download_notice INTEGER NOT NULL DEFAULT 0 CHECK (contains_download_notice IN (0,1)),
    processed INTEGER NOT NULL DEFAULT 0 CHECK (processed IN (0,1)),
    processed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pat_deposits (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT NOT NULL,
    deposit_type TEXT NOT NULL,
    deposit_module_code TEXT,
    filing_party_role TEXT,
    act_subject TEXT,
    submitted_at TEXT,
    outcome_at TEXT,
    outcome_status TEXT,
    portal_reference TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ptt_filings (
    id TEXT PRIMARY KEY,
    telematic_case_id TEXT NOT NULL,
    filing_type TEXT NOT NULL,
    act_subject TEXT,
    submitted_at TEXT,
    outcome_at TEXT,
    outcome_status TEXT,
    temporary_access_requested INTEGER NOT NULL DEFAULT 0 CHECK (temporary_access_requested IN (0,1)),
    sigit_reference TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telematic_case_id) REFERENCES telematic_cases(id) ON DELETE CASCADE
);

CREATE TRIGGER IF NOT EXISTS trg_telematic_cases_updated_at
AFTER UPDATE ON telematic_cases
FOR EACH ROW
BEGIN
    UPDATE telematic_cases SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_telematic_transmissions_updated_at
AFTER UPDATE ON telematic_transmissions
FOR EACH ROW
BEGIN
    UPDATE telematic_transmissions SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_telematic_tasks_updated_at
AFTER UPDATE ON telematic_tasks
FOR EACH ROW
BEGIN
    UPDATE telematic_tasks SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_pdp_access_requests_updated_at
AFTER UPDATE ON pdp_access_requests
FOR EACH ROW
BEGIN
    UPDATE pdp_access_requests SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_pat_deposits_updated_at
AFTER UPDATE ON pat_deposits
FOR EACH ROW
BEGIN
    UPDATE pat_deposits SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_ptt_filings_updated_at
AFTER UPDATE ON ptt_filings
FOR EACH ROW
BEGIN
    UPDATE ptt_filings SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE VIEW IF NOT EXISTS v_telematic_case_overview AS
SELECT
    tc.id,
    tc.practice_id,
    tc.channel_family,
    tc.service_code,
    tc.office_name,
    tc.register_type,
    tc.register_number,
    tc.register_year,
    tc.subject_name,
    tc.counsel_name,
    tc.internal_status,
    tc.native_status,
    tc.last_sync_at,
    (
        SELECT COUNT(*)
        FROM telematic_documents td
        WHERE td.telematic_case_id = tc.id
    ) AS documents_count,
    (
        SELECT COUNT(*)
        FROM telematic_tasks tt
        WHERE tt.telematic_case_id = tc.id
          AND tt.status IN ('open', 'in_progress')
    ) AS open_tasks_count,
    (
        SELECT MAX(te.created_at)
        FROM telematic_events te
        WHERE te.telematic_case_id = tc.id
    ) AS last_event_at,
    tc.created_at,
    tc.updated_at
FROM telematic_cases tc;
"""


def ensure_telematico_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL_TELEMATICO)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json_payload(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


class TelematicoWorkflowRepository:
    """CRUD compatto del modulo telematico comune."""

    _CASE_FIELDS = {
        "practice_id", "channel_family", "service_code", "office_name", "office_type",
        "district", "register_type", "register_number", "register_year", "subject_name",
        "subject_cf", "counterparty_name", "counsel_name", "counsel_cf", "portal_case_ref",
        "portal_case_url", "workflow_url", "internal_status", "native_status",
        "import_log_id", "notes", "last_sync_at", "archived",
    }
    _TRANSMISSION_FIELDS = {
        "transmission_type", "act_type", "portal_reference", "internal_status",
        "native_status", "submitted_at", "outcome_at", "notes",
    }
    _DOCUMENT_FIELDS = {
        "document_role", "document_category", "title", "original_filename", "file_path",
        "file_size_bytes", "sha256", "source_type", "signed", "signature_type", "pdfa",
        "verified", "portal_document_ref", "portal_document_date", "id_deposito",
        "tipo_atto", "data_deposito", "mittente", "notes",
    }

    def __init__(self, db: sqlite3.Connection | Any | str) -> None:
        self._owns_connection = False
        if isinstance(db, sqlite3.Connection):
            self.conn = db
            self.conn.row_factory = sqlite3.Row
        elif hasattr(db, "conn"):
            self.conn = db.conn
            self.conn.row_factory = sqlite3.Row
        else:
            db_path = Path(str(db))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self._owns_connection = True
        ensure_telematico_schema(self.conn)

    def close(self) -> None:
        if self._owns_connection:
            self.conn.close()

    def _insert(self, table: str, data: Mapping[str, Any]) -> dict[str, Any]:
        columns = list(data.keys())
        placeholders = ", ".join("?" for _ in columns)
        self.conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [data[col] for col in columns],
        )
        self.conn.commit()
        row = self.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (data["id"],)).fetchone()
        return _row_to_dict(row) or dict(data)

    def _update(self, table: str, row_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        assignments = ", ".join(f"{column} = ?" for column in data.keys())
        self.conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            [*data.values(), row_id],
        )
        self.conn.commit()
        row = self.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return _row_to_dict(row) or {"id": row_id, **data}

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        return _row_to_dict(
            self.conn.execute("SELECT * FROM telematic_cases WHERE id = ?", (case_id,)).fetchone()
        )

    def list_cases(self, *, practice_id: str | None = None, service_code: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if practice_id:
            clauses.append("practice_id = ?")
            params.append(practice_id)
        if service_code:
            clauses.append("service_code = ?")
            params.append(service_code)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            "SELECT * FROM v_telematic_case_overview "
            f"{where} ORDER BY COALESCE(last_sync_at, updated_at, created_at) DESC LIMIT ?",
            [*params, max(1, int(limit or 50))],
        ).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def list_recent_events(self, *, limit: int = 25) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT e.*, c.practice_id, c.service_code, c.channel_family
            FROM telematic_events e
            JOIN telematic_cases c ON c.id = e.telematic_case_id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (max(1, int(limit or 25)),),
        ).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def find_case(
        self,
        *,
        case_id: str | None = None,
        practice_id: str | None = None,
        service_code: str | None = None,
        portal_case_ref: str | None = None,
        office_name: str | None = None,
        register_type: str | None = None,
        register_number: str | None = None,
        register_year: int | None = None,
    ) -> dict[str, Any] | None:
        if case_id:
            return self.get_case(case_id)
        if practice_id and service_code and portal_case_ref:
            row = self.conn.execute(
                "SELECT * FROM telematic_cases WHERE practice_id = ? AND service_code = ? AND portal_case_ref = ? ORDER BY updated_at DESC LIMIT 1",
                (practice_id, service_code, portal_case_ref),
            ).fetchone()
            if row:
                return _row_to_dict(row)
        if practice_id and service_code and office_name and register_number and register_year:
            row = self.conn.execute(
                """
                SELECT * FROM telematic_cases
                WHERE practice_id = ? AND service_code = ? AND office_name = ?
                  AND COALESCE(register_type, '') = COALESCE(?, '')
                  AND COALESCE(register_number, '') = COALESCE(?, '')
                  AND COALESCE(register_year, 0) = COALESCE(?, 0)
                ORDER BY updated_at DESC LIMIT 1
                """,
                (practice_id, service_code, office_name, register_type or "", register_number or "", int(register_year or 0)),
            ).fetchone()
            if row:
                return _row_to_dict(row)
        if practice_id and service_code:
            row = self.conn.execute(
                "SELECT * FROM telematic_cases WHERE practice_id = ? AND service_code = ? ORDER BY updated_at DESC LIMIT 1",
                (practice_id, service_code),
            ).fetchone()
            return _row_to_dict(row)
        return None

    def upsert_case(self, **fields: Any) -> dict[str, Any]:
        payload = {key: value for key, value in fields.items() if key in self._CASE_FIELDS and value is not None}
        existing = self.find_case(
            case_id=str(fields.get("id") or "").strip() or None,
            practice_id=str(fields.get("practice_id") or "").strip() or None,
            service_code=str(fields.get("service_code") or "").strip() or None,
            portal_case_ref=str(fields.get("portal_case_ref") or "").strip() or None,
            office_name=str(fields.get("office_name") or "").strip() or None,
            register_type=str(fields.get("register_type") or "").strip() or None,
            register_number=str(fields.get("register_number") or "").strip() or None,
            register_year=int(fields.get("register_year") or 0) or None,
        )
        if existing:
            return self._update("telematic_cases", str(existing["id"]), payload)
        return self._insert("telematic_cases", {"id": str(fields.get("id") or _new_id("tm_case")), **payload})

    def add_event(self, telematic_case_id: str, *, event_type: str, title: str, event_source: str = "system", description: str = "", payload_json: Any = None, created_by_user_id: str = "") -> dict[str, Any]:
        return self._insert(
            "telematic_events",
            {
                "id": _new_id("tm_evt"),
                "telematic_case_id": telematic_case_id,
                "event_type": event_type,
                "event_source": event_source,
                "title": title,
                "description": description,
                "payload_json": _json_payload(payload_json),
                "created_by_user_id": created_by_user_id or None,
            },
        )

    def find_transmission(self, telematic_case_id: str, *, portal_reference: str = "", act_type: str = "") -> dict[str, Any] | None:
        if portal_reference:
            row = self.conn.execute(
                "SELECT * FROM telematic_transmissions WHERE telematic_case_id = ? AND portal_reference = ? ORDER BY updated_at DESC LIMIT 1",
                (telematic_case_id, portal_reference),
            ).fetchone()
            if row:
                return _row_to_dict(row)
        if act_type:
            row = self.conn.execute(
                "SELECT * FROM telematic_transmissions WHERE telematic_case_id = ? AND act_type = ? ORDER BY updated_at DESC LIMIT 1",
                (telematic_case_id, act_type),
            ).fetchone()
            return _row_to_dict(row)
        return None

    def upsert_transmission(self, telematic_case_id: str, **fields: Any) -> dict[str, Any]:
        payload = {key: value for key, value in fields.items() if key in self._TRANSMISSION_FIELDS and value is not None}
        existing = self.find_transmission(
            telematic_case_id,
            portal_reference=str(fields.get("portal_reference") or "").strip(),
            act_type=str(fields.get("act_type") or "").strip(),
        )
        if existing:
            return self._update("telematic_transmissions", str(existing["id"]), payload)
        return self._insert("telematic_transmissions", {"id": str(fields.get("id") or _new_id("tm_tx")), "telematic_case_id": telematic_case_id, **payload})

    def find_document(self, telematic_case_id: str, *, portal_document_ref: str = "", title: str = "", id_deposito: str = "") -> dict[str, Any] | None:
        if portal_document_ref:
            row = self.conn.execute(
                "SELECT * FROM telematic_documents WHERE telematic_case_id = ? AND portal_document_ref = ? ORDER BY created_at DESC LIMIT 1",
                (telematic_case_id, portal_document_ref),
            ).fetchone()
            if row:
                return _row_to_dict(row)
        if title and id_deposito:
            row = self.conn.execute(
                "SELECT * FROM telematic_documents WHERE telematic_case_id = ? AND title = ? AND id_deposito = ? ORDER BY created_at DESC LIMIT 1",
                (telematic_case_id, title, id_deposito),
            ).fetchone()
            return _row_to_dict(row)
        return None

    def upsert_document(self, telematic_case_id: str, **fields: Any) -> dict[str, Any]:
        payload = {key: value for key, value in fields.items() if key in self._DOCUMENT_FIELDS and value is not None}
        existing = self.find_document(
            telematic_case_id,
            portal_document_ref=str(fields.get("portal_document_ref") or "").strip(),
            title=str(fields.get("title") or "").strip(),
            id_deposito=str(fields.get("id_deposito") or "").strip(),
        )
        if existing:
            return self._update("telematic_documents", str(existing["id"]), payload)
        return self._insert("telematic_documents", {"id": str(fields.get("id") or _new_id("tm_doc")), "telematic_case_id": telematic_case_id, **payload})

    def link_document_to_transmission(self, transmission_id: str, document_id: str, *, relation_type: str = "attachment") -> dict[str, Any]:
        existing = self.conn.execute(
            "SELECT * FROM telematic_document_links WHERE transmission_id = ? AND document_id = ? AND relation_type = ? LIMIT 1",
            (transmission_id, document_id, relation_type),
        ).fetchone()
        if existing:
            return _row_to_dict(existing) or {}
        return self._insert(
            "telematic_document_links",
            {
                "id": _new_id("tm_lnk"),
                "transmission_id": transmission_id,
                "document_id": document_id,
                "relation_type": relation_type,
            },
        )

    def ensure_task(self, telematic_case_id: str, *, task_type: str, title: str, description: str = "", priority: str = "medium", due_at: str = "", assigned_user_id: str = "", status: str = "open") -> dict[str, Any]:
        existing = self.conn.execute(
            "SELECT * FROM telematic_tasks WHERE telematic_case_id = ? AND task_type = ? AND status IN ('open', 'in_progress') ORDER BY created_at DESC LIMIT 1",
            (telematic_case_id, task_type),
        ).fetchone()
        payload = {
            "title": title,
            "description": description,
            "priority": priority,
            "due_at": due_at or None,
            "assigned_user_id": assigned_user_id or None,
            "status": status,
        }
        if existing:
            return self._update("telematic_tasks", str(existing["id"]), payload)
        return self._insert(
            "telematic_tasks",
            {
                "id": _new_id("tm_task"),
                "telematic_case_id": telematic_case_id,
                "task_type": task_type,
                **payload,
            },
        )

    def close_tasks(self, telematic_case_id: str, *, task_type: str) -> None:
        self.conn.execute(
            "UPDATE telematic_tasks SET status = 'done', completed_at = datetime('now') WHERE telematic_case_id = ? AND task_type = ? AND status IN ('open', 'in_progress')",
            (telematic_case_id, task_type),
        )
        self.conn.commit()

    def case_stats(self) -> dict[str, Any]:
        rows = self.conn.execute(
            """
            SELECT
                service_code,
                COUNT(*) AS totale,
                SUM(CASE WHEN internal_status = 'import_completed' THEN 1 ELSE 0 END) AS import_completed,
                SUM(CASE WHEN internal_status IN ('download_available', 'manual_review_required') THEN 1 ELSE 0 END) AS attention_needed
            FROM telematic_cases
            WHERE archived = 0
            GROUP BY service_code
            """
        ).fetchall()
        per_service = {_row["service_code"]: _row_to_dict(_row) for _row in rows}
        return {
            "totale": sum(int((row or {}).get("totale") or 0) for row in per_service.values()),
            "per_service": per_service,
        }
