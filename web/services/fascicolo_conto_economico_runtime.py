"""Conto economico del fascicolo per la vista economica: raccoglie i dati già letti e li passa al modulo di dominio.

Fonti consultate, senza rileggere documenti nella richiesta:
- crediti da sentenza: eventi del controllo economico delle sentenze della causa (le sentenze di altri procedimenti,
  allegate come precedenti, sono escluse da `build_sentenza_economic_payload`), con il documento da cui nascono;
- contributo unificato: documenti classificati dal catalogo come ricevuta di versamento o autocertificazione;
- parcella, spese, anticipazioni e incassi: documenti economici del fascicolo e registro degli incassi.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

_CREDITI = {"apri_credito_cliente": False, "apri_credito_avvocato_antistatario": True}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def _href_documento(fascicolo_id: str, documento_id: str) -> str:
    return f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(documento_id, safe='')}/visualizza"


def crediti_da_sentenza(fascicolo_id: str) -> list[dict[str, Any]]:
    from web.services.registro_letture_runtime import registro_corrente
    from web.services.sentenza_economic_runtime import _tenant_id, build_sentenza_economic_payload, fonte_audit

    payload = build_sentenza_economic_payload(fascicolo_id)
    if not payload.get("ok"):
        return []
    audits = {str(a["id"]): a for a in payload.get("audits") or []}
    inventario = registro_corrente().oggetti(_tenant_id(), fascicolo_id)
    crediti = []
    for evento in payload.get("eventi") or []:
        tipo = evento.get("event_type")
        if tipo not in _CREDITI or evento.get("status") not in {"to_review", "confirmed"}:
            continue
        audit = audits.get(str(evento.get("source_id") or ""))
        fonte = fonte_audit(audit, inventario, fascicolo_id) if audit else None
        crediti.append({"importo": evento.get("amount"), "distrazione": _CREDITI[tipo], "confermato": evento.get("status") == "confirmed",
                        "fonti": [{"label": fonte["label"], "href": fonte["href"], "norma": "sentenza della causa"}] if fonte else []})
    return crediti


def documenti_contributo(fascicolo: Any) -> list[dict[str, str]]:
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

    fid = _testo(getattr(fascicolo, "id", ""))
    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "") or getattr(d, "nome_file", "")) for d in getattr(fascicolo, "documenti", []) or []}
    risultato = []
    for assegnazione in build_document_ai_service().repository.list_catalog_assignments(document_ai_tenant_id(), fid):
        etichetta = _testo(getattr(assegnazione, "document_label", ""))
        documento_id = _testo(getattr(assegnazione, "document_id", ""))
        if not etichetta.lower().startswith("contributo unificato") or _testo(getattr(assegnazione, "status", "")) == "rejected":
            continue
        if documento_id not in nomi:
            continue  # allegati PEC: la fonte si apre dalla comunicazione
        risultato.append({"etichetta": etichetta, "nome": nomi[documento_id] or etichetta, "href": _href_documento(fid, documento_id),
                          "confermato": _testo(getattr(assegnazione, "status", "")) in {"confirmed", "overridden"}})
    return risultato


def parcelle_del_fascicolo(fascicolo_id: str) -> list[dict[str, Any]]:
    from pct.parcella_incassi_views import balance_amount, balances_for_invoices
    from web.helpers import get_fatturazione

    gestione = get_fatturazione()
    parcelle = list(gestione.per_fascicolo(fascicolo_id) or [])
    saldi = balances_for_invoices(getattr(gestione, "_studio_db", None), {p.id: p for p in parcelle})
    righe = []
    for p in parcelle:
        stato = _testo(getattr(p.stato, "value", p.stato)).upper()
        documento = (p.dati_personalizzati or {}).get("document") if isinstance(p.dati_personalizzati, dict) else {}
        operativo = _testo((documento or {}).get("documento_operativo")).upper() or ("FATTURA" if stato in {"EMESSA", "PAGATA"} else "PROFORMA")
        try:
            incassato = balance_amount(p, saldi, "paid_cents", p.totale if stato == "PAGATA" else 0)
        except ValueError:
            incassato = 0
        ricevute = (saldi.get(p.id) or {}).get("receipts") or []
        data_pagamento = max((str(r.get("paid_on") or "") for r in ricevute), default="") or _testo(p.data_pagamento)
        righe.append({"id": p.id, "numero": p.numero, "stato": stato, "operativo": operativo, "totale": p.totale,
                      "onorari": p.totale_competenze, "spese": p.totale_spese_imponibili, "anticipazioni": p.totale_anticipazioni,
                      "incassato": incassato, "data_pagamento": data_pagamento, "sdi_stato": _testo(p.sdi_stato)})
    return righe


def conto_economico_fascicolo(fascicolo_id: str) -> dict[str, Any]:
    from pct.fascicolo_conto_economico import conto_economico
    from web.helpers import get_fascicoli

    fascicolo = get_fascicoli().get(fascicolo_id)
    if fascicolo is None:
        return {"ok": False, "message": "Fascicolo non trovato."}
    voci = dict(getattr(fascicolo, "pagamenti", {}) or {})
    for chiave in ("spese_esborsi", "fondo_spese", "contributo_unificato"):
        voce = dict(voci.get(chiave) or {})
        documento_id = _testo(voce.get("documento_id") or voce.get("documentoId")) or next(
            (_testo(d.id) for d in getattr(fascicolo, "documenti", []) or []
             if voce.get("documento_fonte") and _testo(getattr(d, "nome", "")) == _testo(voce.get("documento_fonte"))), "")
        if documento_id:
            voce["href"] = _href_documento(fascicolo_id, documento_id)
        voci[chiave] = voce
    risultato = conto_economico(voci=voci, crediti=crediti_da_sentenza(fascicolo_id),
                                documenti_contributo=documenti_contributo(fascicolo), parcelle=parcelle_del_fascicolo(fascicolo_id))
    return {"ok": True, "fascicoloId": fascicolo_id, **risultato}


__all__ = ["conto_economico_fascicolo", "crediti_da_sentenza", "documenti_contributo", "parcelle_del_fascicolo"]
