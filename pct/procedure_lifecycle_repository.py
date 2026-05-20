"""Repository SQLite per inventario XSD, schede, workflow e audit procedurale."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator

from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig, SQLiteCoverageRepository


EXTENDED_SCHEMA_SQL = Path(__file__).with_name("sql") / "20260520_xsd_procedure_lifecycle_knowledge.sql"
LEGACY_EXTENDED_SCHEMA_SQL = Path(__file__).with_name("sql") / "20260520_procedure_lifecycle_knowledge_pipeline.sql"

TENANT_AWARE_TABLES: tuple[str, ...] = (
    "legal_ministerial_xsd_objects",
    "legal_procedure_xsd_map",
    "legal_procedure_source_evidence",
    "procedure_knowledge_cards",
    "procedure_lifecycle_templates",
    "procedure_lifecycle_steps",
    "fascicolo_workflow_instances",
    "fascicolo_workflow_events",
    "digital_signature_events",
    "telematic_deposit_packages",
    "telematic_deposit_receipts",
    "post_acceptance_obligations",
    "notification_events",
    "evidence_documents",
    "procedure_audit_log",
)

_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_CF_RE = re.compile(r"\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b", re.IGNORECASE)
_IBAN_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+39\s*)?(?:\d[\s./-]?){8,14}\d(?!\w)")
_PATH_RE = re.compile(r"(?i)([a-z]:\\|/data/|/home/|/var/|\\\\)[^\s\"']+")
_SECRET_KEY_PARTS = ("pin", "password", "token", "cookie", "secret", "credential", "otp")
_PATH_KEY_PARTS = ("path", "storage_path", "filesystem", "directory")
_PII_KEY_PARTS = ("tax_code", "codice_fiscale", "iban", "email", "phone", "telefono", "recipient_address")
_OFFICIAL_DEPOSIT_RECEIPTS_BY_STATUS = {
    "OFFICE_ACCEPTED": {"ACCETTAZIONE_DEPOSITO"},
    "OFFICE_REJECTED": {"RIFIUTO_DEPOSITO", "ERRORE_TECNICO"},
}
_NOTIFICATION_PROOF_STATUSES = {"PROOF_ACQUIRED", "PROOF_DEPOSIT_REQUIRED", "PROOF_DEPOSITED"}
_SIGNATURE_STATUSES = {
    "NOT_REQUIRED",
    "REQUIRED_PENDING",
    "SIGNED_UNVERIFIED",
    "VERIFIED",
    "INVALID",
    "MISMATCH_SIGNER",
    "EXPIRED_CERTIFICATE",
    "ERROR",
}
_DEPOSIT_STATUSES = {
    "DRAFT",
    "READY",
    "SENT",
    "PEC_ACCEPTED",
    "PEC_DELIVERED",
    "CONTROLS_RECEIVED",
    "OFFICE_ACCEPTED",
    "OFFICE_REJECTED",
    "TECHNICAL_ERROR",
    "CANCELLED",
}
_NOTIFICATION_STATUSES = {
    "DRAFT",
    "READY",
    "SENT",
    "DELIVERED",
    "FAILED",
    "PROOF_ACQUIRED",
    "PROOF_DEPOSIT_REQUIRED",
    "PROOF_DEPOSITED",
}
_OBLIGATION_STATUSES = {"PENDING", "COMPLETED", "CANCELLED"}
_PROTECTED_SIGNATURE_STATUSES = {"VERIFIED"}
_PROTECTED_WORKFLOW_STATES = {
    "FIRMATO",
    "DEPOSITO_ACCETTATO",
    "NOTIFICA_EFFETTUATA",
    "PROVA_NOTIFICA_ACQUISITA",
    "CHIUSA",
}
_VALIDATED_SIGNATURE_SOURCE = "signature_validation"
_VALIDATED_DEPOSIT_SOURCE = "deposit_receipt_validation"
_VALIDATED_NOTIFICATION_SOURCE = "notification_proof_validation"
_VALIDATED_WORKFLOW_SOURCE = "workflow_transition_validation"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        if isinstance(default, list):
            return []
        if isinstance(default, dict):
            return {}
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        if isinstance(default, list):
            return []
        if isinstance(default, dict):
            return {}
        return default


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _stable_payload(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_event_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_payload(payload).encode("utf-8")).hexdigest()


def _mask_text(value: str) -> str:
    masked = _EMAIL_RE.sub("[email-masked]", value)
    masked = _CF_RE.sub("[tax-code-masked]", masked)
    masked = _IBAN_RE.sub("[iban-masked]", masked)
    masked = _PHONE_RE.sub("[phone-masked]", masked)
    masked = _PATH_RE.sub("[path-masked]", masked)
    return masked


def sanitize_audit_payload(value: Any, parent_key: str = "") -> Any:
    """Rimuove dati sensibili prima di scrivere audit persistente."""

    key = str(parent_key or "").lower()
    if any(part in key for part in _SECRET_KEY_PARTS):
        return "[secret-redacted]"
    if any(part in key for part in _PATH_KEY_PARTS):
        return "[path-redacted]" if value not in (None, "") else value
    if isinstance(value, dict):
        return {item_key: sanitize_audit_payload(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_audit_payload(item, parent_key) for item in value]
    if isinstance(value, tuple):
        return [sanitize_audit_payload(item, parent_key) for item in value]
    if isinstance(value, str):
        if any(part in key for part in _PII_KEY_PARTS):
            return _mask_text(value)
        return _mask_text(value)
    return value


def diff_dict(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    previous = before or {}
    current = after or {}
    keys = sorted(set(previous) | set(current))
    changed = {
        key: {"before": previous.get(key), "after": current.get(key)}
        for key in keys
        if previous.get(key) != current.get(key)
    }
    return {"changed": changed, "changed_fields": sorted(changed)}


def _assert_allowed_status(value: Any, allowed: set[str], field_name: str) -> None:
    status = str(value or "")
    if status not in allowed:
        raise ValueError(f"{field_name} non ammesso: {status}")


def _assert_notification_proof_evidence(conn: sqlite3.Connection, fascicolo_id: str, proof_bundle_id: Any) -> None:
    proof_id = str(proof_bundle_id or "").strip()
    if not proof_id:
        raise ValueError("Gli stati prova notifica richiedono evidence_documents collegati.")
    row = conn.execute(
        """
        SELECT id FROM evidence_documents
        WHERE fascicolo_id = ?
          AND (document_id = ? OR CAST(id AS TEXT) = ?)
        LIMIT 1
        """,
        (fascicolo_id, proof_id, proof_id),
    ).fetchone()
    if row is None:
        raise ValueError("Gli stati prova notifica richiedono evidence_documents collegati.")


def _insert_transition_guard(conn: sqlite3.Connection, entity_type: str, entity_id: Any, target_state: Any) -> None:
    conn.execute(
        """
        INSERT INTO procedure_state_transition_guard (entity_type, entity_id, target_state)
        VALUES (?, ?, ?)
        """,
        (entity_type, str(entity_id), str(target_state)),
    )


@dataclass(frozen=True)
class ProcedureLifecycleRepository:
    """Accesso persistente alla pipeline procedurale estesa."""

    config: CoverageSqliteConfig

    @property
    def db_path(self) -> Path:
        return Path(str(self.config.path or "")).resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.config.configured:
            raise RuntimeError("Percorso SQLite coverage non configurato.")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            conn.close()

    def ensure_extended_schema(self) -> None:
        SQLiteCoverageRepository(self.config).ensure_schema()
        with self.connect() as conn:
            schema_path = EXTENDED_SCHEMA_SQL if EXTENDED_SCHEMA_SQL.exists() else LEGACY_EXTENDED_SCHEMA_SQL
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            self._ensure_tenant_columns(conn)
            conn.commit()

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}

    def _ensure_tenant_columns(self, conn: sqlite3.Connection) -> None:
        for table_name in TENANT_AWARE_TABLES:
            if not self._fetch_one(
                conn,
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ):
                continue
            columns = self._table_columns(conn, table_name)
            if "tenant_id" not in columns:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN tenant_id TEXT")
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_tenant_id ON {table_name} (tenant_id)")

    def _fetch_one(self, conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        return row_to_dict(conn.execute(sql, params).fetchone())

    def _fetch_all(self, conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [row_to_dict(row) or {} for row in conn.execute(sql, params).fetchall()]

    def table_exists(self, table_name: str) -> bool:
        with self.connect() as conn:
            row = self._fetch_one(
                conn,
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            )
        return bool(row)

    def audit_log(
        self,
        *,
        entity_type: str,
        entity_id: str | int | None,
        action: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        diff: dict[str, Any] | None = None,
        actor: str = "",
        source: str = "procedure_lifecycle",
        notes: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> str:
        safe_before = sanitize_audit_payload(before or {})
        safe_after = sanitize_audit_payload(after or {})
        safe_diff = sanitize_audit_payload(diff if diff is not None else diff_dict(before, after))
        tenant_id = str((after or {}).get("tenant_id") or (before or {}).get("tenant_id") or "")
        hash_payload = {
            "entity_type": entity_type,
            "entity_id": str(entity_id or ""),
            "action": action,
            "actor": actor,
            "source": source,
            "before": safe_before,
            "after": safe_after,
            "diff": safe_diff,
            "notes": notes,
            "tenant_id": tenant_id,
        }
        event_hash = stable_event_hash(hash_payload)
        params = (
            tenant_id or None,
            entity_type,
            str(entity_id or ""),
            action,
            actor or None,
            source or None,
            json_dumps(safe_before),
            json_dumps(safe_after),
            json_dumps(safe_diff),
            event_hash,
            notes or None,
        )
        sql = """
            INSERT INTO procedure_audit_log (
                tenant_id, entity_type, entity_id, action, actor, source,
                before_json, after_json, diff_json, event_hash, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if conn is not None:
            conn.execute(sql, params)
            return event_hash
        with self.connect() as own_conn:
            own_conn.execute(sql, params)
            own_conn.commit()
        return event_hash

    def list_audit_log(self, entity_type: str = "", entity_id: str | int | None = None) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if entity_type:
            where.append("entity_type = ?")
            params.append(entity_type)
        if entity_id is not None:
            where.append("entity_id = ?")
            params.append(str(entity_id))
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                f"SELECT * FROM procedure_audit_log {clause} ORDER BY id ASC",
                tuple(params),
            )
        for row in rows:
            row["before_json"] = json_loads(row.get("before_json"), {})
            row["after_json"] = json_loads(row.get("after_json"), {})
            row["diff_json"] = json_loads(row.get("diff_json"), {})
        return rows

    def upsert_xsd_object(self, row: dict[str, Any], *, actor: str = "", source: str = "xsd_import") -> str:
        self.ensure_extended_schema()
        xsd_code = str(row["xsd_code"])
        with self.connect() as conn:
            before = self._fetch_one(conn, "SELECT * FROM legal_ministerial_xsd_objects WHERE xsd_code = ?", (xsd_code,))
            conn.execute(
                """
                INSERT INTO legal_ministerial_xsd_objects (
                    tenant_id, xsd_code, xsd_label, xsd_area_code, xsd_area_label, xsd_family_code,
                    xsd_family_label, source_version, source_name, source_url, source_file,
                    active, last_verified_at, import_hash, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(xsd_code) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    xsd_label = excluded.xsd_label,
                    xsd_area_code = excluded.xsd_area_code,
                    xsd_area_label = excluded.xsd_area_label,
                    xsd_family_code = excluded.xsd_family_code,
                    xsd_family_label = excluded.xsd_family_label,
                    source_version = excluded.source_version,
                    source_name = excluded.source_name,
                    source_url = excluded.source_url,
                    source_file = excluded.source_file,
                    active = excluded.active,
                    last_verified_at = excluded.last_verified_at,
                    import_hash = excluded.import_hash,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    row.get("tenant_id"),
                    xsd_code,
                    row["xsd_label"],
                    row.get("xsd_area_code"),
                    row.get("xsd_area_label"),
                    row.get("xsd_family_code"),
                    row.get("xsd_family_label"),
                    row["source_version"],
                    row["source_name"],
                    row.get("source_url"),
                    row.get("source_file"),
                    int(row.get("active", 1)),
                    row.get("last_verified_at"),
                    row.get("import_hash"),
                    row.get("notes"),
                ),
            )
            after = self._fetch_one(conn, "SELECT * FROM legal_ministerial_xsd_objects WHERE xsd_code = ?", (xsd_code,))
            action = "xsd_import_update" if before else "xsd_import_create"
            if before != after:
                self.audit_log(
                    entity_type="legal_ministerial_xsd_objects",
                    entity_id=xsd_code,
                    action=action,
                    before=before,
                    after=after,
                    actor=actor,
                    source=source,
                    conn=conn,
                )
            conn.commit()
        return action

    def get_xsd_object(self, xsd_code: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            return self._fetch_one(conn, "SELECT * FROM legal_ministerial_xsd_objects WHERE xsd_code = ?", (xsd_code,))

    def list_xsd_objects(self, *, active_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE active = 1" if active_only else ""
        with self.connect() as conn:
            return self._fetch_all(conn, f"SELECT * FROM legal_ministerial_xsd_objects {where} ORDER BY xsd_code")

    def upsert_xsd_mapping(self, row: dict[str, Any], *, actor: str = "", source: str = "xsd_mapper") -> int:
        self.ensure_extended_schema()
        key = (row["xsd_code"], row["procedure_code"], row.get("channel_code"))
        with self.connect() as conn:
            before = self._fetch_one(
                conn,
                """
                SELECT * FROM legal_procedure_xsd_map
                WHERE xsd_code = ? AND procedure_code = ? AND COALESCE(channel_code, '') = COALESCE(?, '')
                """,
                key,
            )
            conn.execute(
                """
                INSERT INTO legal_procedure_xsd_map (
                    tenant_id, xsd_code, procedure_code, channel_code, registry_code, workflow_code,
                    is_default, confidence_score, mapping_source, review_status,
                    reviewer, reviewed_at, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(xsd_code, procedure_code, channel_code) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    registry_code = excluded.registry_code,
                    workflow_code = excluded.workflow_code,
                    is_default = excluded.is_default,
                    confidence_score = excluded.confidence_score,
                    mapping_source = excluded.mapping_source,
                    review_status = excluded.review_status,
                    reviewer = excluded.reviewer,
                    reviewed_at = excluded.reviewed_at,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    row.get("tenant_id"),
                    row["xsd_code"],
                    row["procedure_code"],
                    row.get("channel_code"),
                    row.get("registry_code"),
                    row.get("workflow_code"),
                    int(row.get("is_default", 0)),
                    int(row.get("confidence_score", 50)),
                    row.get("mapping_source", "RULE"),
                    row.get("review_status", "needs_review"),
                    row.get("reviewer"),
                    row.get("reviewed_at"),
                    row.get("notes"),
                ),
            )
            after = self._fetch_one(
                conn,
                """
                SELECT * FROM legal_procedure_xsd_map
                WHERE xsd_code = ? AND procedure_code = ? AND COALESCE(channel_code, '') = COALESCE(?, '')
                """,
                key,
            )
            if before != after:
                self.audit_log(
                    entity_type="legal_procedure_xsd_map",
                    entity_id=(after or {}).get("id"),
                    action="xsd_mapping_update" if before else "xsd_mapping_create",
                    before=before,
                    after=after,
                    actor=actor,
                    source=source,
                    conn=conn,
                )
            conn.commit()
        return int((after or {}).get("id") or 0)

    def list_xsd_mappings(self, xsd_code: str = "", procedure_code: str = "") -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if xsd_code:
            clauses.append("xsd_code = ?")
            params.append(xsd_code)
        if procedure_code:
            clauses.append("procedure_code = ?")
            params.append(procedure_code)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            return self._fetch_all(conn, f"SELECT * FROM legal_procedure_xsd_map {where} ORDER BY id", tuple(params))

    def add_source_evidence(self, row: dict[str, Any], *, actor: str = "", source: str = "knowledge_pipeline") -> int:
        self.ensure_extended_schema()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO legal_procedure_source_evidence (
                    tenant_id, procedure_code, xsd_code, source_id, source_type, source_url,
                    source_title, source_author, source_date, last_checked_at,
                    evidence_kind, extracted_principle, original_quote_short,
                    copyright_policy, reliability_score, review_status, reviewer,
                    reviewed_at, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    row.get("tenant_id"),
                    row["procedure_code"],
                    row.get("xsd_code"),
                    row.get("source_id"),
                    row["source_type"],
                    row.get("source_url"),
                    row.get("source_title"),
                    row.get("source_author"),
                    row.get("source_date"),
                    row.get("last_checked_at"),
                    row["evidence_kind"],
                    row.get("extracted_principle"),
                    row.get("original_quote_short"),
                    row.get("copyright_policy", "summary_only"),
                    int(row.get("reliability_score", 50)),
                    row.get("review_status", "needs_review"),
                    row.get("reviewer"),
                    row.get("reviewed_at"),
                    row.get("notes"),
                ),
            )
            evidence_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM legal_procedure_source_evidence WHERE id = ?", (evidence_id,))
            self.audit_log(
                entity_type="legal_procedure_source_evidence",
                entity_id=evidence_id,
                action="source_evidence_add",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return evidence_id

    def list_source_evidence(self, procedure_code: str, xsd_code: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [procedure_code]
        where = "procedure_code = ?"
        if xsd_code is not None:
            where += " AND COALESCE(xsd_code, '') = COALESCE(?, '')"
            params.append(xsd_code)
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                f"SELECT * FROM legal_procedure_source_evidence WHERE {where} ORDER BY id",
                tuple(params),
            )

    def create_knowledge_card(self, row: dict[str, Any], *, actor: str = "", source: str = "knowledge_pipeline") -> int:
        self.ensure_extended_schema()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO procedure_knowledge_cards (
                    tenant_id, procedure_code, xsd_code, title, version, status, risk_level,
                    requires_human_review, generated_from_sources_json, card_json,
                    summary_original, validation_report_json, reviewer, reviewed_at,
                    review_reason, published_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    row.get("tenant_id"),
                    row["procedure_code"],
                    row.get("xsd_code"),
                    row["title"],
                    row.get("version", "v1"),
                    row.get("status", "draft"),
                    row.get("risk_level", "MEDIUM"),
                    int(row.get("requires_human_review", 1)),
                    json_dumps(row.get("generated_from_sources_json", [])),
                    json_dumps(row.get("card_json", {})),
                    row.get("summary_original"),
                    json_dumps(row.get("validation_report_json", {})),
                    row.get("reviewer"),
                    row.get("reviewed_at"),
                    row.get("review_reason"),
                    row.get("published_at"),
                ),
            )
            card_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM procedure_knowledge_cards WHERE id = ?", (card_id,))
            self.audit_log(
                entity_type="procedure_knowledge_cards",
                entity_id=card_id,
                action="knowledge_card_create",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return card_id

    def get_knowledge_card(self, card_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = self._fetch_one(conn, "SELECT * FROM procedure_knowledge_cards WHERE id = ?", (card_id,))
        if row:
            row["generated_from_sources_json"] = json_loads(row.get("generated_from_sources_json"), [])
            row["card_json"] = json_loads(row.get("card_json"), {})
            row["validation_report_json"] = json_loads(row.get("validation_report_json"), {})
        return row

    def list_knowledge_cards(self, procedure_code: str = "", xsd_code: str = "") -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if procedure_code:
            clauses.append("procedure_code = ?")
            params.append(procedure_code)
        if xsd_code:
            clauses.append("xsd_code = ?")
            params.append(xsd_code)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = self._fetch_all(conn, f"SELECT * FROM procedure_knowledge_cards {where} ORDER BY id", tuple(params))
        for row in rows:
            row["generated_from_sources_json"] = json_loads(row.get("generated_from_sources_json"), [])
            row["card_json"] = json_loads(row.get("card_json"), {})
            row["validation_report_json"] = json_loads(row.get("validation_report_json"), {})
        return rows

    def update_knowledge_card_status(
        self,
        card_id: int,
        *,
        status: str,
        reviewer: str = "",
        review_reason: str = "",
        validation_report: dict[str, Any] | None = None,
        published: bool = False,
        actor: str = "",
        source: str = "knowledge_pipeline",
    ) -> None:
        with self.connect() as conn:
            before = self._fetch_one(conn, "SELECT * FROM procedure_knowledge_cards WHERE id = ?", (card_id,))
            conn.execute(
                """
                UPDATE procedure_knowledge_cards
                SET status = ?,
                    reviewer = COALESCE(NULLIF(?, ''), reviewer),
                    reviewed_at = CASE WHEN NULLIF(?, '') IS NULL THEN reviewed_at ELSE CURRENT_TIMESTAMP END,
                    review_reason = COALESCE(NULLIF(?, ''), review_reason),
                    validation_report_json = COALESCE(?, validation_report_json),
                    published_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE published_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    reviewer,
                    reviewer,
                    review_reason,
                    json_dumps(validation_report) if validation_report is not None else None,
                    1 if published else 0,
                    card_id,
                ),
            )
            after = self._fetch_one(conn, "SELECT * FROM procedure_knowledge_cards WHERE id = ?", (card_id,))
            self.audit_log(
                entity_type="procedure_knowledge_cards",
                entity_id=card_id,
                action=f"knowledge_card_{status}",
                before=before,
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()

    def create_lifecycle_template(self, row: dict[str, Any], *, actor: str = "", source: str = "lifecycle") -> int:
        self.ensure_extended_schema()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO procedure_lifecycle_templates (
                    tenant_id, procedure_code, xsd_code, channel_code, registry_code, workflow_code,
                    name, version, active, requires_human_review, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    row.get("tenant_id"),
                    row["procedure_code"],
                    row.get("xsd_code"),
                    row["channel_code"],
                    row.get("registry_code"),
                    row.get("workflow_code"),
                    row["name"],
                    row.get("version", "v1"),
                    int(row.get("active", 1)),
                    int(row.get("requires_human_review", 1)),
                    row.get("notes"),
                ),
            )
            template_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM procedure_lifecycle_templates WHERE id = ?", (template_id,))
            self.audit_log(
                entity_type="procedure_lifecycle_templates",
                entity_id=template_id,
                action="lifecycle_template_create",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return template_id

    def add_lifecycle_step(self, row: dict[str, Any], *, actor: str = "", source: str = "lifecycle") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO procedure_lifecycle_steps (
                    tenant_id, template_id, step_code, step_name, step_type, sort_order,
                    required, trigger_event, deadline_rule_json, validation_rule_json,
                    output_required_json, next_step_on_success, next_step_on_error,
                    human_review_required, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(template_id, step_code) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    step_name = excluded.step_name,
                    step_type = excluded.step_type,
                    sort_order = excluded.sort_order,
                    required = excluded.required,
                    trigger_event = excluded.trigger_event,
                    deadline_rule_json = excluded.deadline_rule_json,
                    validation_rule_json = excluded.validation_rule_json,
                    output_required_json = excluded.output_required_json,
                    next_step_on_success = excluded.next_step_on_success,
                    next_step_on_error = excluded.next_step_on_error,
                    human_review_required = excluded.human_review_required,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    row.get("tenant_id"),
                    int(row["template_id"]),
                    row["step_code"],
                    row["step_name"],
                    row["step_type"],
                    int(row["sort_order"]),
                    int(row.get("required", 1)),
                    row.get("trigger_event"),
                    json_dumps(row.get("deadline_rule_json", {})),
                    json_dumps(row.get("validation_rule_json", {})),
                    json_dumps(row.get("output_required_json", [])),
                    row.get("next_step_on_success"),
                    row.get("next_step_on_error"),
                    int(row.get("human_review_required", 0)),
                    row.get("notes"),
                ),
            )
            step = self._fetch_one(
                conn,
                "SELECT * FROM procedure_lifecycle_steps WHERE template_id = ? AND step_code = ?",
                (int(row["template_id"]), row["step_code"]),
            )
            self.audit_log(
                entity_type="procedure_lifecycle_steps",
                entity_id=(step or {}).get("id"),
                action="lifecycle_step_upsert",
                after=step,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return int((step or {}).get("id") or cur.lastrowid or 0)

    def list_lifecycle_templates(self, xsd_code: str = "", procedure_code: str = "") -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if xsd_code:
            clauses.append("xsd_code = ?")
            params.append(xsd_code)
        if procedure_code:
            clauses.append("procedure_code = ?")
            params.append(procedure_code)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            return self._fetch_all(conn, f"SELECT * FROM procedure_lifecycle_templates {where} ORDER BY id", tuple(params))

    def list_lifecycle_steps(self, template_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                "SELECT * FROM procedure_lifecycle_steps WHERE template_id = ? ORDER BY sort_order, id",
                (template_id,),
            )
        for row in rows:
            row["deadline_rule_json"] = json_loads(row.get("deadline_rule_json"), {})
            row["validation_rule_json"] = json_loads(row.get("validation_rule_json"), {})
            row["output_required_json"] = json_loads(row.get("output_required_json"), [])
        return rows

    def create_workflow_instance(self, row: dict[str, Any], *, actor: str = "", source: str = "lifecycle") -> int:
        self.ensure_extended_schema()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO fascicolo_workflow_instances (
                    tenant_id, fascicolo_id, template_id, procedure_code, xsd_code,
                    current_step_code, status, assigned_lawyer_id, risk_level, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("tenant_id"),
                    row["fascicolo_id"],
                    int(row["template_id"]),
                    row["procedure_code"],
                    row.get("xsd_code"),
                    row.get("current_step_code"),
                    row.get("status", "OPEN"),
                    row.get("assigned_lawyer_id"),
                    row.get("risk_level", "MEDIUM"),
                    row.get("notes"),
                ),
            )
            instance_id = int(cur.lastrowid)
            after = self.get_workflow_instance(instance_id, conn=conn)
            self.audit_log(
                entity_type="fascicolo_workflow_instances",
                entity_id=instance_id,
                action="workflow_instance_create",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return instance_id

    def get_workflow_instance(self, instance_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM fascicolo_workflow_instances WHERE id = ?"
        if conn is not None:
            return self._fetch_one(conn, sql, (instance_id,))
        with self.connect() as own_conn:
            return self._fetch_one(own_conn, sql, (instance_id,))

    def update_workflow_instance_state(
        self,
        instance_id: int,
        *,
        current_step_code: str,
        status: str,
        close: bool = False,
        actor: str = "",
        source: str = "lifecycle",
        notes: str = "",
    ) -> None:
        with self.connect() as conn:
            before = self.get_workflow_instance(instance_id, conn=conn)
            if current_step_code in _PROTECTED_WORKFLOW_STATES:
                if source != _VALIDATED_WORKFLOW_SOURCE:
                    raise ValueError("Stato workflow finale aggiornabile solo tramite transition_workflow validato.")
                _insert_transition_guard(conn, "fascicolo_workflow_instances", instance_id, current_step_code)
            conn.execute(
                """
                UPDATE fascicolo_workflow_instances
                SET current_step_code = ?, status = ?,
                    closed_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE closed_at END,
                    notes = COALESCE(NULLIF(?, ''), notes)
                WHERE id = ?
                """,
                (current_step_code, status, 1 if close else 0, notes, instance_id),
            )
            after = self.get_workflow_instance(instance_id, conn=conn)
            self.audit_log(
                entity_type="fascicolo_workflow_instances",
                entity_id=instance_id,
                action="workflow_transition",
                before=before,
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()

    def add_workflow_event(self, row: dict[str, Any], *, actor: str = "", source: str = "lifecycle") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO fascicolo_workflow_events (
                    tenant_id, workflow_instance_id, event_code, event_type, event_status,
                    source, source_ref, event_payload_json, created_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("tenant_id"),
                    int(row["workflow_instance_id"]),
                    row["event_code"],
                    row["event_type"],
                    row["event_status"],
                    row.get("source"),
                    row.get("source_ref"),
                    json_dumps(row.get("event_payload_json", {})),
                    row.get("created_by") or actor,
                    row.get("notes"),
                ),
            )
            event_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM fascicolo_workflow_events WHERE id = ?", (event_id,))
            self.audit_log(
                entity_type="fascicolo_workflow_events",
                entity_id=event_id,
                action="workflow_event_add",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return event_id

    def add_signature_event(self, row: dict[str, Any], *, actor: str = "", source: str = "signature") -> int:
        self.ensure_extended_schema()
        _assert_allowed_status(row.get("verification_status"), _SIGNATURE_STATUSES, "verification_status")
        if row.get("verification_status") in _PROTECTED_SIGNATURE_STATUSES:
            raise ValueError("VERIFIED deve passare da record_signature_result validato.")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO digital_signature_events (
                    tenant_id, fascicolo_id, document_id, required, signer_expected, signer_detected,
                    signer_tax_code, signature_format, certificate_serial, hash_before,
                    hash_after, verification_status, signed_at, verified_at,
                    evidence_document_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("tenant_id"),
                    row["fascicolo_id"],
                    row["document_id"],
                    int(row.get("required", 1)),
                    row.get("signer_expected"),
                    row.get("signer_detected"),
                    row.get("signer_tax_code"),
                    row.get("signature_format"),
                    row.get("certificate_serial"),
                    row.get("hash_before"),
                    row.get("hash_after"),
                    row["verification_status"],
                    row.get("signed_at"),
                    row.get("verified_at"),
                    row.get("evidence_document_id"),
                    row.get("notes"),
                ),
            )
            event_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM digital_signature_events WHERE id = ?", (event_id,))
            self.audit_log(
                entity_type="digital_signature_events",
                entity_id=event_id,
                action="signature_event_create",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return event_id

    def list_signature_events(self, fascicolo_id: str, document_id: str = "") -> list[dict[str, Any]]:
        params: list[Any] = [fascicolo_id]
        where = "fascicolo_id = ?"
        if document_id:
            where += " AND document_id = ?"
            params.append(document_id)
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                f"SELECT * FROM digital_signature_events WHERE {where} ORDER BY id",
                tuple(params),
            )

    def update_signature_event(self, event_id: int, updates: dict[str, Any], *, actor: str = "", source: str = "signature") -> None:
        allowed = {
            "signer_detected",
            "signer_tax_code",
            "signature_format",
            "certificate_serial",
            "hash_after",
            "verification_status",
            "signed_at",
            "verified_at",
            "evidence_document_id",
            "notes",
        }
        assignments = [f"{key} = ?" for key in updates if key in allowed]
        if not assignments:
            return
        if "verification_status" in updates:
            _assert_allowed_status(updates.get("verification_status"), _SIGNATURE_STATUSES, "verification_status")
        params = [updates[key] for key in updates if key in allowed]
        params.append(event_id)
        with self.connect() as conn:
            before = self._fetch_one(conn, "SELECT * FROM digital_signature_events WHERE id = ?", (event_id,))
            if updates.get("verification_status") in _PROTECTED_SIGNATURE_STATUSES:
                if source != _VALIDATED_SIGNATURE_SOURCE:
                    raise ValueError("VERIFIED aggiornabile solo tramite record_signature_result validato.")
                candidate = {**(before or {}), **updates}
                if not candidate.get("signer_detected") or not candidate.get("hash_after"):
                    raise ValueError("VERIFIED richiede firmatario rilevato e hash del documento firmato.")
                _insert_transition_guard(conn, "digital_signature_events", event_id, updates.get("verification_status"))
            conn.execute(f"UPDATE digital_signature_events SET {', '.join(assignments)} WHERE id = ?", tuple(params))
            after = self._fetch_one(conn, "SELECT * FROM digital_signature_events WHERE id = ?", (event_id,))
            self.audit_log(
                entity_type="digital_signature_events",
                entity_id=event_id,
                action="signature_event_update",
                before=before,
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()

    def create_deposit_package(self, row: dict[str, Any], *, actor: str = "", source: str = "deposit") -> int:
        self.ensure_extended_schema()
        deposit_status = row.get("deposit_status", "DRAFT")
        _assert_allowed_status(deposit_status, _DEPOSIT_STATUSES, "deposit_status")
        if deposit_status in _OFFICIAL_DEPOSIT_RECEIPTS_BY_STATUS:
            raise ValueError("Gli stati di accettazione o rifiuto ufficio richiedono ricevuta ufficiale collegata.")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO telematic_deposit_packages (
                    tenant_id, fascicolo_id, procedure_code, xsd_code, channel_code, office_code,
                    registry_code, dati_atto_xml_id, envelope_file_id, deposit_status,
                    deposit_mode, package_hash, sent_at, accepted_at, rejected_at,
                    rejection_reason, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    row.get("tenant_id"),
                    row["fascicolo_id"],
                    row["procedure_code"],
                    row.get("xsd_code"),
                    row["channel_code"],
                    row.get("office_code"),
                    row.get("registry_code"),
                    row.get("dati_atto_xml_id"),
                    row.get("envelope_file_id"),
                    row.get("deposit_status", "DRAFT"),
                    row.get("deposit_mode"),
                    row.get("package_hash"),
                    row.get("sent_at"),
                    row.get("accepted_at"),
                    row.get("rejected_at"),
                    row.get("rejection_reason"),
                    row.get("notes"),
                ),
            )
            package_id = int(cur.lastrowid)
            after = self.get_deposit_package(package_id, conn=conn)
            self.audit_log(
                entity_type="telematic_deposit_packages",
                entity_id=package_id,
                action="deposit_package_create",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return package_id

    def get_deposit_package(self, package_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM telematic_deposit_packages WHERE id = ?"
        if conn is not None:
            return self._fetch_one(conn, sql, (package_id,))
        with self.connect() as own_conn:
            return self._fetch_one(own_conn, sql, (package_id,))

    def update_deposit_package(self, package_id: int, updates: dict[str, Any], *, actor: str = "", source: str = "deposit") -> None:
        allowed = {
            "deposit_status",
            "deposit_mode",
            "package_hash",
            "sent_at",
            "accepted_at",
            "rejected_at",
            "rejection_reason",
            "notes",
            "dati_atto_xml_id",
            "envelope_file_id",
        }
        keys = [key for key in updates if key in allowed]
        if not keys:
            return
        if "deposit_status" in updates:
            _assert_allowed_status(updates.get("deposit_status"), _DEPOSIT_STATUSES, "deposit_status")
        assignments = [f"{key} = ?" for key in keys] + ["updated_at = CURRENT_TIMESTAMP"]
        params = [updates[key] for key in keys] + [package_id]
        with self.connect() as conn:
            before = self.get_deposit_package(package_id, conn=conn)
            official_status = updates.get("deposit_status")
            if official_status in _OFFICIAL_DEPOSIT_RECEIPTS_BY_STATUS:
                if source != _VALIDATED_DEPOSIT_SOURCE:
                    raise ValueError("Stato deposito ufficio aggiornabile solo da ricevute validate.")
                receipts = self._fetch_all(
                    conn,
                    "SELECT receipt_type FROM telematic_deposit_receipts WHERE deposit_package_id = ?",
                    (package_id,),
                )
                required_receipts = _OFFICIAL_DEPOSIT_RECEIPTS_BY_STATUS[str(official_status)]
                if not any(row.get("receipt_type") in required_receipts for row in receipts):
                    raise ValueError("Stato deposito ufficio non ammesso senza ricevuta ufficiale collegata.")
                _insert_transition_guard(conn, "telematic_deposit_packages", package_id, official_status)
            conn.execute(f"UPDATE telematic_deposit_packages SET {', '.join(assignments)} WHERE id = ?", tuple(params))
            after = self.get_deposit_package(package_id, conn=conn)
            self.audit_log(
                entity_type="telematic_deposit_packages",
                entity_id=package_id,
                action="deposit_package_update",
                before=before,
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()

    def add_deposit_receipt(self, row: dict[str, Any], *, actor: str = "", source: str = "deposit") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO telematic_deposit_receipts (
                    tenant_id, deposit_package_id, receipt_type, receipt_status, pec_message_id,
                    pec_subject, sender, recipient, received_at, event_time,
                    document_id, parsed_payload_json, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("tenant_id"),
                    int(row["deposit_package_id"]),
                    row["receipt_type"],
                    row["receipt_status"],
                    row.get("pec_message_id"),
                    row.get("pec_subject"),
                    row.get("sender"),
                    row.get("recipient"),
                    row.get("received_at"),
                    row.get("event_time"),
                    row.get("document_id"),
                    json_dumps(row.get("parsed_payload_json", {})),
                    row.get("notes"),
                ),
            )
            receipt_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM telematic_deposit_receipts WHERE id = ?", (receipt_id,))
            self.audit_log(
                entity_type="telematic_deposit_receipts",
                entity_id=receipt_id,
                action="deposit_receipt_add",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return receipt_id

    def list_deposit_receipts(self, package_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                "SELECT * FROM telematic_deposit_receipts WHERE deposit_package_id = ? ORDER BY id",
                (package_id,),
            )
        for row in rows:
            row["parsed_payload_json"] = json_loads(row.get("parsed_payload_json"), {})
        return rows

    def add_obligation(self, row: dict[str, Any], *, actor: str = "", source: str = "post_acceptance") -> int:
        self.ensure_extended_schema()
        _assert_allowed_status(row.get("obligation_status", "PENDING"), _OBLIGATION_STATUSES, "obligation_status")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO post_acceptance_obligations (
                    tenant_id, fascicolo_id, procedure_code, xsd_code, trigger_event, obligation_type,
                    obligation_status, deadline_at, legal_basis, required_documents_json,
                    evidence_required_json, human_review_required, completed_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("tenant_id"),
                    row["fascicolo_id"],
                    row["procedure_code"],
                    row.get("xsd_code"),
                    row["trigger_event"],
                    row["obligation_type"],
                    row.get("obligation_status", "PENDING"),
                    row.get("deadline_at"),
                    row.get("legal_basis"),
                    json_dumps(row.get("required_documents_json", [])),
                    json_dumps(row.get("evidence_required_json", [])),
                    int(row.get("human_review_required", 1)),
                    row.get("completed_at"),
                    row.get("notes"),
                ),
            )
            obligation_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM post_acceptance_obligations WHERE id = ?", (obligation_id,))
            self.audit_log(
                entity_type="post_acceptance_obligations",
                entity_id=obligation_id,
                action="obligation_create",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return obligation_id

    def list_obligations(self, fascicolo_id: str, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [fascicolo_id]
        where = "fascicolo_id = ?"
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            where += f" AND obligation_status IN ({placeholders})"
            params.extend(statuses)
        with self.connect() as conn:
            rows = self._fetch_all(conn, f"SELECT * FROM post_acceptance_obligations WHERE {where} ORDER BY id", tuple(params))
        for row in rows:
            row["required_documents_json"] = json_loads(row.get("required_documents_json"), [])
            row["evidence_required_json"] = json_loads(row.get("evidence_required_json"), [])
        return rows

    def update_obligation(self, obligation_id: int, updates: dict[str, Any], *, actor: str = "", source: str = "post_acceptance") -> None:
        allowed = {"obligation_status", "completed_at", "notes", "deadline_at", "legal_basis"}
        keys = [key for key in updates if key in allowed]
        if not keys:
            return
        if "obligation_status" in updates:
            _assert_allowed_status(updates.get("obligation_status"), _OBLIGATION_STATUSES, "obligation_status")
        assignments = [f"{key} = ?" for key in keys]
        params = [updates[key] for key in keys] + [obligation_id]
        with self.connect() as conn:
            before = self._fetch_one(conn, "SELECT * FROM post_acceptance_obligations WHERE id = ?", (obligation_id,))
            conn.execute(f"UPDATE post_acceptance_obligations SET {', '.join(assignments)} WHERE id = ?", tuple(params))
            after = self._fetch_one(conn, "SELECT * FROM post_acceptance_obligations WHERE id = ?", (obligation_id,))
            self.audit_log(
                entity_type="post_acceptance_obligations",
                entity_id=obligation_id,
                action="obligation_update",
                before=before,
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()

    def create_notification_event(self, row: dict[str, Any], *, actor: str = "", source: str = "notification") -> int:
        self.ensure_extended_schema()
        notification_status = row.get("status", "DRAFT")
        _assert_allowed_status(notification_status, _NOTIFICATION_STATUSES, "status")
        with self.connect() as conn:
            if notification_status in _NOTIFICATION_PROOF_STATUSES:
                _assert_notification_proof_evidence(conn, str(row["fascicolo_id"]), row.get("proof_bundle_id"))
            cur = conn.execute(
                """
                INSERT INTO notification_events (
                    tenant_id, fascicolo_id, obligation_id, notification_type, recipient_name,
                    recipient_tax_code, recipient_address, recipient_address_source,
                    act_document_id, relata_document_id, sent_at, delivered_at,
                    status, proof_bundle_id, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    row.get("tenant_id"),
                    row["fascicolo_id"],
                    row.get("obligation_id"),
                    row["notification_type"],
                    row.get("recipient_name"),
                    row.get("recipient_tax_code"),
                    row.get("recipient_address"),
                    row.get("recipient_address_source"),
                    row["act_document_id"],
                    row.get("relata_document_id"),
                    row.get("sent_at"),
                    row.get("delivered_at"),
                    row.get("status", "DRAFT"),
                    row.get("proof_bundle_id"),
                    row.get("notes"),
                ),
            )
            notification_id = int(cur.lastrowid)
            after = self.get_notification_event(notification_id, conn=conn)
            self.audit_log(
                entity_type="notification_events",
                entity_id=notification_id,
                action="notification_create",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return notification_id

    def get_notification_event(self, notification_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM notification_events WHERE id = ?"
        if conn is not None:
            return self._fetch_one(conn, sql, (notification_id,))
        with self.connect() as own_conn:
            return self._fetch_one(own_conn, sql, (notification_id,))

    def update_notification_event(
        self,
        notification_id: int,
        updates: dict[str, Any],
        *,
        actor: str = "",
        source: str = "notification",
    ) -> None:
        allowed = {
            "recipient_name",
            "recipient_tax_code",
            "recipient_address",
            "recipient_address_source",
            "relata_document_id",
            "sent_at",
            "delivered_at",
            "status",
            "proof_bundle_id",
            "notes",
        }
        keys = [key for key in updates if key in allowed]
        if not keys:
            return
        if "status" in updates:
            _assert_allowed_status(updates.get("status"), _NOTIFICATION_STATUSES, "status")
        assignments = [f"{key} = ?" for key in keys] + ["updated_at = CURRENT_TIMESTAMP"]
        params = [updates[key] for key in keys] + [notification_id]
        with self.connect() as conn:
            before = self.get_notification_event(notification_id, conn=conn)
            target_status = updates.get("status")
            if target_status in _NOTIFICATION_PROOF_STATUSES:
                if source != _VALIDATED_NOTIFICATION_SOURCE:
                    raise ValueError("Stato prova notifica aggiornabile solo tramite evidence vault validato.")
                _assert_notification_proof_evidence(
                    conn,
                    str((before or {}).get("fascicolo_id") or ""),
                    updates.get("proof_bundle_id") or (before or {}).get("proof_bundle_id"),
                )
                _insert_transition_guard(conn, "notification_events", notification_id, target_status)
            conn.execute(f"UPDATE notification_events SET {', '.join(assignments)} WHERE id = ?", tuple(params))
            after = self.get_notification_event(notification_id, conn=conn)
            self.audit_log(
                entity_type="notification_events",
                entity_id=notification_id,
                action="notification_update",
                before=before,
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()

    def add_evidence_document(self, row: dict[str, Any], *, actor: str = "", source: str = "evidence_vault") -> int:
        self.ensure_extended_schema()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO evidence_documents (
                    tenant_id, fascicolo_id, evidence_type, document_id, source_event_id, hash,
                    filename_original, storage_path, legal_relevance,
                    retention_policy, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("tenant_id"),
                    row["fascicolo_id"],
                    row["evidence_type"],
                    row["document_id"],
                    row.get("source_event_id"),
                    row.get("hash"),
                    row.get("filename_original"),
                    row.get("storage_path"),
                    row.get("legal_relevance"),
                    row.get("retention_policy"),
                    row.get("notes"),
                ),
            )
            evidence_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM evidence_documents WHERE id = ?", (evidence_id,))
            self.audit_log(
                entity_type="evidence_documents",
                entity_id=evidence_id,
                action="evidence_add",
                after=after,
                actor=actor,
                source=source,
                conn=conn,
            )
            conn.commit()
        return evidence_id

    def list_evidence_documents(
        self,
        fascicolo_id: str,
        *,
        evidence_types: tuple[str, ...] | None = None,
        source_event_id: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [fascicolo_id]
        where = "fascicolo_id = ?"
        if evidence_types:
            placeholders = ", ".join("?" for _ in evidence_types)
            where += f" AND evidence_type IN ({placeholders})"
            params.extend(evidence_types)
        if source_event_id is not None:
            where += " AND source_event_id = ?"
            params.append(source_event_id)
        with self.connect() as conn:
            return self._fetch_all(conn, f"SELECT * FROM evidence_documents WHERE {where} ORDER BY id", tuple(params))

    def add_coverage_gap(
        self,
        *,
        subbranch_code: str,
        gap_type: str,
        priority_score: int,
        gap_payload: dict[str, Any],
        status: str = "OPEN",
    ) -> int:
        self.ensure_extended_schema()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO coverage_gap_queue (
                    subbranch_code, gap_type, priority_score, gap_payload_json, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (subbranch_code, gap_type, int(priority_score), json_dumps(gap_payload), status),
            )
            gap_id = int(cur.lastrowid)
            after = self._fetch_one(conn, "SELECT * FROM coverage_gap_queue WHERE id = ?", (gap_id,))
            self.audit_log(
                entity_type="coverage_gap_queue",
                entity_id=gap_id,
                action="coverage_gap_create",
                after=after,
                source="coverage",
                conn=conn,
            )
            conn.commit()
        return gap_id
