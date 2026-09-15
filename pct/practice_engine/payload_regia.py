"""I blocchi del presidio come li legge l'interfaccia: voci, documenti, cronologia.

Trasformazioni pure dal repository al payload. Lo stato di ogni voce viene da
`voci_checklist`, così l'interfaccia mostra ciò che i controlli hanno davvero
detto e non un'etichetta fissa.
"""

from __future__ import annotations

from typing import Any

from .voci_checklist import controlli_della_voce, stato_voce


def _checklist_payload(rows: list[Any], results: list[Any], *, in_deposito: bool = True, motivo_rinvio: str = "") -> list[dict[str, Any]]:
    """Ogni voce con lo stato dei propri controlli: completata quando sono verdi.

    Prima una voce obbligatoria restava «da completare» per sempre, perché
    nessun controllo le era collegato: il presidio non si completava mai e la
    percentuale restava bassa anche a fascicolo in ordine.
    """
    payload = []
    for item in rows:
        esito = stato_voce(item, results, in_deposito=in_deposito, motivo_rinvio=motivo_rinvio)
        payload.append(
            {
                "id": item.id,
                "key": item.key,
                "label": item.label,
                "required": item.required,
                "blocking": item.blocking,
                "status": esito["stato"],
                "measured": esito["misurabile"],
                "controls": list(controlli_della_voce(item)),
                "message": esito["messaggio"] or (item.message or "Controllo operativo da presidiare."),
                "suggestedAction": esito["azione"] or (item.suggested_action or "Completa il requisito quando applicabile."),
                "source": item.source,
            }
        )
    return payload

def _slots_payload(slots: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": slot.id,
            "slotKey": slot.slot_key,
            "label": slot.label,
            "type": slot.type,
            "required": slot.required,
            "blocking": slot.blocking,
            "documentId": slot.document_id,
            "status": slot.status,
            "validators": list(slot.validators),
            "lastValidationAt": slot.last_validation_at,
            "message": slot.message or ("Documento richiesto mancante." if slot.required and not slot.document_id else ""),
            "suggestedAction": slot.suggested_action or ("Carica o collega il documento richiesto." if slot.required and not slot.document_id else ""),
            "sortOrder": slot.sort_order,
            "linkAction": "",
            "validateAction": "",
        }
        for slot in slots
    ]

def _timeline_payload(events: list[Any], receipts: list[Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "id": event.id,
            "type": event.event_type,
            "status": event.status,
            "message": event.message,
            "createdAt": event.created_at,
            "evidenceRef": event.evidence_ref,
        }
        for event in events
    ]
    if not rows and receipts:
        rows.extend(
            {
                "id": receipt.id,
                "type": receipt.receipt_type,
                "status": receipt.status,
                "message": receipt.message,
                "createdAt": receipt.imported_at,
                "evidenceRef": receipt.id,
            }
            for receipt in receipts
        )
    return rows


__all__ = ["_checklist_payload", "_slots_payload", "_timeline_payload"]
