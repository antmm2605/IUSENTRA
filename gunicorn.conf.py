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
