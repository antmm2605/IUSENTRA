"""Conferma in blocco delle proposte di catalogazione di un fascicolo.

Confermare una proposta significa attestare che la prova letta dal contenuto
è stata vista: la conferma massiva vale come attestazione per tutte le
proposte che una prova ce l'hanno, passa dalla stessa revisione tracciata
della conferma singola (audit «document_catalog.reviewed») e lascia da parte,
dicendolo, le proposte senza prova e i documenti già da verificare.
"""

from __future__ import annotations

from typing import Any

from web.services.document_intelligence_runtime import (
    assert_document_ai_fascicolo_current_tenant,
    build_document_ai_service,
    document_ai_tenant_id,
    resolve_document_catalog_assignment,
)

NOTA_CONFERMA_MASSIVA = "Conferma massiva delle proposte dal pannello Catalogazione documentale"


def conferma_proposte_catalogo(fascicolo_id: str, *, user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Conferma tutte le proposte con prova; restituisce i conteggi e gli esclusi con la ragione."""
    assert_document_ai_fascicolo_current_tenant(fascicolo_id)
    repository = build_document_ai_service().repository
    tenant_id = document_ai_tenant_id()
    assegnazioni = repository.list_catalog_assignments(tenant_id, str(fascicolo_id))
    confermate: list[dict[str, Any]] = []
    senza_prova: list[dict[str, Any]] = []
    errori: list[dict[str, Any]] = []
    for assegnazione in assegnazioni:
        if str(getattr(assegnazione, "status", "") or "") != "proposed":
            continue
        documento_id = str(getattr(assegnazione, "document_id", "") or "")
        etichetta = str(getattr(assegnazione, "document_label", "") or "")
        if not repository.list_catalog_evidence(getattr(assegnazione, "id", "")):
            senza_prova.append({"document_id": documento_id, "document_label": etichetta})
            continue
        try:
            resolve_document_catalog_assignment(
                str(fascicolo_id), documento_id, status="confirmed", note=NOTA_CONFERMA_MASSIVA,
                evidence_acknowledged=True, user_context=user_context,
            )
            confermate.append({"document_id": documento_id, "document_label": etichetta})
        except Exception as exc:  # una proposta che non si conferma non blocca le altre
            errori.append({"document_id": documento_id, "document_label": etichetta, "errore": str(exc)})
    return {
        "confermate": confermate,
        "senza_prova": senza_prova,
        "errori": errori,
        "message": _messaggio(len(confermate), len(senza_prova), len(errori)),
    }


def _messaggio(confermate: int, senza_prova: int, errori: int) -> str:
    if not confermate and not senza_prova and not errori:
        return "Nessuna proposta da confermare: il catalogo è già tutto confermato o da verificare."
    parti = [f"{confermate} propost{'a confermata' if confermate == 1 else 'e confermate'}"]
    if senza_prova:
        parti.append(f"{senza_prova} senza prova letta dal contenuto (restano proposte: correggile o aggiorna l'indice)")
    if errori:
        parti.append(f"{errori} non confermate per errore")
    return "; ".join(parti) + "."


__all__ = ["NOTA_CONFERMA_MASSIVA", "conferma_proposte_catalogo"]
