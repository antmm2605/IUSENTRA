"""Censimento delle etichette certe del catalogo documentale, per studio, fuori dalle richieste web.

Legge soltanto ciò che è già nel catalogo SQL, nei metadati dei documenti importati dal portale e nell'audit delle
decisioni dell'avvocato: nessun documento viene aperto o riletto. Il risultato è un riepilogo di conteggi e voci,
senza nomi di file, testi o dati del cliente, adatto a essere letto fuori dal server
(`pct.document_intelligence.verita`).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, g

from pct.document_intelligence.verita import censisci, riepilogo
from web.services.document_catalog_conferma import NOTA_CONFERMA_MASSIVA

logger = logging.getLogger(__name__)

# Lunghezza della nota della conferma massiva: riconosce le conferme registrate prima che l'audit dichiarasse la
# modalità (2.457.8). Una nota scritta a mano della stessa lunghezza è improbabile e, se capita, esclude un esempio.
_LUNGHEZZA_NOTA_MASSIVA = len(NOTA_CONFERMA_MASSIVA)


def conferme_massive(eventi: list[dict[str, Any]]) -> set[str]:
    """Documenti la cui ultima decisione è una conferma dal pannello «Conferma tutto»."""
    ultima: dict[str, dict[str, Any]] = {}
    for evento in eventi:
        documento = str(evento.get("document_id") or "")
        if documento:
            ultima[documento] = evento
    massive = set()
    for documento, evento in ultima.items():
        payload = dict(evento.get("payload") or {})
        if evento.get("event_type") != "document_catalog.reviewed" or evento.get("status") != "confirmed":
            continue
        modalita = str(payload.get("modalita") or "")
        if modalita == "massiva" or (not modalita and int(payload.get("note_length") or 0) == _LUNGHEZZA_NOTA_MASSIVA):
            massive.add(documento)
    return massive


def censimento_studio_corrente() -> list[dict[str, Any]]:
    """Il censimento di ogni fascicolo dello studio già presente in `g`."""
    from web.helpers import get_fascicoli
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

    repository = build_document_ai_service().repository
    tenant_id = document_ai_tenant_id()
    censimenti = []
    for fascicolo_id, fascicolo in get_fascicoli().items():
        try:
            assegnazioni = repository.list_catalog_assignments(tenant_id, str(fascicolo_id))
            eventi = repository.list_catalog_decision_events(tenant_id, str(fascicolo_id))
        except Exception:  # un fascicolo senza catalogo SQL non ferma il censimento
            logger.debug("Catalogo non disponibile per il censimento di %s", fascicolo_id, exc_info=True)
            continue
        documenti = [d for d in list(getattr(fascicolo, "documenti", []) or []) if not getattr(d, "eliminato_il", "")]
        censimenti.append(censisci(documenti, assegnazioni, fascicolo_id=str(fascicolo_id),
                                   conferme_massive=conferme_massive(eventi)))
    return censimenti


def censimento_studi(app: Flask, *, minimo_per_voce: int = 30) -> dict[str, Any]:
    """Il riepilogo di ogni studio attivo; solo conteggi, nessun dato del cliente."""
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    esito: dict[str, Any] = {"studi": {}}
    studi = _active_tenants(app)
    if studi:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for numero, studio in enumerate(studi, start=1):
            slug = str(getattr(studio, "slug", "") or "").lower()
            with app.test_request_context(f"/__censimento/catalogo/{slug}"):
                _attach_tenant_context(manager, studio)
                # Gli studi si identificano con un numero: il riepilogo non porta nomi.
                esito["studi"][f"studio_{numero}"] = riepilogo(censimento_studio_corrente(), minimo_per_voce=minimo_per_voce)
    elif not app.config.get("MULTI_TENANT"):
        with app.test_request_context("/__censimento/catalogo/default"):
            g.multi_tenant_enabled = False
            esito["studi"]["studio_1"] = riepilogo(censimento_studio_corrente(), minimo_per_voce=minimo_per_voce)
    return esito


__all__ = ["censimento_studi", "censimento_studio_corrente", "conferme_massive"]
