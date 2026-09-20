"""Il ricalcolo dei collegamenti PEC, studio per studio.

La logica sta in `pct/manutenzione_collegamenti_pec`; qui si aggiunge solo il
contesto: ogni studio ha la sua casella, il suo archivio fascicoli e il suo
registro dei collegamenti, e vanno tenuti separati.
"""

from __future__ import annotations

from typing import Any

from pct.manutenzione_collegamenti_pec import EsitoStudio, _riepilogo, esamina, ricollega


def _repository_per_studio(app: Any, slug: str):
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.pec_pipeline_runtime import repository_from_paths

    paths = _attach_tenant_context(app, slug)
    return repository_from_paths(paths, tenant_label=slug)


def esamina_tutti(app: Any, *, ricollegare: bool = False, limite: int = 0) -> dict[str, Any]:
    """Tutti gli studi attivi, ognuno con il suo registro."""
    from web.services.fascicoli_presidi_runtime import _active_tenants

    lavoro = ricollega if ricollegare else esamina
    esiti: list[EsitoStudio] = []
    attivi = _active_tenants(app)
    if not attivi:
        # Installazione a studio singolo: il contesto e' gia' quello giusto.
        from web.services.pec_pipeline_runtime import (
            repository_from_paths,
            tenant_label_for_current_request,
        )

        etichetta = tenant_label_for_current_request()
        repo = repository_from_paths(dict(app.config), tenant_label=etichetta)
        esiti.append(lavoro(repo, studio=etichetta, limite=limite))
        return _riepilogo(esiti, applicato=ricollegare)

    for studio in attivi:
        slug = str(getattr(studio, "slug", "") or "").strip().lower()
        if not slug:
            continue
        with app.test_request_context(f"/__manutenzione/collegamenti-pec/{slug}"):
            try:
                repo = _repository_per_studio(app, slug)
                esiti.append(lavoro(repo, studio=slug, limite=limite))
            except Exception as exc:
                esiti.append(EsitoStudio(studio=slug, errore=str(exc)))
    return _riepilogo(esiti, applicato=ricollegare)
