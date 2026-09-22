"""La rispezzatura dei chunk RAG, studio per studio.

La logica sta in `pct/manutenzione_chunk_rag`; qui si aggiunge solo il
contesto: ogni studio ha il suo archivio locale (`local_ai.db`), i suoi
documenti e la sua configurazione, e vanno tenuti separati.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pct.manutenzione_chunk_rag import EsitoArchivio, _riepilogo, esamina, rispezza

REPO_ROOT = Path(__file__).resolve().parents[2]


def _servizio_da_percorsi(app: Any, percorsi: dict[str, Any]):
    from pct.local_ai import LocalAIService

    giurisprudenza = str(percorsi.get("GIURISPRUDENZA_DB") or app.config.get("GIURISPRUDENZA_DB") or "")
    predefinito_db = str(Path(giurisprudenza).with_name("local_ai.db")) if giurisprudenza else "./intelligence/local_ai.db"
    predefinito_modelli = str(Path(giurisprudenza).with_name("models")) if giurisprudenza else "./intelligence/models"
    return LocalAIService(
        db_path=str(percorsi.get("LOCAL_AI_DB") or predefinito_db),
        policy_path=str(app.config.get("LOCAL_AI_POLICY", "./config/ai-policy.json")),
        config_path=str(
            percorsi.get("CONFIG_STUDIO_DB") or app.config.get("STUDIO_CONFIG", "./config/studio.json")
        ),
        app_root=str(REPO_ROOT),
        models_path=str(percorsi.get("LOCAL_AI_MODELS_DIR") or predefinito_modelli),
    )


def _servizio_per_studio(app: Any, slug: str):
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context

    percorsi = _attach_tenant_context(app, slug)
    return _servizio_da_percorsi(app, dict(percorsi))


def esamina_tutti(app: Any, *, rispezzare: bool = False, limite: int = 0) -> dict[str, Any]:
    """Tutti gli studi attivi, ognuno con il suo archivio."""
    from web.services.fascicoli_presidi_runtime import _active_tenants

    lavoro = rispezza if rispezzare else esamina
    esiti: list[EsitoArchivio] = []
    attivi = _active_tenants(app)
    if not attivi:
        # Installazione a studio singolo: il contesto e' gia' quello giusto.
        servizio = _servizio_da_percorsi(app, dict(app.config))
        esiti.append(lavoro(servizio, studio="default", limite=limite))
        return _riepilogo(esiti, applicato=rispezzare)

    for studio in attivi:
        slug = str(getattr(studio, "slug", "") or "").strip().lower()
        if not slug:
            continue
        with app.test_request_context(f"/__manutenzione/chunk-rag/{slug}"):
            try:
                servizio = _servizio_per_studio(app, slug)
                esiti.append(lavoro(servizio, studio=slug, limite=limite))
            except Exception as exc:
                esiti.append(EsitoArchivio(studio=slug, errore=str(exc)))
    return _riepilogo(esiti, applicato=rispezzare)


__all__ = ["esamina_tutti"]
