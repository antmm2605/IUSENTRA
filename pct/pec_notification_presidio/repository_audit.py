from __future__ import annotations

from typing import Any

from .models import canonical_json, canonical_timestamp, json_load, sha256_text
from .repository_transition_chain import GENESIS_HASH


class NotificationPresidioAuditMixin:

    def verify_transition_chain(self, presidio_id: str) -> dict[str, Any]:
        with self.connection() as conn:
            presidio = self._presidio_row(conn, presidio_id)
            rows = [
                self._row(row)
                for row in conn.execute(
                    """
                    SELECT * FROM pec_legal_notification_transitions
                    WHERE tenant_id=? AND presidio_id=?
                    ORDER BY chain_index
                    """,
                    (self.tenant_id, presidio_id),
                ).fetchall()
            ]
        previous_hash = GENESIS_HASH
        previous_status = ""
        for index, row in enumerate(rows):
            if int(row.get("chain_index") or 0) != index + 1:
                return {"ok": False, "entries": len(rows), "brokenAt": index}
            if str(row.get("previous_status") or "") != previous_status:
                return {"ok": False, "entries": len(rows), "brokenAt": index}
            if str(row.get("prev_hash") or "") != previous_hash:
                return {"ok": False, "entries": len(rows), "brokenAt": index}
            payload = self._transition_payload(
                transition_id=str(row["id"]),
                presidio_id=presidio_id,
                previous_status=str(row.get("previous_status") or ""),
                next_status=str(row["next_status"]),
                actor=str(row["actor"]),
                chain_index=int(row["chain_index"]),
                reason=str(row.get("reason") or ""),
                evidence_json=canonical_json(json_load(row.get("evidence_json"), default={})),
                occurred_at=canonical_timestamp(row["occurred_at"]),
                prev_hash=previous_hash,
            )
            expected = sha256_text(canonical_json(payload))
            if expected != str(row.get("entry_hash") or ""):
                return {"ok": False, "entries": len(rows), "brokenAt": index}
            previous_hash = expected
            previous_status = str(row["next_status"])
        if rows and previous_status != str(presidio.get("status") or ""):
            return {"ok": False, "entries": len(rows), "brokenAt": len(rows)}
        return {"ok": True, "entries": len(rows), "head": previous_hash}
