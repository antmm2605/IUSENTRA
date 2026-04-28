"""
Repository SQLite per il workflow PDP Penale.

Questo modulo introduce il primo slice strutturato del flusso penale:
    - fascicolo ministeriale collegato alla pratica interna (`practice_id`)
    - timeline eventi
    - documenti
    - richieste di accesso
    - PEC collegate
    - task operativi

La scelta e' volutamente coerente con il repo attuale:
Python/Flask + SQLite, senza introdurre un backend Go parallelo.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping


SCHEMA_SQL_PDP_PENALE = """
CREATE TABLE IF NOT EXISTS criminal_cases (
    id TEXT PRIMARY KEY,
    practice_id TEXT NOT NULL,
    minister_case_ref TEXT,
    office_name TEXT NOT NULL,
    office_type TEXT,
    district TEXT,
    register_type TEXT,
    register_number TEXT NOT NULL,
    register_year INTEGER NOT NULL,
    proceeding_type TEXT,
    prosecutor_name TEXT,
    judge_name TEXT,
    chamber_section TEXT,
    assisted_party_name TEXT NOT NULL,
    assisted_party_cf TEXT,
    defense_counsel_name TEXT NOT NULL,
    defense_counsel_cf TEXT NOT NULL,
    nomination_status TEXT NOT NULL DEFAULT 'missing'
        CHECK (nomination_status IN ('missing', 'to_be_deposited', 'deposited', 'accepted', 'rejected')),
    access_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (access_status IN ('draft', 'ready', 'submitted', 'waiting_authorization', 'authorized', 'denied', 'expired', 'technical_error', 'manual_intervention_required')),
    import_status TEXT NOT NULL DEFAULT 'not_started'
        CHECK (import_status IN ('not_started', 'waiting_download', 'downloaded', 'partial_import', 'completed', 'failed')),
    current_ministry_status TEXT
        CHECK (current_ministry_status IN ('INVIATO', 'IN_TRANSITO', 'ACCETTATO', 'IN_VERIFICA', 'RIFIUTATO', 'ERRORE_TECNICO', 'IN_FASE_DI_VERIFICA', 'ACCOLTO', 'RIGETTATO')),
    current_ministry_status_canonical TEXT,
    local_office_rule_source TEXT,
    pec_password_received INTEGER NOT NULL DEFAULT 0 CHECK (pec_password_received IN (0,1)),
    download_available_until TEXT,
    last_download_at TEXT,
    last_sync_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
    UNIQUE (office_name, register_type, register_number, register_year, defense_counsel_cf)
);

CREATE INDEX IF NOT EXISTS idx_criminal_cases_practice_id
    ON criminal_cases(practice_id);
CREATE INDEX IF NOT EXISTS idx_criminal_cases_register
    ON criminal_cases(register_type, register_number, register_year);
CREATE INDEX IF NOT EXISTS idx_criminal_cases_access_status
    ON criminal_cases(access_status);
CREATE INDEX IF NOT EXISTS idx_criminal_cases_nomination_status
    ON criminal_cases(nomination_status);

