"""Corsie dello scheduler: un lavoro alla volta per corsia, invece di dieci insieme.

Verifica del 02/11/2026: lo scheduler usava l'esecutore predefinito di APScheduler, dieci thread, e fino a dieci
lavori giravano insieme sugli stessi archivi SQLite e JSON. Ne venivano «database is locked», «Fascicolo
aggiornato da un altro processo» e tre chiusure del processo per memoria esaurita.

Ora i lavori stanno in tre corsie, ciascuna con la propria coda:

* ``rapida``: lavori brevi da cui dipendono termini, PEC e avvisi (un lavoro alla volta), così non aspettano
  dietro un lavoro pesante;
* ``default`` (corsia lunga): tutti gli altri, compresi i lavori del registro e le fonti legali (un lavoro alla
  volta in tutto il processo);
* ``infrastruttura``: i giri tecnici di pochi millisecondi che consegnano gli eventi alle proiezioni.

Un lavoro che arriva mentre la sua corsia è occupata aspetta in coda e parte appena la corsia si libera: con
``max_instances=1`` e ``coalesce`` non si accumulano più copie dello stesso lavoro.
"""

from __future__ import annotations

from typing import Any

CORSIA_LUNGA = "default"
CORSIA_RAPIDA = "rapida"
CORSIA_INFRASTRUTTURA = "infrastruttura"

THREAD_PER_CORSIA = {CORSIA_LUNGA: 1, CORSIA_RAPIDA: 1, CORSIA_INFRASTRUTTURA: 3}

# Termini legali, PEC, avvisi e calendari: brevi e frequenti.
LAVORI_RAPIDI = frozenset({
    "mailbox_sync_runtime",
    "pec_audit_pipeline_workers",
    "poll_pec_cancelleria",
    "polling_esiti_deposito",
    "legal_notification_relata_presidio",
    "agenda_scadenziario_notifications",
    "calendar_sync_engine_polling",
    "calendar_sync_engine_retry",
    "calendar_sync_hourly",
    "sync_polisweb_registri",
    "aggiorna_scadute",
    "aggiorna_parcelle_scadute",
    "wa_reminder",
    "pec_audit_digest_daily",
})

# Consegne degli eventi alle proiezioni (catalogo fascicoli, ricevute) e ripresa delle richieste manuali.
LAVORI_INFRASTRUTTURA = frozenset({
    "scheduler_registry_reload",
    "fascicoli_list_projection",
    "receipt_query_projection",
})


def corsia_del_lavoro(job_id: str) -> str:
    """La corsia di un lavoro; quelli non elencati, compresi i nuovi, vanno nella corsia lunga."""
    lavoro = str(job_id or "")
    if lavoro.startswith("manual_"):
        # Esecuzione manuale dalla console: «manual_<job>_<run>» segue la corsia del lavoro.
        lavoro = lavoro[len("manual_"):].rsplit("_", 1)[0]
    if lavoro in LAVORI_INFRASTRUTTURA:
        return CORSIA_INFRASTRUTTURA
    if lavoro in LAVORI_RAPIDI:
        return CORSIA_RAPIDA
    return CORSIA_LUNGA


def esecutori() -> dict[str, Any]:
    """Gli esecutori da passare a ``BackgroundScheduler(executors=...)``."""
    from apscheduler.executors.pool import ThreadPoolExecutor

    return {nome: ThreadPoolExecutor(max_workers=thread) for nome, thread in THREAD_PER_CORSIA.items()}


def assegna_corsie(scheduler: Any) -> dict[str, int]:
    """Mette ogni lavoro già registrato nella sua corsia; restituisce quanti lavori per corsia."""
    conteggio = dict.fromkeys(THREAD_PER_CORSIA, 0)
    for job in list(scheduler.get_jobs()):
        corsia = corsia_del_lavoro(job.id)
        if getattr(job, "executor", CORSIA_LUNGA) != corsia:
            scheduler.modify_job(job.id, executor=corsia)
        conteggio[corsia] += 1
    return conteggio
