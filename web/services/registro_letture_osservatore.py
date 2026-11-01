"""L'osservatore dei documenti che porta ogni modifica al registro delle letture.

Dentro una richiesta web le modifiche si raccolgono e diventano un solo evento per fascicolo alla fine della
richiesta (salvo che la rotta l'abbia già inviato con ``documento_aggiornato``/``documento_rimosso``).
Fuori da una richiesta (job, import, worker) il fascicolo si accoda: lo scheduler lo riprende entro un minuto.
In nessun caso si legge un documento qui.
"""

from __future__ import annotations

import logging

from flask import Flask, g, has_app_context, has_request_context

logger = logging.getLogger(__name__)

_IN_ATTESA = "_registro_documenti_cambiati"
_GIA_INVIATI = "_registro_eventi_inviati"


def segna_evento_inviato(fascicolo_id: str) -> None:
    """Le rotte che inviano l'evento in modo esplicito lo dichiarano: alla fine della richiesta non si ripete."""
    if has_request_context():
        inviati = g.get(_GIA_INVIATI)
        if inviati is None:
            inviati = set()
            setattr(g, _GIA_INVIATI, inviati)
        inviati.add(str(fascicolo_id or "").strip())


def osservatore_documenti(fascicolo_id: str, evento: str) -> None:
    if has_request_context():
        in_attesa = g.get(_IN_ATTESA)
        if in_attesa is None:
            in_attesa = set()
            setattr(g, _IN_ATTESA, in_attesa)
        in_attesa.add(fascicolo_id)
        return
    if not has_app_context():
        return
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        registro_corrente().accoda_evento(tenant_corrente(), fascicolo_id)
    except Exception as exc:
        logger.debug("Evento documenti (%s) non accodato per %s: %s", evento, fascicolo_id, exc)


def invia_eventi_in_attesa(_exc: BaseException | None = None) -> None:
    if not has_request_context():
        return
    in_attesa = set(g.get(_IN_ATTESA) or ())
    if not in_attesa:
        return
    gia_inviati = set(g.get(_GIA_INVIATI) or ())
    setattr(g, _IN_ATTESA, set())
    from web.services.registro_letture_runtime import documento_aggiornato

    for fascicolo_id in sorted(in_attesa - gia_inviati):
        try:
            documento_aggiornato(fascicolo_id)
        except Exception as exc:
            logger.warning("Evento del registro non inviato per il fascicolo %s: %s", fascicolo_id, exc)


def registra_osservatore_documenti(app: Flask) -> None:
    from pct.fascicoli_osservatori import registra_osservatore

    registra_osservatore(osservatore_documenti)
    app.teardown_request(invia_eventi_in_attesa)


__all__ = ["invia_eventi_in_attesa", "osservatore_documenti", "registra_osservatore_documenti", "segna_evento_inviato"]
