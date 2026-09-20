"""Scheduler entry point: public-only SQL directory, never a tenant fallback."""
import logging

from pct.mediazione_source_refresh import refresh_sources, verifiche_in_attesa
from web.services.mediazione_directory_surface import directory


def refresh_mediazione_sources(config):
    repo = directory(config)
    if repo is None:
        return {"ok": False, "summary": "Registro degli organismi non disponibile: aggiornamento non eseguito."}
    return refresh_sources(repo, limit=6, workers=2)


logger = logging.getLogger(__name__)


def sveglia_se_ci_sono_verifiche(config, *, username="apertura mediazione"):
    """Chiede un giro quando si apre la mediazione, e solo se serve davvero.

    Il controllo delle fonti non ha piu' una cadenza fissa: girava ogni dieci
    minuti anche con la coda vuota, e quasi sempre la coda e' vuota. Adesso
    parte quando qualcuno apre la mediazione, dopo una COUNT sulla coda — e
    il giro vero resta sullo scheduler, cosi' la pagina non aspetta la rete.

    Non solleva mai: se la sveglia non parte, la passata notturna recupera.
    """
    esito = {"svegliato": False, "in_attesa": 0}
    try:
        repo = directory(config)
        if repo is None:
            return esito
        esito["in_attesa"] = verifiche_in_attesa(repo)
        if esito["in_attesa"] <= 0:
            return esito
        from web.services.scheduler_admin_surface import request_scheduler_run

        request_scheduler_run(
            "mediazione_sources_refresh",
            username=username,
            dedupe_open=True,
        )
        esito["svegliato"] = True
    except Exception:
        logger.debug(
            "Sveglia delle fonti mediazione non inoltrata: la passata notturna la recuperera'.",
            exc_info=True,
        )
    return esito
