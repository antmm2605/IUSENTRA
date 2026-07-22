from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pct.pec_notification_presidio.models import PresidioStatus


_PROOF_RECONCILIABLE_STATUSES = {
    PresidioStatus.DETECTED.value,
    PresidioStatus.NEEDS_REVIEW.value,
    PresidioStatus.ORIGINAL_TO_ACQUIRE.value,
    PresidioStatus.ORIGINAL_ACQUIRED.value,
    PresidioStatus.NOTIFICATION_CONFIRMED.value,
    PresidioStatus.RECIPIENTS_TO_VERIFY.value,
    PresidioStatus.READY_FOR_RELATA.value,
    PresidioStatus.RELATA_DRAFTED.value,
    PresidioStatus.RELATA_SIGNED.value,
    PresidioStatus.READY_TO_SEND.value,
    PresidioStatus.SENT_WAITING_RAC.value,
    PresidioStatus.RAC_RECEIVED.value,
    PresidioStatus.PARTIAL_DELIVERY.value,
    PresidioStatus.DELIVERY_COMPLETE.value,
    PresidioStatus.PROOF_TO_DEPOSIT.value,
    PresidioStatus.LEGACY_REVIEW_REQUIRED.value,
}


def _proof_signature(payload: Mapping[str, Any]) -> str:
    proof_documents = [
        {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or ""),
            "kind": str(item.get("kind") or ""),
            "status": str(item.get("status") or ""),
        }
        for item in payload.get("documents", []) or []
        if str(item.get("kind") or "") == "deposito_prova"
        or str(item.get("status") or "") == "depositato"
    ]
    if not proof_documents:
        proof_documents = [
            {
                "status": str(payload.get("status") or ""),
                "proofDepositDocuments": int(payload.get("proofDepositDocuments") or 0),
                "proofDocuments": int(payload.get("proofDocuments") or 0),
                "systemNotification": str(payload.get("systemNotification") or ""),
            }
        ]
    raw = json.dumps(proof_documents, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def reconcile_presidio_with_fascicolo_notification_proof(
    repo: Any,
    presidio_id: str,
    *,
    actor: str,
    idempotency_prefix: str = "fascicolo-proof-deposited",
) -> dict[str, Any]:
    """Allinea il presidio avanzato alla prova notifica già presente nel fascicolo."""

    row = repo.get_presidio(presidio_id)
    current_status = str(row.get("status") or "")
    if current_status == PresidioStatus.PROOF_DEPOSITED.value:
        return {"ok": True, "changed": False, "status": current_status, "reason": "already_proof_deposited"}
    if current_status not in _PROOF_RECONCILIABLE_STATUSES:
        return {"ok": True, "changed": False, "status": current_status, "reason": "status_not_reconciliable"}

    fascicolo_id = str(row.get("fascicolo_id") or "").strip()
    if not fascicolo_id:
        return {"ok": True, "changed": False, "status": current_status, "reason": "missing_fascicolo_id"}

    try:
        from web.helpers import get_fascicoli
        from web.services.react_fascicoli_bridge import _notification_relata

        fascicolo = get_fascicoli().get(fascicolo_id)
        if fascicolo is None:
            return {"ok": True, "changed": False, "status": current_status, "reason": "fascicolo_not_found"}
        relata = _notification_relata(fascicolo, [])
    except Exception as exc:
        return {
            "ok": False,
            "changed": False,
            "status": current_status,
            "reason": "fascicolo_relata_unavailable",
            "error": str(exc),
        }

    if str(relata.get("status") or "") != "prova_depositata":
        return {
            "ok": True,
            "changed": False,
            "status": current_status,
            "reason": "fascicolo_without_deposited_proof",
            "relata_status": str(relata.get("status") or ""),
        }

    signature = _proof_signature(relata)
    evidence_key = f"{idempotency_prefix}:{fascicolo_id}:{signature}"
    system_notification = str(
        relata.get("systemNotification")
        or "Notifica già eseguita e prova già depositata nel fascicolo: nessuna nuova notifica da preparare."
    )
    repo.append_evidence(
        presidio_id,
        {
            "evidence_key": evidence_key,
            "evidence_type": "document",
            "source_type": "fascicolo",
            "source_id": fascicolo_id,
            "text_excerpt": system_notification,
            "source_locator": str(relata.get("primaryHref") or f"/fascicoli/{fascicolo_id}#relata-notifica"),
            "confidence": 1.0,
        },
    )
    transition = repo.transition(
        presidio_id,
        PresidioStatus.PROOF_DEPOSITED,
        actor=str(actor or "sistema"),
        reason="Prova notifica già depositata nel fascicolo: nessuna nuova relata da preparare.",
        evidence={
            "source": "fascicolo_notification_relata",
            "fascicolo_id": fascicolo_id,
            "relata_status": str(relata.get("status") or ""),
            "proof_documents": int(relata.get("proofDocuments") or 0),
            "proof_deposit_documents": int(relata.get("proofDepositDocuments") or 0),
        },
        idempotency_key=evidence_key,
        expected_status=current_status,
    )
    return {
        "ok": True,
        "changed": bool(getattr(transition, "inserted", False)),
        "status": PresidioStatus.PROOF_DEPOSITED.value,
        "reason": "proof_deposited_from_fascicolo",
    }
