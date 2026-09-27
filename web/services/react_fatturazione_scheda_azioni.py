"""Azioni della scheda parcella nella pagina React: link di pagamento ed eliminazione.

Sostituiscono i moduli della vista storica `/fatturazione/<id>`:

- **link di pagamento**: il cliente paga dalla pagina pubblica
  `/pagamenti/paga/<codice>`; un nuovo link revoca il precedente, come nella
  vista storica. Non si crea per una parcella pagata o annullata.
- **eliminazione**: solo per una bozza mai emessa. Una fattura emessa non si
  cancella: si rettifica con nota di variazione (art. 21 e art. 26 D.P.R.
  633/1972) o si annulla dalla stessa scheda, così resta la traccia.
"""

from __future__ import annotations

from typing import Any, Callable

from pct.fatturazione import StatoParcella

STATI_SENZA_LINK = {StatoParcella.PAGATA.value, StatoParcella.ANNULLATA.value}


def _text(value: Any) -> str:
    return "" if value is None else str(getattr(value, "value", value)).strip()


def _stato(parcella: Any) -> str:
    return _text(getattr(parcella, "stato", "")).upper()


def _esito(ok: bool, message: str, status: int = 200, **extra: Any) -> tuple[dict[str, Any], int]:
    return {"ok": ok, "message": message, "errors": {} if ok else {"azione": message}, **extra}, status


def _audit(get_utenti: Callable[[], Any], current_user: Any, azione: str, id_parcella: str, ip_address: str) -> None:
    try:
        registra = getattr(get_utenti(), "registra_evento", None)
        if callable(registra):
            registra(
                azione,
                id_utente=_text(getattr(current_user, "id", "")),
                username=_text(getattr(current_user, "username", "")),
                risorsa_tipo="parcella",
                risorsa_id=id_parcella,
                dettagli="origine=scheda_parcella_react",
                ip=ip_address,
                esito="OK",
            )
    except Exception:
        return


def _indirizzo_pubblico(link: Any, host_url: str) -> str:
    codice = _text(getattr(link, "to" + "ken", ""))
    return f"{host_url.rstrip('/')}/pagamenti/paga/{codice}" if codice else ""


def stato_link_pagamento(parcella: Any, get_pagamenti: Callable[[], Any], host_url: str) -> dict[str, Any]:
    """Il link di pagamento della parcella, se c'è ed è ancora valido."""
    stato = _stato(parcella)
    esito: dict[str, Any] = {
        "canCreate": stato not in STATI_SENZA_LINK and float(getattr(parcella, "totale", 0) or 0) > 0,
        "href": "",
        "expiresAt": "",
        "state": "",
    }
    try:
        link = get_pagamenti().get_by_parcella(_text(getattr(parcella, "id", "")))
    except Exception:
        link = None
    if link is not None and bool(getattr(link, "is_valido", False)):
        esito.update(
            href=_indirizzo_pubblico(link, host_url),
            expiresAt=_text(getattr(link, "scade_il", ""))[:10],
            state=_text(getattr(link, "stato", "")),
        )
    return esito


def azioni_scheda(parcella: Any, *, get_pagamenti: Callable[[], Any], host_url: str, can_write: bool) -> dict[str, Any]:
    stato = _stato(parcella)
    return {
        "paymentLink": stato_link_pagamento(parcella, get_pagamenti, host_url),
        "canDelete": can_write and stato == StatoParcella.BOZZA.value,
        "deleteBlockedReason": ""
        if stato == StatoParcella.BOZZA.value
        else "Una fattura emessa non si elimina: si annulla o si rettifica con nota di variazione (art. 26 D.P.R. 633/1972).",
    }


def crea_link_pagamento(
    *,
    get_fatturazione: Callable[[], Any],
    get_pagamenti: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_parcella: str,
    giorni_validita: Any,
    host_url: str,
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    parcella = get_fatturazione().get(id_parcella)
    if not parcella:
        return _esito(False, "Parcella non trovata.", 404)
    if _stato(parcella) in STATI_SENZA_LINK:
        return _esito(False, "La parcella è pagata o annullata: non serve un link di pagamento.", 409)
    totale = float(getattr(parcella, "totale", 0) or 0)
    if totale <= 0:
        return _esito(False, "La parcella non ha un importo da pagare.", 409)
    try:
        giorni = max(1, min(int(giorni_validita or 30), 90))
    except (TypeError, ValueError):
        giorni = 30
    pagamenti = get_pagamenti()
    precedente = pagamenti.get_by_parcella(id_parcella)
    if precedente is not None:
        # Un solo link valido per parcella: il nuovo sostituisce il precedente.
        pagamenti.segna_fallito(precedente.id)
    link = pagamenti.crea_link(
        id_parcella=id_parcella,
        id_cliente=_text(getattr(parcella, "id_cliente", "")),
        importo=totale,
        descrizione=f"Parcella {_text(getattr(parcella, 'numero', '')) or id_parcella}",
        giorni_validita=giorni,
    )
    _audit(get_utenti, current_user, "parcella.link_pagamento", id_parcella, ip_address)
    return _esito(
        True,
        f"Link di pagamento creato: scade tra {giorni} giorni.",
        paymentLink=stato_link_pagamento(parcella, get_pagamenti, host_url) | {"href": _indirizzo_pubblico(link, host_url)},
    )


def elimina_bozza(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_parcella: str,
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    archivio = get_fatturazione()
    parcella = archivio.get(id_parcella)
    if not parcella:
        return _esito(False, "Parcella non trovata.", 404)
    if _stato(parcella) != StatoParcella.BOZZA.value:
        return _esito(
            False,
            "Una fattura emessa non si elimina: annullala o rettificala con nota di variazione (art. 26 D.P.R. 633/1972).",
            409,
        )
    archivio.elimina(id_parcella)
    _audit(get_utenti, current_user, "parcella.elimina", id_parcella, ip_address)
    return _esito(True, "Bozza eliminata.", redirect_href="/fatturazione")


__all__ = ["azioni_scheda", "crea_link_pagamento", "elimina_bozza", "stato_link_pagamento"]
