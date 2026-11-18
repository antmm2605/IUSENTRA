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

    def _fascicolo_pec(self, conn: Any, message_id: str) -> str:
        # L'archivio MIME è nel database PEC SQLite condiviso con il worker.
        # I repository autonomi non hanno quel registro.
        if not message_id or self.backend_kind != "sqlite" or not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pec_messages'"
        ).fetchone():
            return ""
        row = conn.execute(
            "SELECT linked_fascicolo_id FROM pec_messages WHERE tenant_id=? AND id=?",
            (self.tenant_id, message_id),
        ).fetchone()
        return str(row[0] or "") if row is not None else ""

    def annulla_presidio_sul_fascicolo_errato(
        self, presidio_id: str, presidio_corretto_id: str, *, actor: str,
    ) -> TransitionResult:
        return self.transition(
            presidio_id, PresidioStatus.CANCELLED,
            actor=actor,
            reason="Rettifica del collegamento: la PEC appartiene a un altro fascicolo. "
                   "Il presidio corrispondente è già presente nel fascicolo corretto.",
            evidence={"source": "rettifica_fascicolo_pec", "presidio_corretto_id": presidio_corretto_id},
            idempotency_key=f"rettifica-fascicolo-pec:{presidio_corretto_id}",
        )

    def _verifica_rettifica_fascicolo_pec(
        self, conn: Any, presidio: Mapping[str, Any], presidio_corretto_id: str,
    ) -> None:
        corretto = self._presidio_row(conn, presidio_corretto_id, lock=True)
        fascicolo_pec = self._fascicolo_pec(conn, str(presidio["source_message_id"]))
        stessi_riferimenti = all(presidio[key] == corretto[key] for key in (
            "source_message_id", "source_parsed_version_id", "trigger_type", "notification_case", "channel",
        ))
        if (not fascicolo_pec or fascicolo_pec == presidio["fascicolo_id"]
                or fascicolo_pec != corretto["fascicolo_id"] or not stessi_riferimenti
                or corretto["status"] == PresidioStatus.CANCELLED.value):
            raise ValueError("Rettifica non ammessa: PEC e presidio del fascicolo corretto devono concordare.")
        documenti = conn.execute(
            "SELECT presidio_id,identity_key FROM pec_legal_notification_documents "
            "WHERE tenant_id=? AND presidio_id IN (?,?)",
            (self.tenant_id, presidio["id"], corretto["id"]),
        ).fetchall()
        identita = {row[1] for row in documenti if row[0] == presidio["id"]}
        if not identita or identita != {row[1] for row in documenti if row[0] == corretto["id"]}:
            raise ValueError("Rettifica non ammessa: i documenti dei due presìdi non coincidono.")
        invii = conn.execute(
            "SELECT 1 FROM pec_legal_notification_recipients "
            "WHERE tenant_id=? AND presidio_id=? AND "
            "(sent_message_id<>'' OR rac_message_id<>'' OR rdac_message_id<>'' OR failure_message_id<>'')",
            (self.tenant_id, presidio["id"]),
        ).fetchone()
        if invii:
            raise ValueError("Rettifica non ammessa: il presidio ha invii o ricevute proprie.")
        if presidio["status"] == PresidioStatus.PROOF_DEPOSITED.value:
            ultima = conn.execute(
                "SELECT evidence_json FROM pec_legal_notification_transitions "
                "WHERE tenant_id=? AND presidio_id=? ORDER BY chain_index DESC LIMIT 1",
                (self.tenant_id, presidio["id"]),
            ).fetchone()
            if not ultima or json_load(ultima[0], default={}).get("source") != "fascicolo_notification_relata":
                raise ValueError("Rettifica non ammessa: la prova non deriva dal solo fascicolo associato.")

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
            rettifica = target == PresidioStatus.CANCELLED and (evidence or {}).get("source") == "rettifica_fascicolo_pec"
            if rettifica:
                self._verifica_rettifica_fascicolo_pec(conn, presidio, str(evidence["presidio_corretto_id"]))
            if not rettifica or previous != PresidioStatus.PROOF_DEPOSITED:
                validate_transition(previous.value, target.value, reason=reason)
            ruolo_estraneo = target == PresidioStatus.CANCELLED and (evidence or {}).get("source") == "frontespizio_e_allegato_pec"
            if ruolo_estraneo:
                invii = conn.execute(
                    "SELECT 1 FROM pec_legal_notification_recipients WHERE tenant_id=? AND presidio_id=? "
                    "AND (sent_message_id<>'' OR rac_message_id<>'' OR rdac_message_id<>'' OR failure_message_id<>'')",
                    (self.tenant_id, presidio_id),
                ).fetchone()
                if invii or presidio.get("confirmed_at"):
                    raise ValueError("Il presidio ha già una conferma, un invio o una ricevuta.")
            if target == PresidioStatus.PROOF_DEPOSITED:
                fascicolo_pec = self._fascicolo_pec(conn, str(presidio["source_message_id"]))
                if fascicolo_pec and fascicolo_pec != presidio["fascicolo_id"]:
                    raise ValueError("La prova riguarda un fascicolo diverso dal fascicolo della PEC.")
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
            if ruolo_estraneo:
                conn.execute(
                    "UPDATE pec_legal_notification_presidia SET resolution_code=?, resolution_reason=? WHERE tenant_id=? AND id=?",
                    ("PROVVEDIMENTO_ALTRO_RUOLO", reason, self.tenant_id, presidio_id),
                )
            return result
