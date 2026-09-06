"""Scheduler entry point: public-only SQL directory, never a tenant fallback."""
from pct.mediazione_source_refresh import refresh_sources
from web.services.mediazione_directory_surface import directory


def refresh_mediazione_sources(config):
    repo = directory(config)
    if repo is None:
        return {"ok": False, "summary": "Registro degli organismi non disponibile: aggiornamento non eseguito."}
    return refresh_sources(repo, limit=6, workers=2)
