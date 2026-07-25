from __future__ import annotations

from typing import Any, Mapping

from .identity import normalize_pec
from .models import (
    ReceiptKind,
    canonical_json,
    canonical_timestamp,
    normalize_failure_attribution,
    required_text,
    sanitize_operational_error,
    utc_now_iso,
)


class NotificationPresidioReceiptMixin:

    def find_recipient_for_receipt(
        self, *, original_message_id: str, pec_address: str = ""
    ) -> dict[str, Any] | None:
        message_id = required_text(original_message_id, "original_message_id")
        stripped_message_id = message_id.strip("<> ")
        variants = {
            message_id,
            stripped_message_id,
            f"<{stripped_message_id}>" if stripped_message_id else "",
        }
        variants = {item for item in variants if item}
        normalized_pec = normalize_pec(pec_address)
        sql = """
            SELECT * FROM pec_legal_notification_recipients
            WHERE tenant_id=? AND sent_message_id IN ({placeholders})
        """
        sql = sql.format(placeholders=",".join("?" for _ in variants))
        params: list[Any] = [self.tenant_id, *sorted(variants)]
        if normalized_pec:
            sql += " AND pec_address=?"
            params.append(normalized_pec)
        sql += " ORDER BY updated_at DESC, id DESC LIMIT 2"
        with self.connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return self._row(rows[0]) if len(rows) == 1 else None

    def mark_recipient_event(
        self,
        recipient_id: str,
        *,
        kind: ReceiptKind | str,
        message_id: str,
        failure_reason: str = "",
        failure_attribution: str = "",
        evidence: Mapping[str, Any] | None = None,
        occurred_at: str = "",
    ) -> dict[str, Any]:
        receipt_kind = ReceiptKind(str(kind))
        event_message_id = required_text(message_id, "message_id")
        when = canonical_timestamp(occurred_at or utc_now_iso())
        attribution = normalize_failure_attribution(failure_attribution)
        with self.connection() as conn:
            if self.backend_kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM pec_legal_notification_recipients WHERE tenant_id=? AND id=?",
                (self.tenant_id, required_text(recipient_id, "recipient_id")),
            ).fetchone()
            if row is None:
                raise KeyError("Destinatario non trovato per il tenant corrente")
            current = self._row(row)
            if receipt_kind == ReceiptKind.SENT:
                conn.execute(
                    """
                    UPDATE pec_legal_notification_recipients
                    SET send_status='sent', sent_message_id=?, evidence_json=?, updated_at=?
                    WHERE tenant_id=? AND id=?
                    """,
                    (event_message_id, canonical_json(evidence or {}), when, self.tenant_id, recipient_id),
                )
            elif receipt_kind == ReceiptKind.RAC:
                conn.execute(
                    """
                    UPDATE pec_legal_notification_recipients
                    SET rac_status='received', rac_message_id=?, updated_at=?
                    WHERE tenant_id=? AND id=?
                    """,
                    (event_message_id, when, self.tenant_id, recipient_id),
                )
            elif receipt_kind == ReceiptKind.RDAC and str(current.get("delivery_status")) != "failed":
                conn.execute(
                    """
                    UPDATE pec_legal_notification_recipients
                    SET delivery_status='delivered', rdac_message_id=?, failure_reason='', updated_at=?
                    WHERE tenant_id=? AND id=?
                    """,
                    (event_message_id, when, self.tenant_id, recipient_id),
                )
            elif receipt_kind == ReceiptKind.FAILURE and str(current.get("delivery_status")) != "delivered":
                conn.execute(
                    """
                    UPDATE pec_legal_notification_recipients
                    SET delivery_status='failed', failure_message_id=?, failure_reason=?,
                        failure_attribution=?, updated_at=?
                    WHERE tenant_id=? AND id=? AND delivery_status<>'delivered'
                    """,
                    (
                        event_message_id,
                        sanitize_operational_error(failure_reason),
                        attribution,
                        when,
                        self.tenant_id,
                        recipient_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE pec_legal_notification_presidia
                    SET priority='P0',
                        human_review_required=CASE WHEN ? THEN TRUE ELSE human_review_required END,
                        updated_at=?
                    WHERE tenant_id=? AND id=?
                    """,
                    (
                        attribution == "uncertain",
                        when,
                        self.tenant_id,
                        str(current["presidio_id"]),
                    ),
                )
            updated = conn.execute(
                "SELECT * FROM pec_legal_notification_recipients WHERE tenant_id=? AND id=?",
                (self.tenant_id, recipient_id),
            ).fetchone()
            return self._row(updated)
