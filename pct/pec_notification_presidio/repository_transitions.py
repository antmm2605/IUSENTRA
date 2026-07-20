from __future__ import annotations

from typing import Any, Mapping

from .models import (
    PresidioStatus,
    Priority,
    TransitionResult,
    canonical_json,
    canonical_timestamp,
    json_load,
    required_text,
    utc_now_iso,
    validate_transition,
)


class NotificationPresidioTransitionMixin:

    def transition(
        self,
        presidio_id: str,
        next_status: PresidioStatus | str,
        *,
        actor: str,
        reason: str,
        evidence: Mapping[str, Any] | None,
        idempotency_key: str,
        expected_status: PresidioStatus | str | None = None,
        occurred_at: str = "",
    ) -> TransitionResult:
        target = PresidioStatus(str(next_status))
        key = required_text(idempotency_key, "idempotency_key")
        actor_value = required_text(actor, "actor")
        when = canonical_timestamp(occurred_at or utc_now_iso())
        evidence_json = canonical_json(dict(evidence or {}))
        with self.connection() as conn:
            if self.backend_kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            presidio = self._presidio_row(conn, presidio_id, lock=True)
            previous = PresidioStatus(str(presidio["status"]))
            existing = conn.execute(
                """
                SELECT * FROM pec_legal_notification_transitions
                WHERE tenant_id=? AND presidio_id=? AND idempotency_key=?
                """,
                (self.tenant_id, presidio_id, key),
            ).fetchone()
            if existing is not None:
                row = self._row(existing)
                if (
                    str(row.get("next_status") or "") != target.value
                    or str(row.get("reason") or "") != str(reason or "")
                    or canonical_json(json_load(row.get("evidence_json"), default={})) != evidence_json
                ):
                    raise ValueError("Collisione idempotency_key con transizione differente")
                return TransitionResult(
                    str(row["id"]),
                    str(row.get("previous_status") or ""),
                    str(row["next_status"]),
                    str(row["entry_hash"]),
                    False,
                )
            if expected_status is not None and previous != PresidioStatus(str(expected_status)):
                raise ValueError(f"Stato atteso {expected_status}, trovato {previous.value}")
            if previous == target:
                return TransitionResult("", previous.value, target.value, "", False)
            validate_transition(previous.value, target.value, reason=reason)
            counts = self._recipient_counts_conn(conn, presidio_id)
            if target == PresidioStatus.DELIVERY_COMPLETE and (
                counts["recipients_total"] <= 0
                or counts["recipients_delivered"] != counts["recipients_total"]
            ):
                raise ValueError("DELIVERY_COMPLETE richiede RdAC per tutti i destinatari obbligatori")
            if target == PresidioStatus.CLOSED:
                proof_required = bool(presidio.get("proof_deposit_required"))
                if proof_required and previous != PresidioStatus.PROOF_DEPOSITED:
                    raise ValueError("CLOSED richiede il deposito della prova")
                if not proof_required and previous not in {
                    PresidioStatus.DELIVERY_COMPLETE, PresidioStatus.PROOF_DEPOSITED
                }:
                    raise ValueError("CLOSED richiede consegna completa")
            result = self._append_transition_row(
                conn,
                presidio_id=presidio_id,
                previous_status=previous.value,
                next_status=target.value,
                actor=actor_value,
                reason=str(reason or ""),
                evidence=evidence,
                idempotency_key=key,
                occurred_at=when,
            )
            priority = Priority.P0.value if target == PresidioStatus.DELIVERY_FAILED else str(
                presidio.get("priority") or Priority.P1.value
            )
            review_required = bool(presidio.get("human_review_required")) or (
                target == PresidioStatus.DELIVERY_FAILED
                and str((evidence or {}).get("failure_attribution") or "") == "uncertain"
            )
            resolved_at = when if target in {
                PresidioStatus.CLOSED, PresidioStatus.NOT_REQUIRED, PresidioStatus.CANCELLED
            } else (presidio.get("resolved_at") or None)
            updated = conn.execute(
                """
                UPDATE pec_legal_notification_presidia
                SET status=?, priority=?, human_review_required=?, resolved_at=?, updated_at=?
                WHERE tenant_id=? AND id=? AND status=?
                RETURNING id
                """,
                (
                    target.value,
                    priority,
                    review_required,
                    resolved_at,
                    when,
                    self.tenant_id,
                    presidio_id,
                    previous.value,
                ),
            ).fetchone()
            if updated is None:
                raise RuntimeError("Conflitto concorrente durante la transizione del presidio")
            return result
