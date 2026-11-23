"""Configurazione Gunicorn produzione IUSENTRA."""

from __future__ import annotations

import os

bind = os.getenv("GUNICORN_BIND") or f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
# I lettori PDF/OCR nativi non cedono al loop gevent: il heartbeat deve
# restare indipendente dalla richiesta lunga, senza alzare il timeout.
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "100"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
# Il riciclo per numero di richieste tronca importazioni/OCR ancora attivi
# quando il polling raggiunge la soglia. Il watchdog timeout resta attivo.
# Un riciclo pianificato richiede prima la conclusione dei lavori in corso.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "0"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")


# ── Diagnosi dei worker (collaudo 21/11/2026) ────────────────────────────────
# Nel container gunicorn è il processo 1 e adotta i sottoprocessi orfani (per
# esempio un controllo di salute scaduto): gunicorn 23 registra la loro uscita
# come «Worker (pid) exited with code 1» anche se non sono worker. I worker veri
# si riconoscono da «worker terminato» qui sotto; il resto è un processo adottato.
# La cura per il processo 1 è `init: true` nel compose (tini come processo 1).

def child_exit(server, worker):  # noqa: ARG001 - firma di gunicorn
    from core.gunicorn_diagnosi import stato_uscita

    server.log.info("IUSENTRA: worker terminato pid=%s %s", worker.pid, stato_uscita(worker.pid))


def post_worker_init(worker):
    from core.gunicorn_diagnosi import avvia_sorveglianza

    avvia_sorveglianza(worker)
    # Prima esportazione PDF/RTF dell'editor non a freddo: conversione di prova in sfondo.
    try:
        from pct.editor_export import avvia_preriscaldamento_in_sfondo

        avvia_preriscaldamento_in_sfondo()
    except Exception as exc:  # l'avvio del worker non dipende dal convertitore
        worker.log.warning("IUSENTRA: preriscaldamento del convertitore non avviato: %s", exc)


def pre_request(worker, req):  # noqa: ARG001
    from core.gunicorn_diagnosi import inizio_richiesta

    inizio_richiesta(req)


def post_request(worker, req, environ, resp):  # noqa: ARG001
    from core.gunicorn_diagnosi import fine_richiesta

    fine_richiesta()


def worker_abort(worker):
    from core.gunicorn_diagnosi import registra_pile

    registra_pile(worker.log, "worker interrotto per tempo massimo (SIGABRT)")


def worker_exit(server, worker):  # noqa: ARG001
    from core.gunicorn_diagnosi import richieste_in_corso

    in_corso = richieste_in_corso()
    if in_corso:
        worker.log.error("IUSENTRA: worker %s esce con richieste ancora in corso: %s", worker.pid, in_corso)
