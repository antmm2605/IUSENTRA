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

    riavvio_guardiano = False

    def _default_signal_handler(event: threading.Event) -> Callable[[int, Any], None]:
        def _handle_signal(signum: int, _frame: Any) -> None:
            nonlocal riavvio_guardiano
            riavvio_guardiano = signum == SEGNALE_GUARDIANO and signum != signal.SIGTERM
            logger.info("Scheduler worker: ricevuto segnale %s, arresto in corso.", signum)
            event.set()

        return _handle_signal

    from pct.scheduler_health import mark_worker_started

    mark_worker_started()
    from pct.scheduler_corsie import CORSIA_INFRASTRUTTURA
    from pct.scheduler_guardiano import INTERVALLO_BATTITO, SEGNALE_GUARDIANO, avvia_guardiano, scrivi_battito

    # Battito ogni 30 s e guardiano in un processo separato: un lavoro che blocca il processo non ferma più per ore
    # tutti i lavori automatici (08/11/2026); il worker viene chiuso e Docker lo riavvia.
    scheduler.add_job(scrivi_battito, "interval", seconds=INTERVALLO_BATTITO, id="battito_scheduler",
                      max_instances=1, coalesce=True, replace_existing=True, executor=CORSIA_INFRASTRUTTURA)
    from pct.preriscaldamento_archivi import avvia_in_sfondo

    avvia_in_sfondo(shutdown_event)  # la prima ricerca normativa non attende il disco (solo con IUSENTRA_PRERISCALDA_ARCHIVI=1)
    handler_factory = signal_handler_factory or _default_signal_handler
    handler = handler_factory(shutdown_event)
    for signal_name in ("SIGTERM", "SIGINT"):
        signum = getattr(signal, signal_name, None)
        if signum is not None:
            signal.signal(signum, handler)

    if SEGNALE_GUARDIANO != signal.SIGTERM:
        signal.signal(SEGNALE_GUARDIANO, _default_signal_handler(shutdown_event))
    guardiano = avvia_guardiano()

    logger.info("Scheduler worker dedicato avviato correttamente.")
    try:
        while not shutdown_event.wait(60):
            continue
    finally:
        # Una richiesta del guardiano deve lasciargli completare l'escalation:
        # i thread APScheduler possono impedire l'uscita anche dopo shutdown().
        if guardiano is not None and not riavvio_guardiano:
            guardiano.terminate()
        try:
            scheduler.shutdown(wait=False)
        except Exception as exc:  # pragma: no cover - shutdown best effort
            logger.warning("Arresto scheduler worker non pulito: %s", exc)
    return 0


def check_presidio_health(config: dict[str, Any] | None = None) -> int:
    """Esito del battito dei presidi, per l'healthcheck del container.

    Restituisce 0 se tutti i presidi hanno girato entro la propria tolleranza,
    1 altrimenti, stampando quale presidio e' fermo e da quanto. Il worker vivo
    ma muto non deve piu' risultare "healthy".

    Deliberatamente leggero: legge il registro pianificazioni direttamente dal
    percorso di runtime, senza costruire la Flask app. Gira ogni 30 secondi e
    non deve pesare sulla CPU del server.
    """

    from pct.scheduler_health import (
        format_heartbeat_lines,
        presidio_heartbeat_for_config,
        worker_startup_grace_active,
    )

    report = presidio_heartbeat_for_config(dict(config or {}))
    for riga in format_heartbeat_lines(report):
        print(riga)
    if report.get("ok"):
        return 0
    # Appena riavviato il worker non ha ancora eseguito nulla: segnalare
    # "degradato" in quella finestra creerebbe un ciclo di riavvii del
    # container invece di riportare un guasto reale.
    if worker_startup_grace_active() and not report.get("hard_failures"):
        print("presidi: avvio recente del worker, attesa del primo giro")
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m pct.scheduler_worker", allow_abbrev=False)
    parser.add_argument("--health", "--check-presidi", action="store_true", help="Verifica lo stato dei presìdi ed esce.")
    if parser.parse_args(argv).health:
        return check_presidio_health()
    return serve_scheduler_worker()


if __name__ == "__main__":
    raise SystemExit(main())
