from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .models import (
    JobStatus,
    canonical_json,
    required_text,
    sanitize_operational_error,
    sha256_text,
    utc_now_iso,
)


class NotificationPresidioWorkQueueLifecycleMixin:

    def complete(self, job_id: str, *, worker_id: str) -> bool:
        now = utc_now_iso()
        with self.repository.connection() as conn:
            row = conn.execute(
                """
                UPDATE pec_legal_notification_jobs
                SET status='completed', completed_at=?, heartbeat_at=?, updated_at=?
                WHERE tenant_id=? AND id=? AND status='running' AND worker_id=?
                RETURNING id
                """,
                (now, now, now, self.tenant_id, job_id, worker_id),
            ).fetchone()
        return row is not None

    def fail(
        self,
        job_id: str,
        *,
        worker_id: str,
        error: str,
        retry_at: str = "",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.repository.connection() as conn:
            if self.repository.backend_kind == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                """
                SELECT * FROM pec_legal_notification_jobs
                WHERE tenant_id=? AND id=? AND status='running' AND worker_id=?
                """,
                (self.tenant_id, job_id, worker_id),
            ).fetchone()
            if current is None:
                raise KeyError("Job non posseduto dal worker")
            current_row = dict(current)
            exhausted = int(current_row.get("attempts") or 0) >= int(current_row.get("max_attempts") or 1)
            status = JobStatus.DEAD.value if exhausted else JobStatus.QUEUED.value
            available = str(retry_at or now)
            updated = conn.execute(
                """
                UPDATE pec_legal_notification_jobs
                SET status=?, available_at=?, worker_id='', locked_at=NULL, heartbeat_at=NULL,
                    last_error=?, updated_at=?
                WHERE tenant_id=? AND id=? AND status='running' AND worker_id=?
                RETURNING *
                """,
                (
                    status,
                    available,
                    sanitize_operational_error(error),
                    now,
                    self.tenant_id,
                    job_id,
                    worker_id,
                ),
            ).fetchone()
        return self._row(updated)

    def recover_stale(self, *, stale_after_seconds: int = 900) -> int:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=max(60, int(stale_after_seconds)))
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        now = utc_now_iso()
        recovered = 0
        with self.repository.connection() as conn:
            rows = conn.execute(
                """
                SELECT id FROM pec_legal_notification_jobs
                WHERE tenant_id=? AND status='running' AND heartbeat_at IS NOT NULL AND heartbeat_at<?
                ORDER BY heartbeat_at, id LIMIT 100
                """,
                (self.tenant_id, cutoff),
            ).fetchall()
            for row in rows:
                claimed = conn.execute(
                    """
                    UPDATE pec_legal_notification_jobs
                    SET status='queued', worker_id='', locked_at=NULL, heartbeat_at=NULL,
                        available_at=?, last_error='stale worker recovered', updated_at=?
                    WHERE tenant_id=? AND id=? AND status='running' AND heartbeat_at<?
                    RETURNING id
                    """,
                    (now, now, self.tenant_id, row["id"], cutoff),
                ).fetchone()
                recovered += int(claimed is not None)
        return recovered

    def store_unmatched_receipt(self, receipt: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        receipt_message_id = required_text(receipt.get("message_id"), "message_id")
        receipt_type = required_text(receipt.get("receipt_type"), "receipt_type")
        recipient_key = str(receipt.get("recipient_identity_key") or "")
        receipt_key = str(
            receipt.get("receipt_key")
            or sha256_text(canonical_json([receipt_message_id, receipt_type, recipient_key]))
        )
        item_id = str(uuid.uuid4())
        now = utc_now_iso()
        with self.repository.connection() as conn:
            conn.execute(
                """
                INSERT INTO pec_legal_notification_unmatched_receipts
                (id, tenant_id, receipt_key, receipt_type, receipt_message_id,
                 original_message_id, recipient_identity_key, payload_json, status,
                 worker_id, locked_at, attempts, matched_presidio_id,
                 matched_recipient_id, created_at, updated_at, resolved_at)
                VALUES (?,?,?,?,?,?,?,?,'queued','',NULL,0,NULL,NULL,?,?,NULL)
                ON CONFLICT(tenant_id, receipt_key) DO NOTHING
                """,
                (
                    item_id,
                    self.tenant_id,
                    receipt_key,
                    receipt_type,
                    receipt_message_id,
                    str(receipt.get("original_message_id") or ""),
                    recipient_key,
                    canonical_json(receipt.get("payload") or dict(receipt)),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM pec_legal_notification_unmatched_receipts
                WHERE tenant_id=? AND receipt_key=?
                """,
                (self.tenant_id, receipt_key),
            ).fetchone()
        result = self._row(row)
        return result, str(result.get("id") or "") == item_id

    def claim_unmatched(self, worker_id: str) -> dict[str, Any] | None:
        worker = required_text(worker_id, "worker_id")
        now = utc_now_iso()
        with self.repository.connection() as conn:
            if self.repository.backend_kind == "postgresql":
                row = conn.execute(
                    """
                    WITH candidate AS (
                        SELECT id FROM pec_legal_notification_unmatched_receipts
                        WHERE tenant_id=? AND status='queued'
                        ORDER BY created_at, id FOR UPDATE SKIP LOCKED LIMIT 1
                    )
                    UPDATE pec_legal_notification_unmatched_receipts AS item
                    SET status='running', worker_id=?, locked_at=?,
                        attempts=item.attempts+1, updated_at=?
                    FROM candidate
                    WHERE item.tenant_id=? AND item.id=candidate.id AND item.status='queued'
                    RETURNING item.*
                    """,
                    (self.tenant_id, worker, now, now, self.tenant_id),
                ).fetchone()
            else:
                conn.execute("BEGIN IMMEDIATE")
                candidate = conn.execute(
                    """
                    SELECT id FROM pec_legal_notification_unmatched_receipts
                    WHERE tenant_id=? AND status='queued'
                    ORDER BY created_at, id LIMIT 1
                    """,
                    (self.tenant_id,),
                ).fetchone()
                if candidate is None:
                    return None
                row = conn.execute(
                    """
                    UPDATE pec_legal_notification_unmatched_receipts
                    SET status='running', worker_id=?, locked_at=?,
                        attempts=attempts+1, updated_at=?
                    WHERE tenant_id=? AND id=? AND status='queued'
                    RETURNING *
                    """,
                    (worker, now, now, self.tenant_id, candidate["id"]),
                ).fetchone()
        return self._row(row) if row is not None else None

    def resolve_unmatched(
        self,
        item_id: str,
        *,
        worker_id: str,
        presidio_id: str,
        recipient_id: str,
    ) -> bool:
        now = utc_now_iso()
        with self.repository.connection() as conn:
            row = conn.execute(
                """
                UPDATE pec_legal_notification_unmatched_receipts
                SET status='matched', matched_presidio_id=?, matched_recipient_id=?,
                    resolved_at=?, updated_at=?
                WHERE tenant_id=? AND id=? AND status='running' AND worker_id=?
                RETURNING id
                """,
                (
                    presidio_id,
                    recipient_id or None,
                    now,
                    now,
                    self.tenant_id,
                    item_id,
                    worker_id,
                ),
            ).fetchone()
        return row is not None

    def release_unmatched(self, item_id: str, *, worker_id: str) -> bool:
        now = utc_now_iso()
        with self.repository.connection() as conn:
            row = conn.execute(
                """
                UPDATE pec_legal_notification_unmatched_receipts
                SET status='queued', worker_id='', locked_at=NULL, updated_at=?
                WHERE tenant_id=? AND id=? AND status='running' AND worker_id=?
                RETURNING id
                """,
                (now, self.tenant_id, item_id, worker_id),
            ).fetchone()
        return row is not None
