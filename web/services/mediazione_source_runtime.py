"""Scheduler entry point: public-only SQL directory, never a tenant fallback."""
import logging
from pathlib import Path

from pct.mediazione_directory_repository import MediazioneDirectoryRepository

from pct.mediazione_source_refresh import refresh_sources, verifiche_in_attesa
from web.services.mediazione_directory_surface import directory


def refresh_mediazione_sources(config):
    repo = directory(config)
    anchor = config.get("NORMATIVE_TABLES_DB")
    popolato = False
    if repo is not None:
        with repo.connection() as conn:
            popolato = conn.execute("SELECT 1 FROM mediazione_organismi LIMIT 1").fetchone() is not None
    if not popolato and anchor and Path(anchor).is_file():
        # Prima inizializzazione da uno snapshot pubblico completo già acquisito.
        # La pagina resta in sola lettura; la rete è gestita dal job.
        from pct.legal_intelligence import REGISTRO_MEDIAZIONE_DIRECT_URL, REGISTRO_MEDIAZIONE_TABLE_ID
        from pct.normative_tables import GestioneTabelleNormative

        norme = GestioneTabelleNormative(str(anchor))
        tabella = norme.get_table(REGISTRO_MEDIAZIONE_TABLE_ID)
        versione = tabella["active_version"]
        righe = versione.get("rows") or []
        attese = tabella["defaults"].get("registry_expected_rows")
        data = versione.get("acquired_at")
        if versione.get("origin") == "live_registry" and righe and len(righe) == attese and data:
            path = config.get("MEDIAZIONE_DIRECTORY_DB") or Path(anchor).with_name("mediazione_directory.db")
            repo = repo or MediazioneDirectoryRepository(path)
            popolato = repo.import_registry(righe, source=REGISTRO_MEDIAZIONE_DIRECT_URL, checked_at=data) > 0
    if not popolato:
        return {"ok": False, "message": "Archivio degli organismi assente e nessun elenco ministeriale completo disponibile."}
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
