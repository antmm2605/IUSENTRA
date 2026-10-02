"""Rettifica auditata dei soli candidati automatici nati da ricevute di deposito."""

import email
from email import policy

from .receipt_policy import is_transport_receipt

REASON = ("Ricevuta di trasporto di un deposito telematico, non un nuovo atto da notificare. "
          "PEC e ricevute restano conservate nel deposito e nell'audit.")


def reconcile_deposit_receipts(repo, *, apply: bool = False) -> dict:
    with repo.connection() as conn:
        rows = [repo._row(row) for row in conn.execute(
            "SELECT p.*, m.original_mime FROM pec_legal_notification_presidia p "
            "JOIN pec_messages m ON m.id=p.source_message_id AND m.tenant_id=p.tenant_id "
            "WHERE p.tenant_id=? AND p.status IN ('DETECTED','NEEDS_REVIEW')",
            (repo.tenant_id,),
        ).fetchall()]
    candidates, corrected = [], []
    for row in rows:
        if not is_transport_receipt(row):
            continue
        raw = row.get("original_mime")
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if not raw:
            continue
        message = email.message_from_bytes(bytes(raw), policy=policy.default)
        subject = str(message.get("subject") or "").upper()
        if "DEPOSITO TELEMATICO" not in subject:
            continue
        if not subject.startswith(("ACCETTAZIONE:", "CONSEGNA:", "AVVISO DI MANCATA CONSEGNA:")):
            continue
        pid = str(row["id"])
        candidates.append(pid)
        if apply:
            repo.transition(pid, "NOT_REQUIRED", actor="verificatore-ricevute-deposito",
                reason=REASON, evidence={"source_message_id": row["source_message_id"],
                    "rule": "transport-receipt-is-not-notification-v1", "original_mime_checked": True},
                expected_status=row["status"], idempotency_key="deposit-receipt-reconciliation-v1")
            if not repo.verify_transition_chain(pid)["ok"]:
                raise RuntimeError("Verifica della catena audit fallita")
            corrected.append(pid)
    return {"source_of_truth": repo.backend_kind, "candidates": candidates, "corrected": corrected}