CREATE TABLE IF NOT EXISTS criminal_case_events (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_source TEXT NOT NULL DEFAULT 'system'
        CHECK (event_source IN ('system', 'user', 'pec', 'import', 'ministry')),
    event_status TEXT,
    title TEXT NOT NULL,
    description TEXT,
    payload_json TEXT,
    created_by_user_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (criminal_case_id) REFERENCES criminal_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_criminal_case_events_case_id
    ON criminal_case_events(criminal_case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_criminal_case_events_type
    ON criminal_case_events(event_type);

CREATE TABLE IF NOT EXISTS criminal_case_documents (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL,
    document_role TEXT NOT NULL
        CHECK (document_role IN ('nomination', 'access_request', 'payment_receipt', 'legal_aid_order', 'pec_message', 'download_package', 'ministry_document', 'hearing_minutes', 'decree', 'ordinance', 'judgment', 'defense_brief', 'attachment', 'other')),
    document_category TEXT,
    title TEXT NOT NULL,
    original_filename TEXT,
    stored_filename TEXT,
    mime_type TEXT,
    extension TEXT,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    sha256 TEXT,
    source_type TEXT NOT NULL DEFAULT 'manual'
        CHECK (source_type IN ('manual', 'generated', 'pec', 'download', 'import', 'ministry')),
    signed INTEGER NOT NULL DEFAULT 0 CHECK (signed IN (0,1)),
    signature_type TEXT,
    pdfa INTEGER NOT NULL DEFAULT 0 CHECK (pdfa IN (0,1)),
    verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0,1)),
    minister_document_code TEXT,
    minister_document_date TEXT,
    imported_from_download INTEGER NOT NULL DEFAULT 0 CHECK (imported_from_download IN (0,1)),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (criminal_case_id) REFERENCES criminal_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_criminal_case_documents_case_id
    ON criminal_case_documents(criminal_case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_criminal_case_documents_role
    ON criminal_case_documents(document_role);
CREATE INDEX IF NOT EXISTS idx_criminal_case_documents_sha256
    ON criminal_case_documents(sha256);

CREATE TABLE IF NOT EXISTS criminal_access_requests (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL,
    request_type TEXT NOT NULL DEFAULT 'access_to_case_file'
        CHECK (request_type IN ('access_to_case_file', 'document_copy_request', 'supplementary_request', 'reissue_password', 'other')),
    request_reference TEXT,
    request_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (request_status IN ('draft', 'prepared', 'submitted', 'in_review', 'authorized', 'denied', 'expired', 'downloaded', 'closed', 'technical_error')),
    submitted_at TEXT,
    office_response_at TEXT,
    authorized_at TEXT,
    denied_at TEXT,
    payment_required INTEGER NOT NULL DEFAULT 0 CHECK (payment_required IN (0,1)),
    payment_amount REAL,
    payment_due_date TEXT,
    payment_done INTEGER NOT NULL DEFAULT 0 CHECK (payment_done IN (0,1)),
    payment_receipt_document_id TEXT,
    legal_aid_declared INTEGER NOT NULL DEFAULT 0 CHECK (legal_aid_declared IN (0,1)),
    legal_aid_document_id TEXT,
    pec_password_received_at TEXT,
    download_link_available INTEGER NOT NULL DEFAULT 0 CHECK (download_link_available IN (0,1)),
    download_available_until TEXT,
    downloaded_at TEXT,
    ministry_status TEXT
        CHECK (ministry_status IN ('INVIATO', 'IN_TRANSITO', 'ACCETTATO', 'IN_VERIFICA', 'RIFIUTATO', 'ERRORE_TECNICO', 'IN_FASE_DI_VERIFICA', 'ACCOLTO', 'RIGETTATO')),
    ministry_status_canonical TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (criminal_case_id) REFERENCES criminal_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (payment_receipt_document_id) REFERENCES criminal_case_documents(id) ON DELETE SET NULL,
    FOREIGN KEY (legal_aid_document_id) REFERENCES criminal_case_documents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_criminal_access_requests_case_id
    ON criminal_access_requests(criminal_case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_criminal_access_requests_status
    ON criminal_access_requests(request_status);
CREATE INDEX IF NOT EXISTS idx_criminal_access_requests_download_until
    ON criminal_access_requests(download_available_until);

CREATE TABLE IF NOT EXISTS pec_messages (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT,
    mailbox TEXT NOT NULL,
    sender TEXT,
    recipient TEXT,
    subject TEXT NOT NULL,
    message_date TEXT,
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_id_header TEXT,
    thread_reference TEXT,
    body_text TEXT,
    raw_eml_path TEXT,
    matched INTEGER NOT NULL DEFAULT 0 CHECK (matched IN (0,1)),
    matched_reason TEXT,
    contains_password INTEGER NOT NULL DEFAULT 0 CHECK (contains_password IN (0,1)),
    extracted_password TEXT,
    contains_download_notice INTEGER NOT NULL DEFAULT 0 CHECK (contains_download_notice IN (0,1)),
    processed INTEGER NOT NULL DEFAULT 0 CHECK (processed IN (0,1)),
    processed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (criminal_case_id) REFERENCES criminal_cases(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pec_messages_case_id
    ON pec_messages(criminal_case_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_pec_messages_subject
    ON pec_messages(subject);
CREATE INDEX IF NOT EXISTS idx_pec_messages_message_id_header
    ON pec_messages(message_id_header);

CREATE TABLE IF NOT EXISTS criminal_workflow_tasks (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL,
    task_type TEXT NOT NULL
        CHECK (task_type IN ('check_nomination', 'prepare_access_request', 'deposit_request', 'wait_office_response', 'check_pec', 'download_case_file', 'import_documents', 'verify_documents', 'manual_review', 'other')),
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'done', 'cancelled')),
    assigned_user_id TEXT,
    due_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (criminal_case_id) REFERENCES criminal_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_criminal_workflow_tasks_case_id
    ON criminal_workflow_tasks(criminal_case_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_criminal_workflow_tasks_status
    ON criminal_workflow_tasks(status);

CREATE TABLE IF NOT EXISTS criminal_access_request_documents (
    id TEXT PRIMARY KEY,
    access_request_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'attachment'
        CHECK (relation_type IN ('attachment', 'generated_request', 'receipt', 'result')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (access_request_id) REFERENCES criminal_access_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES criminal_case_documents(id) ON DELETE CASCADE,
    UNIQUE (access_request_id, document_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_criminal_access_request_documents_req
    ON criminal_access_request_documents(access_request_id);
CREATE INDEX IF NOT EXISTS idx_criminal_access_request_documents_doc
    ON criminal_access_request_documents(document_id);

CREATE TRIGGER IF NOT EXISTS trg_criminal_cases_updated_at
AFTER UPDATE ON criminal_cases
FOR EACH ROW
BEGIN
    UPDATE criminal_cases
    SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_criminal_access_requests_updated_at
AFTER UPDATE ON criminal_access_requests
FOR EACH ROW
BEGIN
    UPDATE criminal_access_requests
    SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_criminal_workflow_tasks_updated_at
AFTER UPDATE ON criminal_workflow_tasks
FOR EACH ROW
BEGIN
    UPDATE criminal_workflow_tasks
    SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;

CREATE VIEW IF NOT EXISTS v_criminal_case_overview AS
SELECT
    cc.id,
    cc.practice_id,
    cc.office_name,
    cc.register_type,
    cc.register_number,
    cc.register_year,
    cc.assisted_party_name,
    cc.defense_counsel_name,
    cc.nomination_status,
    cc.access_status,
    cc.import_status,
    cc.current_ministry_status,
    cc.pec_password_received,
    cc.download_available_until,
    (
        SELECT COUNT(*)
        FROM criminal_case_documents d
        WHERE d.criminal_case_id = cc.id
    ) AS documents_count,
    (
        SELECT COUNT(*)
        FROM criminal_workflow_tasks t
        WHERE t.criminal_case_id = cc.id
          AND t.status IN ('open', 'in_progress')
    ) AS open_tasks_count,
    cc.created_at,
    cc.updated_at
FROM criminal_cases cc;
"""


def ensure_pdp_penale_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL_PDP_PENALE)
    _ensure_column(conn, "criminal_cases", "current_ministry_status_canonical", "TEXT")
    _ensure_column(conn, "criminal_cases", "local_office_rule_source", "TEXT")
    _ensure_column(conn, "criminal_access_requests", "ministry_status_canonical", "TEXT")


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {str(row[1]) for row in rows}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _now_sql() -> str:
    return "datetime('now')"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _normalize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _normalize_text(*parts: Any) -> str:
    return " ".join(str(part or "").strip() for part in parts if str(part or "").strip()).lower()


def pdp_penale_classifica_documento(
    nome_file: str,
    titolo: str = "",
    note: str = "",
) -> dict[str, str]:
    testo = _normalize_text(nome_file, titolo, note)
    ruolo = "other"
    categoria = ""
    if "nomina" in testo or "procura" in testo:
        ruolo = "nomination"
        categoria = "titolo_accesso"
    elif "accesso" in testo or "istanza" in testo or "richiesta" in testo:
        ruolo = "access_request"
        categoria = "istanza_accesso"
    elif "pagopa" in testo or "contribut" in testo or "ricevuta" in testo:
        ruolo = "payment_receipt"
        categoria = "pagamento"
    elif "gratuito patrocinio" in testo or "patrocinio" in testo:
        ruolo = "legal_aid_order"
        categoria = "gratuito_patrocinio"
    elif "verbale" in testo or "udienza" in testo:
        ruolo = "hearing_minutes"
        categoria = "udienza"
    elif "ordinanza" in testo:
        ruolo = "ordinance"
        categoria = "provvedimento"
    elif "sentenza" in testo:
        ruolo = "judgment"
        categoria = "provvedimento"
    elif "decreto" in testo:
        ruolo = "decree"
        categoria = "provvedimento"
    elif "memoria" in testo or "difens" in testo or "istanza difensiva" in testo:
        ruolo = "defense_brief"
        categoria = "atto_difensivo"
    elif "pec" in testo or nome_file.lower().endswith(".eml"):
        ruolo = "pec_message"
        categoria = "comunicazione"
    elif nome_file.lower().endswith(".zip"):
        ruolo = "download_package"
        categoria = "pacchetto_download"
    elif "allegat" in testo:
        ruolo = "attachment"
        categoria = "allegato"
    elif "fascicolo" in testo or "minister" in testo:
        ruolo = "ministry_document"
        categoria = "fascicolo_ministeriale"
    return {
        "document_role": ruolo,
        "document_category": categoria,
    }


def pdp_penale_estrai_password(testo: str, subject: str = "") -> str:
    merged = " ".join(part for part in [subject, testo] if str(part or "").strip())
    patterns = (
        r"(?:password(?:\s+di\s+accesso)?|pwd|codice\s+di\s+accesso)\s*(?:[:=\-])\s*([A-Za-z0-9][A-Za-z0-9._@#/\-]{3,})",
        r"(?:password\s+di\s+accesso|codice\s+di\s+accesso)\s+([A-Za-z0-9][A-Za-z0-9._@#/\-]{3,})",
    )
    for pattern in patterns:
        match = re.search(pattern, merged, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".,;:)")
    return ""


def pdp_penale_estrai_scadenza_download(testo: str, reference_iso: str = "") -> str:
    source = " ".join(str(testo or "").split())
    if not source:
        return ""

    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}:\d{2}))?\b", source)
    if iso_match:
        giorno = iso_match.group(1)
        ora = iso_match.group(2) or "23:59"
        return f"{giorno}T{ora}"

    ita_match = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})(?:\s*(?:alle|ore)?\s*(\d{2}:\d{2}))?\b", source, re.IGNORECASE)
    if ita_match:
        giorno = int(ita_match.group(1))
        mese = int(ita_match.group(2))
        anno = int(ita_match.group(3))
        ora = ita_match.group(4) or "23:59"
        return f"{anno:04d}-{mese:02d}-{giorno:02d}T{ora}"

    giorni_match = re.search(r"\b(?:entro|disponibil[ei]\s+per)\s+(\d+)\s+giorn", source, re.IGNORECASE)
    if giorni_match and reference_iso:
        try:
            base = datetime.fromisoformat(str(reference_iso).replace("Z", "+00:00"))
            limite = base + timedelta(days=int(giorni_match.group(1)))
            return limite.replace(second=0, microsecond=0).isoformat(timespec="minutes")
        except Exception:
            return ""
    return ""


class PDPPenaleWorkflowRepository:
    """CRUD principale del modulo PDP Penale su SQLite."""

    _CASE_MUTABLE_FIELDS = {
        "practice_id",
        "minister_case_ref",
        "office_name",
        "office_type",
        "district",
        "register_type",
        "register_number",
        "register_year",
        "proceeding_type",
        "prosecutor_name",
        "judge_name",
        "chamber_section",
        "assisted_party_name",
        "assisted_party_cf",
        "defense_counsel_name",
        "defense_counsel_cf",
        "nomination_status",
        "access_status",
        "import_status",
        "current_ministry_status",
        "current_ministry_status_canonical",
        "local_office_rule_source",
        "pec_password_received",
        "download_available_until",
        "last_download_at",
        "last_sync_at",
        "notes",
        "archived",
    }
    _ACCESS_REQUEST_MUTABLE_FIELDS = {
        "request_type",
        "request_reference",
        "request_status",
        "submitted_at",
        "office_response_at",
        "authorized_at",
        "denied_at",
        "payment_required",
        "payment_amount",
        "payment_due_date",
        "payment_done",
        "payment_receipt_document_id",
        "legal_aid_declared",
        "legal_aid_document_id",
        "pec_password_received_at",
        "download_link_available",
        "download_available_until",
        "downloaded_at",
        "ministry_status",
        "ministry_status_canonical",
        "notes",
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
        ensure_pdp_penale_schema(self.conn)

    def close(self) -> None:
        if self._owns_connection:
            self.conn.close()

    def _insert(self, table: str, data: Mapping[str, Any]) -> dict[str, Any]:
        columns = list(data.keys())
        placeholders = ", ".join("?" for _ in columns)
        query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        self.conn.execute(query, tuple(_normalize_value(data[col]) for col in columns))
        self.conn.commit()
        pk = str(data["id"])
        return self._get_by_id(table, pk)

    def _get_by_id(self, table: str, pk: str) -> dict[str, Any]:
        row = self.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (pk,)).fetchone()
        result = _row_to_dict(row)
        if result is None:
            raise KeyError(f"Record non trovato in {table}: {pk}")
        return result

    def _update(self, table: str, pk: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        if not changes:
            return self._get_by_id(table, pk)
        assignments = ", ".join(f"{col} = ?" for col in changes.keys())
        params = tuple(_normalize_value(value) for value in changes.values()) + (pk,)
        self.conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", params)
        self.conn.commit()
        return self._get_by_id(table, pk)

    def create_case(
        self,
        *,
        practice_id: str,
        office_name: str,
        register_number: str,
        register_year: int,
        assisted_party_name: str,
        defense_counsel_name: str,
        defense_counsel_cf: str,
        **extra: Any,
    ) -> dict[str, Any]:
        data = {
            "id": _new_id("ccase"),
            "practice_id": practice_id,
            "office_name": office_name,
            "register_number": register_number,
            "register_year": int(register_year),
            "assisted_party_name": assisted_party_name,
            "defense_counsel_name": defense_counsel_name,
            "defense_counsel_cf": defense_counsel_cf,
        }
        for key, value in extra.items():
            if key in self._CASE_MUTABLE_FIELDS:
                data[key] = value
        return self._insert("criminal_cases", data)

    def get_case(self, case_id: str) -> dict[str, Any]:
        return self._get_by_id("criminal_cases", case_id)

    def update_case(self, case_id: str, **changes: Any) -> dict[str, Any]:
        filtered = {
            key: value
            for key, value in changes.items()
            if key in self._CASE_MUTABLE_FIELDS and key != "id"
        }
        return self._update("criminal_cases", case_id, filtered)

    def list_cases_for_practice(self, practice_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM criminal_cases WHERE practice_id = ? ORDER BY updated_at DESC, created_at DESC",
            (practice_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def list_overview_for_practice(self, practice_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM v_criminal_case_overview WHERE practice_id = ? ORDER BY updated_at DESC, created_at DESC",
            (practice_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def add_event(
        self,
        criminal_case_id: str,
        *,
        event_type: str,
        title: str,
        event_source: str = "system",
        event_status: str | None = None,
        description: str | None = None,
        payload_json: Mapping[str, Any] | list[Any] | str | None = None,
        created_by_user_id: str | None = None,
    ) -> dict[str, Any]:
        return self._insert(
            "criminal_case_events",
            {
                "id": _new_id("cevt"),
                "criminal_case_id": criminal_case_id,
                "event_type": event_type,
                "event_source": event_source,
                "event_status": event_status,
                "title": title,
                "description": description,
                "payload_json": payload_json,
                "created_by_user_id": created_by_user_id,
            },
        )

    def list_case_events(self, criminal_case_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM criminal_case_events WHERE criminal_case_id = ? ORDER BY created_at DESC",
            (criminal_case_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def add_document(
        self,
        criminal_case_id: str,
        *,
        document_role: str,
        title: str,
        file_path: str,
        **extra: Any,
    ) -> dict[str, Any]:
        data = {
            "id": _new_id("cdoc"),
            "criminal_case_id": criminal_case_id,
            "document_role": document_role,
            "title": title,
            "file_path": file_path,
        }
        for key, value in extra.items():
            data[key] = value
        return self._insert("criminal_case_documents", data)

    def list_case_documents(self, criminal_case_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM criminal_case_documents WHERE criminal_case_id = ? ORDER BY created_at DESC",
            (criminal_case_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def create_access_request(self, criminal_case_id: str, **extra: Any) -> dict[str, Any]:
        data = {"id": _new_id("careq"), "criminal_case_id": criminal_case_id}
        data.update(extra)
        return self._insert("criminal_access_requests", data)

    def list_access_requests(self, criminal_case_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM criminal_access_requests WHERE criminal_case_id = ? ORDER BY created_at DESC",
            (criminal_case_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def update_access_request(self, access_request_id: str, **changes: Any) -> dict[str, Any]:
        filtered = {
            key: value
            for key, value in changes.items()
            if key in self._ACCESS_REQUEST_MUTABLE_FIELDS and key != "id"
        }
        return self._update("criminal_access_requests", access_request_id, filtered)

    def link_document_to_access_request(
        self,
        access_request_id: str,
        document_id: str,
        relation_type: str = "attachment",
    ) -> dict[str, Any]:
        return self._insert(
            "criminal_access_request_documents",
            {
                "id": _new_id("cardoc"),
                "access_request_id": access_request_id,
                "document_id": document_id,
                "relation_type": relation_type,
            },
        )

    def register_pec_message(self, *, mailbox: str, subject: str, **extra: Any) -> dict[str, Any]:
        data = {
            "id": _new_id("pec"),
            "mailbox": mailbox,
            "subject": subject,
        }
        data.update(extra)
        record = self._insert("pec_messages", data)
        criminal_case_id = str(record.get("criminal_case_id") or "").strip()
        contains_password = bool(int(record.get("contains_password") or 0))
        if not contains_password and str(record.get("extracted_password") or "").strip():
            record = self._update(
                "pec_messages",
                str(record["id"]),
                {"contains_password": 1},
            )
            contains_password = True
        if criminal_case_id and contains_password:
            self.update_case(criminal_case_id, pec_password_received=1)
        return record

    def list_pec_messages(self, criminal_case_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM pec_messages WHERE criminal_case_id = ? ORDER BY received_at DESC, created_at DESC",
            (criminal_case_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def create_task(
        self,
        criminal_case_id: str,
        *,
        task_type: str,
        title: str,
        **extra: Any,
    ) -> dict[str, Any]:
        data = {
            "id": _new_id("ctask"),
            "criminal_case_id": criminal_case_id,
            "task_type": task_type,
            "title": title,
        }
        data.update(extra)
        return self._insert("criminal_workflow_tasks", data)

    def list_tasks(self, criminal_case_id: str, only_open: bool = False) -> list[dict[str, Any]]:
        if only_open:
            rows = self.conn.execute(
                """
                SELECT * FROM criminal_workflow_tasks
                WHERE criminal_case_id = ? AND status IN ('open', 'in_progress')
                ORDER BY due_at IS NULL, due_at, created_at DESC
                """,
                (criminal_case_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM criminal_workflow_tasks WHERE criminal_case_id = ? ORDER BY created_at DESC",
                (criminal_case_id,),
            ).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]

    def close_task(self, task_id: str, *, completion_note: str | None = None) -> dict[str, Any]:
        task = self._get_by_id("criminal_workflow_tasks", task_id)
        description = str(task.get("description") or "")
        if completion_note:
            description = "\n".join(part for part in [description.strip(), completion_note.strip()] if part).strip()
        return self._update(
            "criminal_workflow_tasks",
            task_id,
            {
                "status": "done",
                "completed_at": self.conn.execute(f"SELECT {_now_sql()}").fetchone()[0],
                "description": description or None,
            },
        )

    def get_access_request(self, access_request_id: str) -> dict[str, Any]:
        return self._get_by_id("criminal_access_requests", access_request_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._get_by_id("criminal_workflow_tasks", task_id)

    def get_document(self, document_id: str) -> dict[str, Any]:
        return self._get_by_id("criminal_case_documents", document_id)

    def get_event(self, event_id: str) -> dict[str, Any]:
        return self._get_by_id("criminal_case_events", event_id)

    def get_pec_message(self, message_id: str) -> dict[str, Any]:
        return self._get_by_id("pec_messages", message_id)

