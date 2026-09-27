"""Payload JSON del link di pagamento per la pagina React.

Mai chiavi o segreti dei gestori (Stripe, PayPal, Satispay, SumUp): solo
importo, descrizione, metodi attivi e, per il bonifico, le coordinate che il
cliente deve usare.
"""

from __future__ import annotations

from typing import Any

from pct.formatting import format_date_it, format_euro_it
from web.services.pagamenti_link_azioni import STATO_PAGATO, VistaLink, studio_nome


def _testo(valore: Any) -> str:
    return "" if valore is None else str(valore)


def _importo(lp: Any) -> dict[str, str]:
    return {"importo": format_euro_it(lp.importo), "importo_cifra": f"{float(lp.importo or 0):.2f}", "valuta": _testo(lp.valuta or "EUR")}


def _nome_cliente(id_cliente: str) -> str:
    from web.helpers import get_clienti

    try:
        cliente = get_clienti().get(id_cliente)
    except Exception:
        return ""
    return _testo(getattr(cliente, "nome_completo", "")) if cliente else ""


def payload_vista(vista: VistaLink, gp) -> dict[str, Any]:
    """Pagina di pagamento: checkout, già pagato oppure link scaduto."""
    payload: dict[str, Any] = {"ok": vista.vista != "scaduto", "vista": vista.vista, "studio_nome": studio_nome()}
    if vista.vista == "scaduto":
        payload.update({
            "code": "link_non_valido",
            "message": "Questo link di pagamento non è più valido o è scaduto. Contatta lo studio per richiederne uno nuovo.",
        })
        return payload
    lp = vista.link
    payload.update(_importo(lp))
    payload["descrizione"] = _testo(lp.descrizione)
    if vista.vista == "gia_pagato":
        payload.update({"data_pagamento": format_date_it(lp.pagato_il), "metodo": _testo(lp.provider_usato)})
        return payload
    payload.update({
        "scadenza": format_date_it(lp.scade_il),
        "cliente": _nome_cliente(lp.id_cliente),
        "provider_attivi": list(gp.config.provider_attivi()),
    })
    return payload


def coordinate_bonifico(gp) -> dict[str, str] | None:
    if "bonifico" not in gp.config.provider_attivi():
        return None
    cfg = gp.config.bonifico
    return {
        "intestazione": _testo(cfg.intestazione),
        "iban": _testo(cfg.iban),
        "banca": _testo(cfg.banca),
        "note_aggiuntive": _testo(cfg.note_aggiuntive),
    }


def payload_esito(lp: Any, provider: str, gp) -> dict[str, Any]:
    """Pagina di esito: pagamento ricevuto, coordinate del bonifico o attesa."""
    provider = _testo(provider)
    if provider == "bonifico":
        vista = "bonifico"
    elif lp.stato == STATO_PAGATO:
        vista = "pagato"
    else:
        vista = "atteso"
    payload: dict[str, Any] = {
        "ok": True,
        "vista": vista,
        "studio_nome": studio_nome(),
        **_importo(lp),
        "descrizione": _testo(lp.descrizione),
        "causale": _testo(lp.descrizione) or "Pagamento parcella",
        "metodo": _testo(lp.provider_usato) or provider,
        "id_transazione": _testo(lp.provider_tx_id),
        "data_pagamento": format_date_it(lp.pagato_il),
    }
    if vista == "bonifico":
        payload["bonifico"] = coordinate_bonifico(gp)
    return payload


__all__ = ["coordinate_bonifico", "payload_esito", "payload_vista"]
