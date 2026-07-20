from __future__ import annotations

from typing import Any, Mapping

from .models import (
    TransitionResult,
    canonical_json,
    canonical_timestamp,
    json_load,
    sha256_text,
)

GENESIS_HASH = "0" * 64


class NotificationPresidioTransitionChainMixin:

    def _transition_payload(
        self,
        *,
        transition_id: str,
        presidio_id: str,
        previous_status: str,
        next_status: str,
        actor: str,
        chain_index: int,
        reason: str,
        evidence_json: str,
        occurred_at: str,
        prev_hash: str,
    ) -> dict[str, Any]:
        return {
            "algorithm": "sha256-chain-v2",
            "id": transition_id,
            "tenant_id": self.tenant_id,
            "presidio_id": presidio_id,
            "previous_status": previous_status,
            "next_status": next_status,
            "actor": actor,
            "chain_index": chain_index,
            "reason": reason,
            "evidence": json_load(evidence_json, default={}),
            "occurred_at": occurred_at,
            "prev_hash": prev_hash,
        }

    def _append_transition_row(
        self,
        conn: Any,
        *,
        presidio_id: str,
        previous_status: str,
        next_status: str,
        actor: str,
        reason: str,
        evidence: Mapping[str, Any] | None,
        idempotency_key: str,
        occurred_at: str,
    ) -> TransitionResult:
        transition_id = self._uuid()
        occurred_at = canonical_timestamp(occurred_at)
        evidence_json = canonical_json(dict(evidence or {}))
        latest = conn.execute(
            """
            SELECT entry_hash, chain_index FROM pec_legal_notification_transitions
            WHERE tenant_id=? AND presidio_id=?
            ORDER BY chain_index DESC LIMIT 1
            """,
            (self.tenant_id, presidio_id),
        ).fetchone()
        prev_hash = str((latest["entry_hash"] if latest else "") or GENESIS_HASH)
        chain_index = int(latest["chain_index"] if latest else 0) + 1
        payload = self._transition_payload(
            transition_id=transition_id,
            presidio_id=presidio_id,
            previous_status=previous_status,
            next_status=next_status,
            actor=actor,
            chain_index=chain_index,
            reason=reason,
            evidence_json=evidence_json,
            occurred_at=occurred_at,
            prev_hash=prev_hash,
        )
        entry_hash = sha256_text(canonical_json(payload))
        conn.execute(
            """
            INSERT INTO pec_legal_notification_transitions
            (id, tenant_id, presidio_id, previous_status, next_status, actor, chain_index,
             reason, evidence_json, occurred_at, prev_hash, entry_hash, idempotency_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                transition_id,
                self.tenant_id,
                presidio_id,
                previous_status,
                next_status,
                actor,
                chain_index,
                reason,
                evidence_json,
                occurred_at,
                prev_hash,
                entry_hash,
                idempotency_key,
            ),
        )
        return TransitionResult(transition_id, previous_status, next_status, entry_hash, True)
