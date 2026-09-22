"""La rispezzatura dei chunk RAG, studio per studio.

La logica sta in `pct/manutenzione_chunk_rag`; qui si aggiunge solo il
contesto. L'archivio locale di uno studio non si apre ricostruendo i percorsi
a mano: si entra nel contesto tenant e si chiede il servizio alla stessa
fabbrica che usa l'applicazione (`get_local_ai_service`). Altrimenti si finisce
a guardare un database diverso da quello vero — o a crearne uno vuoto — e il
conteggio torna zero mentre i chunk sono tutti al loro posto.
"""

from __future__ import annotations

from typing import Any

from flask import g

from pct.manutenzione_chunk_rag import EsitoArchivio, _riepilogo, esamina, rispezza


def _servizio_corrente():
    from lex.providers.local_ai_service import get_local_ai_service

    return get_local_ai_service()


def esamina_tutti(app: Any, *, rispezzare: bool = False, limite: int = 0) -> dict[str, Any]:
    """Tutti gli studi attivi, ognuno con il suo archivio."""
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    lavoro = rispezza if rispezzare else esamina
    esiti: list[EsitoArchivio] = []
    attivi = _active_tenants(app)
    if not attivi:
        # Installazione a studio singolo: nessun contesto tenant da montare.
        with app.test_request_context("/__manutenzione/chunk-rag/default"):
            g.multi_tenant_enabled = False
            g.tenant_context_missing = False
            g.tenant_context_slug = ""
            try:
                esiti.append(lavoro(_servizio_corrente(), studio="default", limite=limite))
            except Exception as exc:
                esiti.append(EsitoArchivio(studio="default", errore=str(exc)))
        return _riepilogo(esiti, applicato=rispezzare)

    from pct.tenant import GestioneTenant

    manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
    for studio in attivi:
        slug = str(getattr(studio, "slug", "") or "").strip().lower()
        if not slug:
            continue
        with app.test_request_context(f"/__manutenzione/chunk-rag/{slug}"):
            try:
                _attach_tenant_context(manager, studio)
                esiti.append(lavoro(_servizio_corrente(), studio=slug, limite=limite))
            except Exception as exc:
                esiti.append(EsitoArchivio(studio=slug, errore=str(exc)))
    return _riepilogo(esiti, applicato=rispezzare)


__all__ = ["esamina_tutti"]
