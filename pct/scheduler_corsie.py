"""Corsie dello scheduler: un lavoro alla volta per corsia, invece di dieci insieme.

Verifica del 02/11/2026: lo scheduler usava l'esecutore predefinito di APScheduler, dieci thread, e fino a dieci
lavori giravano insieme sugli stessi archivi SQLite e JSON. Ne venivano «database is locked», «Fascicolo
aggiornato da un altro processo» e tre chiusure del processo per memoria esaurita.

I lavori hanno code distinte:

* ``rapida``: lavori brevi da cui dipendono termini, PEC e avvisi (un lavoro alla volta), così non aspettano
  dietro un lavoro pesante;
* ``default`` (corsia lunga): tutti gli altri, compresi i lavori del registro e le fonti legali (un lavoro alla
  volta in tutto il processo);
* ``notturna``: coordinatore della sequenza notturna, un passo alla volta. I motori conservano il semaforo;
* ``pec_acquisizione``: acquisizione, classificazione e OCR PEC, con una sola istanza;
* ``infrastruttura``: i giri tecnici di pochi millisecondi che consegnano gli eventi alle proiezioni;
* ``posta``: la sincronizzazione delle caselle, fuori dalla corsia rapida;
* ``giurisprudenza``: l'alimentazione dell'archivio di giurisprudenza (SentenzeWeb e lettura delle citazioni), che
  lavora su archivi propri e può durare quasi un'ora: nella corsia lunga la occupava e faceva saltare gli altri lavori.

Verifica del 18/11/2026: un lavoro della corsia lunga a orario fisso che parte con più di cinque minuti di ritardo
(la tolleranza predefinita) viene scartato da APScheduler. Con la corsia occupata dal piano del giorno (11 minuti
ogni 15) e dall'alimentazione della giurisprudenza, i controlli operativi delle 7:00, 13:30 e 19:30 e il time
tracking delle 20:30 risultavano «saltati dal worker» ogni giorno, senza nessuna esecuzione completata. Per questi
lavori ``TOLLERANZA_RITARDO_SECONDI`` dice fino a quanto ritardo il giro si esegue comunque.

Un lavoro che arriva mentre la sua corsia è occupata aspetta in coda e parte appena la corsia si libera: con
``max_instances=1`` e ``coalesce`` non si accumulano più copie dello stesso lavoro.
"""

from __future__ import annotations

from typing import Any

CORSIA_LUNGA = "default"
CORSIA_RAPIDA = "rapida"
CORSIA_INFRASTRUTTURA = "infrastruttura"
CORSIA_ACQUISIZIONE_PEC = "pec_acquisizione"
CORSIA_NOTTURNA = "notturna"
CORSIA_GIURISPRUDENZA = "giurisprudenza"
CORSIA_POSTA = "posta"
CORSIA_FONTI_PUBBLICHE = "fonti_pubbliche"

THREAD_PER_CORSIA = {
    CORSIA_LUNGA: 1,
    CORSIA_RAPIDA: 1,
    CORSIA_ACQUISIZIONE_PEC: 1,
    CORSIA_NOTTURNA: 1,
    CORSIA_INFRASTRUTTURA: 3,
    CORSIA_GIURISPRUDENZA: 1,
    CORSIA_POSTA: 1,
    CORSIA_FONTI_PUBBLICHE: 1,
}

# Testi della Giustizia amministrativa e prassi (23/11/2026): giri da 20 minuti ogni ora; nella corsia lunga
# fermerebbero il piano del giorno, quindi hanno una corsia propria e si alternano.
LAVORI_FONTI_PUBBLICHE = frozenset({
    "giustizia_amministrativa_testi",
    "prassi_agenzia_entrate_inps",
})

# Sincronizzazione delle caselle (decisione del 19/11/2026): il 18/11 sera la corsia rapida è rimasta ferma 90 minuti
# dietro le caselle; agenda, relata ed esiti deposito non devono mai aspettare la posta.
LAVORI_POSTA = frozenset({
    "mailbox_sync_runtime",
    "poll_pec_cancelleria",
})

