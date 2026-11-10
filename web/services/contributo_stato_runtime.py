"""Lo stato del contributo unificato di un fascicolo, con gli stessi dati per tutti i pannelli.

La regola è in ``pct.contributo_unificato_stato``; qui si raccolgono, senza leggere documenti, la voce economica
del fascicolo (quella proiettata dall'archivio delle letture, come nel presidio economico) e le voci del catalogo
documentale «contributo unificato / pagamento» ed «esenzione». Card della regia, finestra del controllo
economico, conto economico e quadro del fascicolo chiamano tutti ``stato_contributo_fascicolo`` o
``applica_stato_contributo``: per questo dicono la stessa cosa.

Base normativa: art. 13 e art. 9, comma 1-bis, D.P.R. 115/2002.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def href_documento(fascicolo_id: str, documento_id: str) -> str:
    return f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(documento_id, safe='')}/visualizza"


def documenti_contributo(fascicolo: Any) -> list[dict[str, Any]]:
    """Le voci del catalogo sul contributo unificato, solo per i documenti presenti nel fascicolo."""
    from web.services.document_intelligence_runtime import build_document_ai_repository, document_ai_tenant_id

    fid = _testo(getattr(fascicolo, "id", ""))
    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "") or getattr(d, "nome_file", ""))
            for d in getattr(fascicolo, "documenti", []) or []}
    try:
        voci = build_document_ai_repository().list_contributo_labels(document_ai_tenant_id(), fid)
    except Exception as exc:  # catalogo non pronto: lo stato resta deciso dalla voce economica
        logger.debug("Catalogo del contributo non disponibile per %s: %s", fid, exc)
        return []
    risultato = []
    for documento_id, etichetta, stato in voci:
        if documento_id not in nomi:
            continue  # allegati PEC: la fonte si apre dalla comunicazione
        risultato.append({"etichetta": etichetta, "id": documento_id, "nome": nomi[documento_id] or etichetta,
                          "href": href_documento(fid, documento_id), "confermato": stato in {"confirmed", "overridden"}})
    return risultato


def _documento_della_voce(fascicolo: Any, voce: Mapping[str, Any]) -> str:
    documento_id = _testo(voce.get("documento_id") or voce.get("documentoId"))
    documenti = list(getattr(fascicolo, "documenti", []) or [])
    if documento_id and any(_testo(getattr(d, "id", "")) == documento_id for d in documenti):
        return documento_id
    nomi = {_testo(voce.get(campo)) for campo in ("documento_fonte", "documentoFonte", "documentoFonteRaw")} - {""}
    return next((_testo(getattr(d, "id", "")) for d in documenti if _testo(getattr(d, "nome", "")) in nomi), "")


_AUTOMATICI = ("import", "automatic", "automatico", "document ai", "lex", "scheduler", "iusentra", "archivio delle letture")


def decisione_dell_avvocato(voce: Mapping[str, Any]) -> bool:
    """Vero se la voce è stata registrata o cambiata da una persona dello studio, non da una lettura automatica.

    Diversamente dal presidio economico, «non previsto» senza importo qui conta: è proprio la decisione
    «contributo non dovuto» o «esente» presa dall'avvocato.
    """
    autori = [_testo(voce.get("updated_by") or voce.get("updatedBy"))]
    for riga in voce.get("history") or voce.get("storico") or []:
        if isinstance(riga, Mapping):
            autori.append(_testo(riga.get("by") or riga.get("updated_by")))
    return any(a and not any(m in a.casefold() for m in _AUTOMATICI) for a in autori)


def voce_contributo(fascicolo: Any, voce: Mapping[str, Any]) -> dict[str, Any]:
    """La voce economica pronta per la regola: documento fonte risolto e decisione dell'avvocato riconosciuta."""
    fid = _testo(getattr(fascicolo, "id", ""))
    documento_id = _documento_della_voce(fascicolo, voce)
    return {
        "status": _testo(voce.get("status") or voce.get("stato")).lower(),
        "importo": voce.get("importo"),
        "documento_fonte": _testo(voce.get("documento_fonte") or voce.get("documentoFonteRaw") or voce.get("documentoFonte")),
        "documento_id": documento_id,
        "href": href_documento(fid, documento_id) if documento_id else "",
        "richiedeConferma": bool(voce.get("richiedeConferma")),
        "importiLetti": list(voce.get("importiLetti") or []),
        "manuale": decisione_dell_avvocato(voce),
    }


def voce_corrente(fascicolo: Any) -> dict[str, Any]:
    """La voce «contributo_unificato» come la vede il presidio economico (archivio delle letture già proiettato)."""
    from web.services.react_fascicoli_bridge import _payment_source_for_kind, _payments_with_automatic_sources

    pagamenti = _payments_with_automatic_sources(fascicolo, getattr(fascicolo, "pagamenti", {}) or {}, enabled=False)
    return _payment_source_for_kind(pagamenti, "contributo_unificato")


def stato_contributo_fascicolo(fascicolo: Any, voce: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from pct.contributo_unificato_stato import stato_contributo

    grezza = voce if voce is not None else voce_corrente(fascicolo)
    return stato_contributo(voce_contributo(fascicolo, grezza or {}), documenti_contributo(fascicolo))


def applica_stato_contributo(items: dict[str, dict[str, Any]], fascicolo: Any, voce: Mapping[str, Any]) -> None:
    """Card e finestra del presidio economico: etichetta, tono e fonti dallo stato unico del contributo."""
    from pct.contributo_unificato_stato import solo_fonti_del_contributo

    item = items.get("contributo_unificato")
    if not isinstance(item, dict):
        return
    try:
        stato = stato_contributo_fascicolo(fascicolo, voce)
    except Exception as exc:  # il presidio resta consultabile con l'etichetta della voce
        logger.warning("Stato del contributo non calcolato per %s: %s", getattr(fascicolo, "id", ""), exc)
        return
    item["statoContributo"] = stato
    item["statusLabel"] = stato["etichetta"]
    item["tone"] = stato["tono"]
    # «Verifiche e fonti del contributo unificato»: solo ricevute, note che lo riportano e autocertificazioni.
    item["fontiVerifica"] = solo_fonti_del_contributo(item.get("fontiVerifica") or [])


__all__ = ["applica_stato_contributo", "documenti_contributo", "href_documento", "stato_contributo_fascicolo",
           "decisione_dell_avvocato", "voce_contributo", "voce_corrente"]
