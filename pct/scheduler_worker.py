"""Worker dedicato per i job periodici IUSENTRA.

Uso:
    python -m pct.scheduler_worker
"""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable
from typing import Any

from flask import Flask

from pct.scheduler import start_scheduler
from web.app import create_app


logger = logging.getLogger("pct.scheduler_worker")


def create_scheduler_app(config: dict[str, Any] | None = None) -> Flask:
    """Costruisce una Flask app leggera per il solo worker scheduler."""

    cfg = dict(config or {})
    cfg["SCHEDULER_ONLY"] = True
    return create_app(cfg)


def start_scheduler_worker(config: dict[str, Any] | None = None) -> Flask:
    """Avvia lo scheduler sul worker dedicato e restituisce la Flask app usata."""

    app = create_scheduler_app(config)
    scheduler = start_scheduler(app)
    if scheduler is None:
        logger.warning(
            "Worker scheduler non avviato: APScheduler mancante o avvio disabilitato."
        )
    return app


def serve_scheduler_worker(
    app: Flask | None = None,
    *,
    stop_event: threading.Event | None = None,
    signal_handler_factory: Callable[[threading.Event], Callable[[int, Any], None]] | None = None,
) -> int:
    """Mantiene vivo il worker finché non riceve un segnale di arresto."""

    runtime_app = app or start_scheduler_worker()
    scheduler = runtime_app.config.get("PCT_SCHEDULER")
    if scheduler is None:
        logger.error("Nessuno scheduler attivo: il worker termina senza job registrati.")
        return 1

    shutdown_event = stop_event or threading.Event()

    def _default_signal_handler(event: threading.Event) -> Callable[[int, Any], None]:
        def _handle_signal(signum: int, _frame: Any) -> None:
            logger.info("Scheduler worker: ricevuto segnale %s, arresto in corso.", signum)
            event.set()

        return _handle_signal

    handler_factory = signal_handler_factory or _default_signal_handler
    handler = handler_factory(shutdown_event)
    for signal_name in ("SIGTERM", "SIGINT"):
        signum = getattr(signal, signal_name, None)
        if signum is not None:
            signal.signal(signum, handler)

    logger.info("Scheduler worker dedicato avviato correttamente.")
    try:
        while not shutdown_event.wait(60):
            continue
    finally:
        try:
            scheduler.shutdown(wait=False)
        except Exception as exc:  # pragma: no cover - shutdown best effort
            logger.warning("Arresto scheduler worker non pulito: %s", exc)
    return 0


def main() -> int:
    return serve_scheduler_worker()


if __name__ == "__main__":
    raise SystemExit(main())