# Acquisizione SentenzeWeb e lettura delle citazioni: stesso blocco ``acquisizione.lock``, archivi propri.
LAVORI_GIURISPRUDENZA = frozenset({
    "giurisprudenza_alimentazione_continua",
    "cassazione_sentenzeweb_nightly",
})

# Ritardo massimo (secondi) con cui un giro in attesa della corsia si esegue ancora, invece di essere scartato.
# Resta sotto la cadenza del lavoro, così due giri non si sommano (``coalesce`` li unisce comunque).
TOLLERANZA_RITARDO_SECONDI = {
    "operational_crash_morning": 2 * 3600,
    "operational_crash_midday": 2 * 3600,
    "operational_crash_evening": 2 * 3600,
    "time_tracking_passivo": 3600,
    "legal_monitor_pst": 3600,
    "calendar_sync_engine_webcal": 45 * 60,
    "giurisprudenza_alimentazione_continua": 45 * 60,
    "local_ai_maintenance": 25 * 60,
    "archivio_letture_automatico": 8 * 60,
}

# Termini legali, PEC, avvisi e calendari: brevi e frequenti.
LAVORI_RAPIDI = frozenset({
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
    "pannelli_pronti_ricalcolo",
    "bozze_passi_preparazione",
})


def corsia_del_lavoro(job_id: str) -> str:
    """La corsia di un lavoro; quelli non elencati, compresi i nuovi, vanno nella corsia lunga."""
    lavoro = str(job_id or "")
    if lavoro.startswith("manual_"):
        # Esecuzione manuale dalla console: «manual_<job>_<run>» segue la corsia del lavoro.
        lavoro = lavoro[len("manual_"):].rsplit("_", 1)[0]
    if lavoro == "sequenza_notturna":
        return CORSIA_NOTTURNA
    if lavoro == "pec_audit_pipeline_workers":
        return CORSIA_ACQUISIZIONE_PEC
    if lavoro in LAVORI_INFRASTRUTTURA:
        return CORSIA_INFRASTRUTTURA
    if lavoro in LAVORI_GIURISPRUDENZA:
        return CORSIA_GIURISPRUDENZA
    if lavoro in LAVORI_POSTA:
        return CORSIA_POSTA
    if lavoro in LAVORI_FONTI_PUBBLICHE:
        return CORSIA_FONTI_PUBBLICHE
    if lavoro in LAVORI_RAPIDI:
        return CORSIA_RAPIDA
    return CORSIA_LUNGA


def esecutori() -> dict[str, Any]:
    """Gli esecutori da passare a ``BackgroundScheduler(executors=...)``."""
    from apscheduler.executors.pool import ThreadPoolExecutor

    return {nome: ThreadPoolExecutor(max_workers=thread) for nome, thread in THREAD_PER_CORSIA.items()}


_ASSENTE = object()


def assegna_corsie(scheduler: Any) -> dict[str, int]:
    """Mette ogni lavoro già registrato nella sua corsia e con la sua tolleranza di ritardo; conta i lavori per corsia."""
    conteggio = dict.fromkeys(THREAD_PER_CORSIA, 0)
    for job in list(scheduler.get_jobs()):
        corsia = corsia_del_lavoro(job.id)
        modifiche: dict[str, Any] = {}
        if getattr(job, "executor", CORSIA_LUNGA) != corsia:
            modifiche["executor"] = corsia
        tolleranza = TOLLERANZA_RITARDO_SECONDI.get(job.id)
        # Prima di ``scheduler.start()`` un lavoro senza tolleranza propria non ha ancora l'attributo (APScheduler
        # applica i ``job_defaults`` all'avvio); ``None`` esplicito vuol dire «nessun limite» e resta così.
        attuale = getattr(job, "misfire_grace_time", _ASSENTE)
        if tolleranza and (attuale is _ASSENTE or (attuale is not None and attuale < tolleranza)):
            modifiche["misfire_grace_time"] = tolleranza
        if modifiche:
            scheduler.modify_job(job.id, **modifiche)
        conteggio[corsia] += 1
    return conteggio
