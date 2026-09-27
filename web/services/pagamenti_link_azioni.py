"""Link di pagamento del cliente (`/pagamenti/paga/<token>`): verifica e avvio.

Una sola logica per la pagina storica e per le API JSON della pagina React:
stato del link (valido, già pagato, scaduto), avvio del pagamento presso il
gestore scelto, verifica al ritorno dal gestore. I webhook restano nel
blueprint `pagamenti`: di qui prendono solo lo studio del link (più studi).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flask import current_app, g, request, session, url_for

from web.services.token_pubblici_tenant import (
    contesto_studio_mancante,
    multi_studio_attivo,
    risolvi_studio_da_slug,
    risolvi_studio_da_token,
)

STATO_PAGATO = "PAGATO"
STATO_ATTESO = "ATTESO"
PROVIDER_REDIRECT = {"stripe", "paypal", "satispay"}
MESSAGGIO_STRIPE_NON_AVVIATO = "Errore Stripe: pagamento non avviato. Riprova o scegli un altro metodo."

# Impronta del token -> studio (vedi token_pubblici_tenant).
_STUDIO_DEL_LINK: dict[str, str] = {}
# Impronta del riferimento del link (id inviato dal gestore nel webhook) -> studio.
_STUDIO_DEL_RIFERIMENTO: dict[str, str] = {}


@dataclass
class VistaLink:
    vista: str  # checkout | gia_pagato | scaduto
    link: Any = None
    status: int = 200


@dataclass
class EsitoAvvio:
    """Esito dell'avvio: redirect al gestore, widget SumUp, bonifico o errore.

    `messaggio` è il solo testo per il cliente: il dettaglio tecnico
    dell'errore del gestore resta nel log del server.
    """

    tipo: str
    url: str = ""
    checkout_id: str = ""
    messaggio: str = ""


def gestore_pagamenti():
    from web.helpers import get_pagamenti

    return get_pagamenti()


def studio_nome() -> str:
    return str(current_app.config.get("STUDIO_NOME", "IUSENTRA"))


# ------------------------------------------------------------------ studio del link

def _archivio_dello_studio(trovato):
    """Verifica per il resolver: l'archivio pagamenti dello studio candidato contiene il link."""
    def verifica(_studio, percorsi: dict[str, str]) -> bool:
        from pct.pagamenti import GestionePagamenti
        from web.services.storage_runtime import get_request_studio_db

        try:
            cartella = percorsi["PAGAMENTI_DIR"]
            gestore = GestionePagamenti(db_dir=cartella, studio_db=get_request_studio_db(cartella))
            return bool(trovato(gestore))
        except Exception:
            current_app.logger.warning("Pagamenti: archivio dello studio %s non leggibile", getattr(_studio, "slug", "-"))
            return False

    return verifica


def _link_nello_studio(token: str):
    return _archivio_dello_studio(lambda gestore: gestore.get_by_token(token) is not None)


def _riferimento_nello_studio(link_id: str):
    return _archivio_dello_studio(lambda gestore: any(lp.id == link_id for lp in gestore.tutti_link()))


def risolvi_studio_pagamento(token: str) -> None:
    """Imposta lo studio che ha creato il link (installazioni con più studi).

    Prima mancava: il link del cliente leggeva l'archivio pagamenti comune e,
    con più studi, risultava sempre scaduto.
    """
    risolvi_studio_da_token(token, verifica=_link_nello_studio(token), cache=_STUDIO_DEL_LINK, etichetta="Pagamenti")


def risolvi_studio_webhook(link_id: str) -> bool:
    """Studio del link annunciato da un webhook; True se la richiesta può proseguire.

    A studio singolo non cambia nulla (True: archivio e chiavi di sempre). Con
    più studi lo studio si cerca con il riferimento del link inviato dal
    gestore (metadata/custom_id/checkout_reference): il riferimento serve solo
    a scegliere lo studio, la firma o la conferma presso il gestore si
    verificano dopo, con le chiavi di quello studio. False: nessuno studio ha
    il link, il webhook non si può verificare e non si registra nulla.
    """
    if not multi_studio_attivo():
        return True
    link_id = str(link_id or "").strip()
    if link_id:
        risolvi_studio_da_token(
            link_id, verifica=_riferimento_nello_studio(link_id), cache=_STUDIO_DEL_RIFERIMENTO, etichetta="Webhook pagamenti"
        )
    return not contesto_studio_mancante()


def entra_studio_webhook(slug: str) -> bool:
    """Webhook con lo studio nell'indirizzo (`/webhooks/<gestore>/<slug>`), solo con più studi."""
    return risolvi_studio_da_slug(slug, etichetta="Webhook pagamenti")


def indirizzo_webhook(gestore: str) -> str:
    """Indirizzo del webhook del gestore: con più studi quello dello studio corrente."""
    slug = str(getattr(getattr(g, "tenant", None), "slug", "") or "") if multi_studio_attivo() else ""
    if slug:
        return url_for("pagamenti.webhook_studio", gestore=gestore, slug=slug)
    return url_for(f"pagamenti.webhook_{gestore}")


# ------------------------------------------------------------------ stato del link

def link_del_token(gp, token: str):
    if contesto_studio_mancante():
        return None
    return gp.get_by_token(token)


def vista_link(gp, token: str) -> VistaLink:
    lp = link_del_token(gp, token)
    if not lp:
        return VistaLink("scaduto", None, 410)
    if not lp.is_valido:
        if lp.stato == STATO_PAGATO:
            return VistaLink("gia_pagato", lp, 200)
        return VistaLink("scaduto", None, 410)
    return VistaLink("checkout", lp, 200)


