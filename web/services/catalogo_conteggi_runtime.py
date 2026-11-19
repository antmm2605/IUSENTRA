"""Gli stati del catalogo documentale di un fascicolo, letti una volta e contati con una sola regola.

Il pannello «Catalogazione documentale», il quadro del fascicolo e la Lettura (card Documentazione) usano
``pct.document_intelligence.certezza_lettura.stato_catalogo`` e ``riepilogo_catalogo``: una proposta riconosciuta con
certezza dal contenuto è «catalogata in automatico» ovunque, e i documenti sono sempre catalogati + da verificare + in
attesa. Le bozze preparate dal software non sono documenti del fascicolo e restano fuori dai conteggi.
Sola lettura del catalogo SQL: nessuna pipeline, nessuna rilettura dei documenti.
"""

from __future__ import annotations

from typing import Any


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def stato_assegnazione(assegnazione: Any, con_prova: set[str]) -> str:
    from pct.document_intelligence.certezza_lettura import stato_catalogo

    return stato_catalogo(getattr(assegnazione, "status", ""), getattr(assegnazione, "confidence", 0),
                          ha_prova=_testo(getattr(assegnazione, "id", "")) in con_prova,
                          automatico=bool((getattr(assegnazione, "metadata", None) or {}).get("automatic_classification")))


def voci_con_prova(fascicolo_id: str) -> set[str]:
    from web.services.document_intelligence_runtime import build_document_ai_repository, document_ai_tenant_id

    try:
        return build_document_ai_repository().catalog_assignment_ids_with_evidence(document_ai_tenant_id(), fascicolo_id)
    except Exception:
        return set()


def documenti_del_fascicolo(fascicolo: Any) -> list[Any]:
    """I documenti del fascicolo senza le bozze dello studio."""
    from pct.bozze_passi.modello import e_bozza_del_software

    return [d for d in getattr(fascicolo, "documenti", []) or [] if not e_bozza_del_software(d)]


def stati_documenti(fascicolo: Any) -> dict[str, str | None]:
    """Lo stato del catalogo per ogni documento del fascicolo (None = non ancora catalogato), bozze escluse."""
    from web.services.react_fascicoli_bridge import _sql_document_catalog_by_id

    fid = _testo(getattr(fascicolo, "id", ""))
    assegnazioni = _sql_document_catalog_by_id(fascicolo)
    con_prova = voci_con_prova(fid) if assegnazioni else set()
    stati: dict[str, str | None] = {}
    for documento in documenti_del_fascicolo(fascicolo):
        identificativo = _testo(getattr(documento, "id", ""))
        assegnazione = assegnazioni.get(identificativo)
        stati[identificativo] = stato_assegnazione(assegnazione, con_prova) if assegnazione is not None else None
    return stati


def riepilogo_fascicolo(fascicolo: Any) -> dict[str, int]:
    from pct.document_intelligence.certezza_lettura import riepilogo_catalogo

    return riepilogo_catalogo(stati_documenti(fascicolo).values())


__all__ = ["documenti_del_fascicolo", "riepilogo_fascicolo", "stati_documenti", "stato_assegnazione", "voci_con_prova"]
