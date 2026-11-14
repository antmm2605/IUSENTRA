"""Bozza di relata nel database del presidio notifiche dello studio."""
from __future__ import annotations

import json
from typing import Any, Mapping

from web.services.notification_presidia_runtime import build_notification_presidio_repository

STATI_BOZZA = ("NOTIFICATION_CONFIRMED", "RECIPIENTS_TO_VERIFY", "READY_FOR_RELATA", "RELATA_DRAFTED")


def load_presidio_draft(presidio_id: str, practice_id: str, *, repository: Any = None) -> dict[str, Any] | None:
    repo = repository if repository is not None else build_notification_presidio_repository(read_only=True)
    with repo.connection() as conn:
        # Un archivio precedente non ha ancora applicato la migrazione.
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'pec_legal_notification_relata_drafts'"
        ).fetchone() is None:
            return None
        row = conn.execute(
            """
            SELECT d.draft_json FROM pec_legal_notification_relata_drafts d
            JOIN pec_legal_notification_presidia p
              ON p.tenant_id = d.tenant_id AND p.id = d.presidio_id AND p.fascicolo_id = d.fascicolo_id
            WHERE d.tenant_id = ? AND d.presidio_id = ? AND d.fascicolo_id = ?
            """,
            (repo.tenant_id, presidio_id, practice_id),
        ).fetchone()
    return json.loads(row["draft_json"]) if row is not None else None


def save_presidio_draft(presidio_id: str, draft: Mapping[str, Any]) -> bool:
    repo = build_notification_presidio_repository()
    payload = json.dumps({**draft, "presidioId": presidio_id}, ensure_ascii=False)
    with repo.connection() as conn:
        result = conn.execute(
            """
            INSERT INTO pec_legal_notification_relata_drafts (tenant_id, presidio_id, fascicolo_id, draft_json)
            SELECT p.tenant_id, p.id, p.fascicolo_id, ? FROM pec_legal_notification_presidia p
            WHERE p.tenant_id = ? AND p.id = ? AND p.fascicolo_id = ? AND p.source_message_id <> ''
              AND p.status IN (?, ?, ?, ?)
              AND EXISTS (
                  SELECT 1 FROM pec_legal_notification_documents d
                  WHERE d.tenant_id = p.tenant_id AND d.presidio_id = p.id
                    AND d.document_role = 'portal_original' AND d.authoritative = 1
                    AND TRIM(d.fascicolo_document_id) <> ''
              )
            ON CONFLICT (tenant_id, presidio_id) DO UPDATE SET
                fascicolo_id = excluded.fascicolo_id, draft_json = excluded.draft_json
            """,
            (payload, repo.tenant_id, presidio_id, draft["practiceId"], *STATI_BOZZA),
        )
        return result.rowcount == 1
