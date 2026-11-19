from __future__ import annotations

from hashlib import sha256
from typing import Any

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


def _notification_document_role(fascicolo_id: str, document: dict[str, Any]) -> tuple[str, str]:
    """Confronta il ruolo del fascicolo con il frontespizio già letto, per impronta."""
    from pct.ragionamento.testo import rg_frontespizio, rg_normale
    from web.helpers import get_fascicoli
    from web.services.document_intelligence_runtime import build_document_ai_repository, document_ai_tenant_id
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    fascicolo = get_fascicoli().get(fascicolo_id)
    expected = rg_normale(getattr(fascicolo, "numero_rg", ""), getattr(fascicolo, "anno_rg", ""))
    if not expected:
        return "", ""
    hashes = {document.get("content_sha256"), document.get("outer_sha256")} - {None, ""}
    if not hashes:
        return expected, ""
    registro = registro_corrente(sola_lettura=True)
    oggetto = registro.oggetto(tenant_corrente(), fascicolo_id, "documento", document["fascicolo_document_id"])
    if not oggetto or not oggetto.presente or not hashes.intersection({oggetto.sha256, oggetto.sha256_archivio}):
        return expected, ""
    hashes.add(oggetto.sha256)
    repo = build_document_ai_repository()
    tenant = document_ai_tenant_id()
    for record in repo.list_documents(tenant, fascicolo_id):
        if record.sha256 not in hashes or not record.current_version_id:
            continue
        extraction = repo.get_extracted_text(tenant, fascicolo_id, record.id, record.current_version_id)
        role = rg_frontespizio(getattr(extraction, "text", "") or "")
        if role:
            return expected, role
    return expected, ""


def _rettifica_fonte_di_altro_ruolo(repo, audit, row, documents, recipients, actor) -> bool:
    if row["status"] not in {"DETECTED", "NEEDS_REVIEW", "ORIGINAL_TO_ACQUIRE", "ORIGINAL_ACQUIRED"} or row.get("confirmed_at"):
        return False
    if any(
        any(recipient.get(field) for field in ("sent_message_id", "rac_message_id", "rdac_message_id", "failure_message_id"))
        for recipient in recipients
    ):
        return False
    originals = [
        doc for doc in documents
        if doc.get("document_role") == "portal_original" and doc.get("authoritative") and doc.get("fascicolo_document_id")
    ]
    if len(originals) != 1 or any(doc.get("document_role") not in {"portal_original", "office_pec_copy"} for doc in documents):
        return False
    expected, found = _notification_document_role(row["fascicolo_id"], originals[0])
    if not expected or not found or found == expected:
        return False

    from pct.pec_pipeline import extract_rg_candidates
    from pct.ragionamento.testo import rg_normale

    copies = {doc.get("content_sha256") for doc in documents if doc.get("document_role") == "office_pec_copy"} - {None, ""}
    message_id = str(row.get("source_message_id") or "")
    if len(copies) != 1 or not message_id:
        return False
    with audit.connect() as conn:
        parsed = audit.latest_parsed_row(conn, message_id)
        if parsed is None:
            return False
        attachments = audit.attachment_rows(conn, message_id, parsed["id"])
    matches = [a for a in attachments if a["sha256"] in copies]
    if len(matches) != 1:
        return False
    roles = {rg_normale(rg) for rg in extract_rg_candidates(matches[0]["ocr_text"][:1500])} - {""}
    if roles != {found}:
        return False
    result = repo.transition(
        row["id"], PresidioStatus.CANCELLED, actor=actor, expected_status=row["status"],
        reason=f"Il provvedimento e l’allegato della PEC riguardano il R.G. {found}. Il fascicolo ha R.G. {expected}.",
        evidence={"source": "frontespizio_e_allegato_pec", "expected_rg": expected, "document_rg": found,
                  "attachment_sha256": matches[0]["sha256"], "document_id": originals[0]["fascicolo_document_id"],
                  "source_message_id": message_id},
        idempotency_key=f"rettifica-ruolo:{matches[0]['sha256']}:{expected}",
    )
    return bool(result.inserted)


def reconcile_presidio_with_fascicolo_notification_proof(
    repo: Any,
    presidio_id: str,
    *,
    actor: str,
    idempotency_prefix: str = "fascicolo-proof-deposited",
) -> dict[str, Any]:
    """Allinea il presidio avanzato alla prova notifica già presente nel fascicolo."""

    from web.services.notification_presidia_payloads import _detail_rows
    from web.services.pec_pipeline_runtime import repository_for_current_request

    row, documents, recipients = _detail_rows(repo, presidio_id)
    current_status = str(row.get("status") or "")
    if current_status == PresidioStatus.PROOF_DEPOSITED.value:
        return {"ok": True, "changed": False, "status": current_status, "reason": "already_proof_deposited"}
    if current_status not in _PROOF_RECONCILIABLE_STATUSES:
        return {"ok": True, "changed": False, "status": current_status, "reason": "status_not_reconciliable"}

    fascicolo_id = str(row.get("fascicolo_id") or "").strip()
    if not fascicolo_id:
        return {"ok": True, "changed": False, "status": current_status, "reason": "missing_fascicolo_id"}

    try:
        audit = repository_for_current_request()
        if _rettifica_fonte_di_altro_ruolo(repo, audit, row, documents, recipients, str(actor or "sistema")):
            return {"ok": True, "changed": True, "status": "CANCELLED", "reason": "another_docket"}
        proof = audit._notification_complete_proof_from_fascicolo(
            fascicolo_id=fascicolo_id,
            source_effective_at=row.get("source_effective_at"),
            source_message_id=str(row.get("source_message_id") or ""),
            candidate_documents=documents,
            candidate_recipients=[{**recipient, "required": bool(recipient["required"])} for recipient in recipients],
            require_deposit=True,
        )
    except Exception as exc:
        return {
            "ok": False,
            "changed": False,
            "status": current_status,
            "reason": "fascicolo_relata_unavailable",
            "error": str(exc),
        }

    deposit_ids = proof.get("proof_deposit_ids") or []
    if not proof.get("complete_proof") or not deposit_ids:
        return {
            "ok": True,
            "changed": False,
            "status": current_status,
            "reason": "specific_notification_without_deposited_proof",
        }

    signature = sha256("|".join((str(proof["notification_id"]), *deposit_ids)).encode()).hexdigest()[:24]
    evidence_key = f"{idempotency_prefix}:{fascicolo_id}:{signature}"
    system_notification = "La prova della stessa notifica è già depositata nel fascicolo."
    repo.append_evidence(
        presidio_id,
        {
            "evidence_key": evidence_key,
            "evidence_type": "document",
            "source_type": "fascicolo",
            "source_id": deposit_ids[0],
            "text_excerpt": system_notification,
            "source_locator": f"/fascicoli/{fascicolo_id}/documenti/{deposit_ids[0]}/visualizza",
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
            "notification_id": proof["notification_id"],
            "proof_deposit_document_ids": deposit_ids,
            "act_binding": proof["act_binding"],
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