def aggiorna_parcella_pagata(id_parcella: str, metodo: str) -> None:
    """Segna la parcella come PAGATA nel modulo fatturazione."""
    try:
        from pct.fatturazione import StatoParcella
        from web.helpers import get_fatturazione

        get_fatturazione().cambia_stato(id_parcella, StatoParcella.PAGATA, metodo_pagamento=metodo)
    except Exception:
        pass


# ------------------------------------------------------------------ avvio

def _url_esterno(url: Any) -> str:
    valore = str(url or "").strip()
    return valore if valore.startswith("https://") else ""


def indirizzi_ritorno(token: str) -> dict[str, str]:
    base = request.host_url.rstrip("/")
    return {
        "success": base + url_for("pagamenti.successo", token=token),
        "cancel": base + url_for("pagamenti.checkout", token=token),
        "callback_satispay": base + indirizzo_webhook("satispay"),
    }


def avvia_pagamento(gp, lp, provider: str) -> EsitoAvvio:
    """Avvia il pagamento con il gestore scelto fra quelli attivi dello studio."""
    provider = str(provider or "").strip()
    if provider not in gp.config.provider_attivi():
        return EsitoAvvio("provider_non_valido", messaggio="Metodo di pagamento non disponibile.")
    ritorno = indirizzi_ritorno(lp.token)

    if provider == "stripe":
        try:
            url = _url_esterno(gp.stripe_crea_sessione(lp, ritorno["success"], ritorno["cancel"]))
        except Exception:
            # Il testo dell'eccezione (chiavi, identificativi del gestore) resta nel log.
            current_app.logger.exception("Stripe: sessione di pagamento non creata per il link %s", lp.id)
            return EsitoAvvio("errore", messaggio=MESSAGGIO_STRIPE_NON_AVVIATO)
        if url:
            return EsitoAvvio("redirect", url=url)
        return EsitoAvvio("errore", messaggio=MESSAGGIO_STRIPE_NON_AVVIATO)

    if provider == "paypal":
        ordine = gp.paypal_crea_ordine(lp, return_url=ritorno["success"] + "?provider=paypal", cancel_url=ritorno["cancel"])
        url = _url_esterno((ordine or {}).get("approve_url"))
        if url:
            # L'ordine si cattura al ritorno (pagina di esito).
            session[f"paypal_order_{lp.id}"] = ordine["id"]
            return EsitoAvvio("redirect", url=url)
        return EsitoAvvio("errore", messaggio="Errore nella creazione dell'ordine PayPal.")

    if provider == "sumup":
        checkout = gp.sumup_crea_checkout(lp, return_url=ritorno["success"])
        if checkout and checkout.get("checkout_id"):
            return EsitoAvvio("sumup", checkout_id=str(checkout["checkout_id"]), url=ritorno["success"])
        return EsitoAvvio("errore", messaggio="Errore SumUp.")

    if provider == "satispay":
        risultato = gp.satispay_crea_pagamento(lp, callback_url=ritorno["callback_satispay"])
        url = _url_esterno((risultato or {}).get("redirect_url"))
        if url:
            return EsitoAvvio("redirect", url=url)
        return EsitoAvvio("errore", messaggio="Errore Satispay.")

    # Bonifico: coordinate nella pagina di esito, conferma a cura dello studio.
    return EsitoAvvio("bonifico", url=url_for("pagamenti.successo", token=lp.token) + "?provider=bonifico")


# ------------------------------------------------------------------ ritorno dal gestore

def verifica_ritorno(gp, token: str, provider: str, argomenti: Mapping[str, Any]):
    """Registra il pagamento confermato dal gestore (PayPal, Stripe) e rilegge il link."""
    from pct.pagamenti_verifica import paypal_ordine_del_link, stripe_sessione_del_link

    lp = link_del_token(gp, token)
    if not lp:
        return None
    if provider == "paypal" and lp.stato == STATO_ATTESO:
        order_id = argomenti.get("token") or session.pop(f"paypal_order_{lp.id}", None)
        if order_id and paypal_ordine_del_link(gp, order_id, lp) and gp.paypal_cattura_ordine(order_id):
            gp.segna_pagato(lp.id, "PayPal", tx_id=order_id)
            aggiorna_parcella_pagata(lp.id_parcella, "PayPal")

    session_id = str(argomenti.get("session_id") or "")
    if session_id and lp.stato == STATO_ATTESO:
        try:
            import stripe

            stripe.api_key = gp.config.stripe.sk
            sess = stripe.checkout.Session.retrieve(session_id)
            if stripe_sessione_del_link(sess, lp):
                gp.segna_pagato(lp.id, "Stripe", tx_id=session_id)
                aggiorna_parcella_pagata(lp.id_parcella, "Stripe")
        except Exception:
            pass
    return gp.get_by_token(token)


__all__ = [
    "EsitoAvvio",
    "VistaLink",
    "MESSAGGIO_STRIPE_NON_AVVIATO",
    "aggiorna_parcella_pagata",
    "avvia_pagamento",
    "entra_studio_webhook",
    "gestore_pagamenti",
    "indirizzi_ritorno",
    "indirizzo_webhook",
    "link_del_token",
    "risolvi_studio_pagamento",
    "risolvi_studio_webhook",
    "studio_nome",
    "verifica_ritorno",
    "vista_link",
]
