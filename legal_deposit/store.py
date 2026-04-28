from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_SQL_LEGAL_DEPOSIT = """
CREATE TABLE IF NOT EXISTS deposit_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    confirmed_at TEXT,
    signed_at TEXT,
    sent_at TEXT,
    completed_at TEXT,
    error_code TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_deposit_jobs_tenant_fascicolo ON deposit_jobs(tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_deposit_jobs_status ON deposit_jobs(status);

CREATE TABLE IF NOT EXISTS deposit_documents (
    id TEXT PRIMARY KEY,
    deposit_job_id TEXT NOT NULL,
    document_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'attachment',
    filename TEXT NOT NULL DEFAULT '',
    mime_type TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    validation_status TEXT NOT NULL DEFAULT '',
    validation_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_deposit_documents_job ON deposit_documents(deposit_job_id);

CREATE TABLE IF NOT EXISTS deposit_packages (
    id TEXT PRIMARY KEY,
    deposit_job_id TEXT NOT NULL,
    package_path TEXT NOT NULL DEFAULT '',
    manifest_path TEXT NOT NULL DEFAULT '',
    xml_path TEXT NOT NULL DEFAULT '',
    zip_path TEXT NOT NULL DEFAULT '',
    p7m_path TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_deposit_packages_job ON deposit_packages(deposit_job_id);

CREATE TABLE IF NOT EXISTS deposit_receipts (
    id TEXT PRIMARY KEY,
    deposit_job_id TEXT NOT NULL,
    receipt_type TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    pec_from TEXT NOT NULL DEFAULT '',
    pec_to TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    eml_path TEXT NOT NULL DEFAULT '',
    xml_path TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT '',
    parsed_json TEXT NOT NULL DEFAULT '{}',
    sha256 TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_deposit_receipts_job ON deposit_receipts(deposit_job_id);

CREATE TABLE IF NOT EXISTS deposit_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT '',
    deposit_job_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    status_before TEXT NOT NULL DEFAULT '',
    status_after TEXT NOT NULL DEFAULT '',
    detail_json TEXT NOT NULL DEFAULT '{}',
    ip_address TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deposit_alerts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    deposit_job_id TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'INFO',
    title TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    dedupe_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_deposit_alerts_dedupe
    ON deposit_alerts(tenant_id, dedupe_key)
    WHERE dedupe_key <> '';
CREATE INDEX IF NOT EXISTS idx_deposit_alerts_status ON deposit_alerts(tenant_id, status);
"""


class DepositRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL_LEGAL_DEPOSIT)

    def save_job(
        self,
        *,
        job_id: str,
        tenant_id: str,
        fascicolo_id: str,
        channel: str,
        status: str,
        created_by: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO deposit_jobs
                (id, tenant_id, fascicolo_id, channel, status, created_by, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (job_id, tenant_id, fascicolo_id, channel, status, created_by, json.dumps(metadata, ensure_ascii=False)),
            )
            row = conn.execute("SELECT * FROM deposit_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row or {})

    def save_package(
        self,
        *,
        package_id: str,
        job_id: str,
        package_path: str = "",
        manifest_path: str = "",
        xml_path: str = "",
        zip_path: str = "",
        sha256: str = "",
        size_bytes: int = 0,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO deposit_packages
                (id, deposit_job_id, package_path, manifest_path, xml_path, zip_path, sha256, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (package_id, job_id, package_path, manifest_path, xml_path, zip_path, sha256, int(size_bytes or 0)),
            )

    def add_audit(
        self,
        *,
        tenant_id: str,
        job_id: str,
        user_id: str,
        action: str,
        before: str,
        after: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO deposit_audit_logs
                (tenant_id, deposit_job_id, user_id, action, status_before, status_after, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, job_id, user_id, action, before, after, json.dumps(detail or {}, ensure_ascii=False)),
            )
