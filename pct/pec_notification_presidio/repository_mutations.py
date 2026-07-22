from __future__ import annotations

from typing import Any, Mapping

from .identity import canonical_document_identity, normalize_pec, recipient_identity_key
from .models import (
    DocumentRole,
    PresidioStatus,
    Priority,
    canonical_json,
    canonical_timestamp,
    required_text,
    sha256_text,
    utc_now_iso,
)

_PRESIDIO_COLUMNS = (
    "id",
    "tenant_id",
    "fascicolo_id",
    "legal_event_id",
    "source_message_id",
    "source_parsed_version_id",
    "trigger_type",
    "notification_case",
    "channel",
    "status",
    "priority",
    "confidence",
    "human_review_required",
    "source_effective_at",
    "explicit_due_at",
    "rulepack_version",
    "legal_basis_json",
    "detection_reason",
    "evidence_summary_json",
    "dedupe_key",
    "notification_instance_key",
    "assigned_user_id",
    "confirmed_at",
    "resolved_at",
    "resolution_code",
    "resolution_reason",
    "legacy_policy_id",
    "legacy_assumed_handled",
    "proof_deposit_required",
    "created_at",
    "updated_at",
)


class NotificationPresidioMutationMixin:

    def create_or_get_presidio(self, candidate: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        dedupe_key = required_text(candidate.get("dedupe_key"), "dedupe_key")
        instance_key = required_text(
            candidate.get("notification_instance_key"), "notification_instance_key"
        )
        status = PresidioStatus(str(candidate.get("status") or PresidioStatus.DETECTED))
        priority = Priority(str(candidate.get("priority") or Priority.P1))
        now = canonical_timestamp(candidate.get("created_at") or utc_now_iso())
        with self.connection() as conn:
            if self.backend_kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM pec_legal_notification_presidia
                WHERE tenant_id=? AND (dedupe_key=? OR notification_instance_key=?)
                ORDER BY created_at, id LIMIT 1
                """,
                (self.tenant_id, dedupe_key, instance_key),
            ).fetchone()
            if existing is not None:
                row = self._row(existing)
                if str(row.get("notification_instance_key") or "") != instance_key:
                    raise ValueError("Collisione dedupe_key con istanza di notifica differente")
                return row, False

            presidio_id = str(candidate.get("id") or self._uuid())
            values_by_column = {
                "id": presidio_id,
                "tenant_id": self.tenant_id,
                "fascicolo_id": required_text(candidate.get("fascicolo_id"), "fascicolo_id"),
                "legal_event_id": str(candidate.get("legal_event_id") or ""),
                "source_message_id": required_text(
                    candidate.get("source_message_id"), "source_message_id"
                ),
                "source_parsed_version_id": str(candidate.get("source_parsed_version_id") or ""),
                "trigger_type": required_text(candidate.get("trigger_type"), "trigger_type"),
                "notification_case": required_text(
                    candidate.get("notification_case"), "notification_case"
                ),
                "channel": str(candidate.get("channel") or "pec").strip().lower(),
                "status": status.value,
                "priority": priority.value,
                "confidence": float(candidate.get("confidence") or 0.0),
                "human_review_required": bool(candidate.get("human_review_required")),
                "source_effective_at": (
                    canonical_timestamp(candidate["source_effective_at"])
                    if candidate.get("source_effective_at") else None
                ),
                "explicit_due_at": (
                    canonical_timestamp(candidate["explicit_due_at"])
                    if candidate.get("explicit_due_at") else None
                ),
                "rulepack_version": required_text(
                    candidate.get("rulepack_version"), "rulepack_version"
                ),
                "legal_basis_json": canonical_json(candidate.get("legal_basis") or []),
                "detection_reason": str(candidate.get("detection_reason") or ""),
                "evidence_summary_json": canonical_json(candidate.get("evidence_summary") or {}),
                "dedupe_key": dedupe_key,
                "notification_instance_key": instance_key,
                "assigned_user_id": str(candidate.get("assigned_user_id") or ""),
                "confirmed_at": (
                    canonical_timestamp(candidate["confirmed_at"])
                    if candidate.get("confirmed_at") else None
                ),
                "resolved_at": (
                    canonical_timestamp(candidate["resolved_at"])
                    if candidate.get("resolved_at") else None
                ),
                "resolution_code": str(candidate.get("resolution_code") or ""),
                "resolution_reason": str(candidate.get("resolution_reason") or ""),
                "legacy_policy_id": str(candidate.get("legacy_policy_id") or ""),
                "legacy_assumed_handled": bool(candidate.get("legacy_assumed_handled")),
                "proof_deposit_required": bool(candidate.get("proof_deposit_required")),
                "created_at": now,
                "updated_at": now,
            }
            inserted = conn.execute(
                self._insert_sql("pec_legal_notification_presidia", _PRESIDIO_COLUMNS)
                + " ON CONFLICT DO NOTHING RETURNING id",
                tuple(values_by_column[column] for column in _PRESIDIO_COLUMNS),
            ).fetchone()
            if inserted is None:
                existing = conn.execute(
                    """
                    SELECT * FROM pec_legal_notification_presidia
                    WHERE tenant_id=? AND (dedupe_key=? OR notification_instance_key=?)
                    ORDER BY created_at, id LIMIT 1
                    """,
                    (self.tenant_id, dedupe_key, instance_key),
                ).fetchone()
                if existing is None:
                    raise ValueError("Identificatore presidio già utilizzato nel tenant")
                row = self._row(existing)
                if str(row.get("notification_instance_key") or "") != instance_key:
                    raise ValueError("Collisione dedupe_key con istanza di notifica differente")
                return row, False
            self._append_transition_row(
                conn,
                presidio_id=presidio_id,
                previous_status="",
                next_status=status.value,
                actor=str(candidate.get("actor") or "notification-detector"),
                reason=str(candidate.get("detection_reason") or "Candidato rilevato."),
                evidence=candidate.get("evidence_summary") or {},
                idempotency_key=f"create:{dedupe_key}",
                occurred_at=now,
            )
            return self._presidio_row(conn, presidio_id), True

    def assign_presidio(
        self,
        presidio_id: str,
        assigned_user_id: str,
        *,
        actor: str,
        reason: str = "",
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        assigned = str(assigned_user_id or "").strip()
        actor_value = required_text(actor, "actor")
        key = required_text(
            idempotency_key or f"assign:{presidio_id}:{actor_value}:{assigned}",
            "idempotency_key",
        )
        now = canonical_timestamp(utc_now_iso())
        with self.connection() as conn:
            if self.backend_kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            presidio = self._presidio_row(conn, presidio_id, lock=True)
            existing = conn.execute(
                """
                SELECT id FROM pec_legal_notification_transitions
                WHERE tenant_id=? AND presidio_id=? AND idempotency_key=?
                """,
                (self.tenant_id, presidio_id, key),
            ).fetchone()
            if existing is not None:
                return self._presidio_row(conn, presidio_id)
            previous = PresidioStatus(str(presidio["status"]))
            conn.execute(
                """
                UPDATE pec_legal_notification_presidia
                SET assigned_user_id=?, updated_at=?
                WHERE tenant_id=? AND id=?
                """,
                (assigned, now, self.tenant_id, presidio_id),
            )
            self._append_transition_row(
                conn,
                presidio_id=presidio_id,
                previous_status=previous.value,
                next_status=previous.value,
                actor=actor_value,
                reason=str(reason or "Assegnazione presidio aggiornata."),
                evidence={"event": "assignment", "assigned": bool(assigned)},
                idempotency_key=key,
                occurred_at=now,
            )
            return self._presidio_row(conn, presidio_id)

    def upsert_document(self, presidio_id: str, document: Mapping[str, Any]) -> dict[str, Any]:
        role = DocumentRole(str(document.get("document_role") or DocumentRole.OFFICE_PEC_COPY))
        identity = canonical_document_identity(document)
        identity_key = str(document.get("identity_key") or identity.key)
        now = canonical_timestamp(document.get("created_at") or utc_now_iso())
        with self.connection() as conn:
            self._presidio_row(conn, presidio_id)
            conn.execute(
                """
                INSERT INTO pec_legal_notification_documents
                (id, tenant_id, presidio_id, identity_key, fascicolo_document_id,
                 document_role, document_version, outer_sha256, content_sha256,
                 zip_sha256, zip_member_path, portal_document_id, portal_reference,
                 original_filename, authoritative, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id, presidio_id, identity_key) DO UPDATE SET
                    fascicolo_document_id=CASE
                        WHEN excluded.fascicolo_document_id<>'' THEN excluded.fascicolo_document_id
                        ELSE pec_legal_notification_documents.fascicolo_document_id
                    END,
                    document_role=CASE
                        WHEN excluded.document_role='portal_original' THEN excluded.document_role
                        ELSE pec_legal_notification_documents.document_role
                    END,
                    document_version=CASE
                        WHEN excluded.document_version<>'' THEN excluded.document_version
                        ELSE pec_legal_notification_documents.document_version
                    END,
                    outer_sha256=CASE
                        WHEN excluded.outer_sha256<>'' THEN excluded.outer_sha256
                        ELSE pec_legal_notification_documents.outer_sha256
                    END,
                    content_sha256=CASE
                        WHEN excluded.content_sha256<>'' THEN excluded.content_sha256
                        ELSE pec_legal_notification_documents.content_sha256
                    END,
                    zip_sha256=CASE
                        WHEN excluded.zip_sha256<>'' THEN excluded.zip_sha256
                        ELSE pec_legal_notification_documents.zip_sha256
                    END,
                    zip_member_path=CASE
                        WHEN excluded.zip_member_path<>'' THEN excluded.zip_member_path
                        ELSE pec_legal_notification_documents.zip_member_path
                    END,
                    portal_document_id=CASE
                        WHEN excluded.portal_document_id<>'' THEN excluded.portal_document_id
                        ELSE pec_legal_notification_documents.portal_document_id
                    END,
                    portal_reference=CASE
                        WHEN excluded.portal_reference<>'' THEN excluded.portal_reference
                        ELSE pec_legal_notification_documents.portal_reference
                    END,
                    original_filename=CASE
                        WHEN excluded.original_filename<>'' THEN excluded.original_filename
                        ELSE pec_legal_notification_documents.original_filename
                    END,
                    authoritative=CASE
                        WHEN excluded.authoritative THEN TRUE
                        ELSE pec_legal_notification_documents.authoritative
                    END
                """,
                (
                    str(document.get("id") or self._uuid()),
                    self.tenant_id,
                    presidio_id,
                    identity_key,
                    str(document.get("fascicolo_document_id") or ""),
                    role.value,
                    str(document.get("document_version") or "1"),
                    str(document.get("outer_sha256") or ""),
                    str(document.get("content_sha256") or ""),
                    str(document.get("zip_sha256") or ""),
                    str(document.get("zip_member_path") or ""),
                    str(document.get("portal_document_id") or ""),
                    str(document.get("portal_reference") or ""),
                    str(document.get("original_filename") or ""),
                    bool(document.get("authoritative")),
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM pec_legal_notification_documents
                WHERE tenant_id=? AND presidio_id=? AND identity_key=?
                """,
                (self.tenant_id, presidio_id, identity_key),
            ).fetchone()
            return self._row(row)

    def upsert_recipient(self, presidio_id: str, recipient: Mapping[str, Any]) -> dict[str, Any]:
        identity_key = str(recipient.get("recipient_identity_key") or recipient_identity_key(recipient))
        now = canonical_timestamp(recipient.get("updated_at") or utc_now_iso())
        with self.connection() as conn:
            self._presidio_row(conn, presidio_id)
            conn.execute(
                """
                INSERT INTO pec_legal_notification_recipients
                (id, tenant_id, presidio_id, recipient_identity_key, name, fiscal_id,
                 role, pec_address, public_register, public_register_verified_at,
                 required, send_status, rac_status, delivery_status, failure_reason,
                 failure_attribution, sent_message_id, rac_message_id, rdac_message_id, failure_message_id,
                 evidence_json, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id, presidio_id, recipient_identity_key) DO UPDATE SET
                    name=excluded.name,
                    fiscal_id=excluded.fiscal_id,
                    role=excluded.role,
                    pec_address=excluded.pec_address,
                    public_register=excluded.public_register,
                    public_register_verified_at=excluded.public_register_verified_at,
                    required=excluded.required,
                    updated_at=excluded.updated_at
                """,
                (
                    str(recipient.get("id") or self._uuid()),
                    self.tenant_id,
                    presidio_id,
                    identity_key,
                    str(recipient.get("name") or ""),
                    str(recipient.get("fiscal_id") or ""),
                    str(recipient.get("role") or ""),
                    normalize_pec(recipient.get("pec_address") or recipient.get("pec")),
                    str(recipient.get("public_register") or ""),
                    (
                        canonical_timestamp(recipient["public_register_verified_at"])
                        if recipient.get("public_register_verified_at") else None
                    ),
                    bool(recipient.get("required", True)),
                    str(recipient.get("send_status") or "pending"),
                    str(recipient.get("rac_status") or "pending"),
                    str(recipient.get("delivery_status") or "pending"),
                    str(recipient.get("failure_reason") or ""),
                    str(recipient.get("failure_attribution") or ""),
                    str(recipient.get("sent_message_id") or ""),
                    str(recipient.get("rac_message_id") or ""),
                    str(recipient.get("rdac_message_id") or ""),
                    str(recipient.get("failure_message_id") or ""),
                    canonical_json(recipient.get("evidence") or {}),
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM pec_legal_notification_recipients
                WHERE tenant_id=? AND presidio_id=? AND recipient_identity_key=?
                """,
                (self.tenant_id, presidio_id, identity_key),
            ).fetchone()
            return self._row(row)

    def append_evidence(self, presidio_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
        evidence_type = required_text(evidence.get("evidence_type"), "evidence_type")
        source_type = required_text(evidence.get("source_type"), "source_type")
        source_id = required_text(evidence.get("source_id"), "source_id")
        recipient_id = str(evidence.get("recipient_id") or "")
        evidence_key = str(
            evidence.get("evidence_key")
            or sha256_text(canonical_json([presidio_id, recipient_id, evidence_type, source_type, source_id]))
        )
        with self.connection() as conn:
            self._presidio_row(conn, presidio_id)
            conn.execute(
                """
                INSERT INTO pec_legal_notification_evidence
                (id, tenant_id, presidio_id, recipient_id, evidence_key, evidence_type,
                 source_type, source_id, message_id, eml_sha256, attachment_sha256,
                 text_excerpt, source_locator, confidence, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id, presidio_id, evidence_key) DO NOTHING
                """,
                (
                    str(evidence.get("id") or self._uuid()),
                    self.tenant_id,
                    presidio_id,
                    recipient_id or None,
                    evidence_key,
                    evidence_type,
                    source_type,
                    source_id,
                    str(evidence.get("message_id") or ""),
                    str(evidence.get("eml_sha256") or ""),
                    str(evidence.get("attachment_sha256") or ""),
                    str(evidence.get("text_excerpt") or "")[:2000],
                    str(evidence.get("source_locator") or ""),
                    float(evidence.get("confidence") or 0.0),
                    canonical_timestamp(evidence.get("created_at") or utc_now_iso()),
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM pec_legal_notification_evidence
                WHERE tenant_id=? AND presidio_id=? AND evidence_key=?
                """,
                (self.tenant_id, presidio_id, evidence_key),
            ).fetchone()
            return self._row(row)

    def _recipient_counts_conn(self, conn: Any, presidio_id: str) -> dict[str, int]:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN required=TRUE THEN 1 ELSE 0 END) AS recipients_total,
                SUM(CASE WHEN required=TRUE AND send_status='sent' THEN 1 ELSE 0 END) AS recipients_sent,
                SUM(CASE WHEN required=TRUE AND rac_status='received' THEN 1 ELSE 0 END) AS recipients_rac,
                SUM(CASE WHEN required=TRUE AND delivery_status='delivered' THEN 1 ELSE 0 END) AS recipients_delivered,
                SUM(CASE WHEN required=TRUE AND delivery_status='failed' THEN 1 ELSE 0 END) AS recipients_failed
            FROM pec_legal_notification_recipients
            WHERE tenant_id=? AND presidio_id=?
            """,
            (self.tenant_id, presidio_id),
        ).fetchone()
        values = self._row(row)
        return {key: int(values.get(key) or 0) for key in (
            "recipients_total", "recipients_sent", "recipients_rac",
            "recipients_delivered", "recipients_failed"
        )}

    def recipient_counts(self, presidio_id: str) -> dict[str, int]:
        with self.connection() as conn:
            self._presidio_row(conn, presidio_id)
            return self._recipient_counts_conn(conn, presidio_id)
