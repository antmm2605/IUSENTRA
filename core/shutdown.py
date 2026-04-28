"""Hook di shutdown graceful per web e worker."""

from __future__ import annotations

import logging
import signal
from types import FrameType
from typing import Callable


def register_shutdown_handlers(on_shutdown: Callable[[], None] | None = None) -> None:
    logger = logging.getLogger("iusentra.shutdown")

    def _handler(signum: int, frame: FrameType | None) -> None:
        logger.info("Shutdown ricevuto: segnale %s", signum)
        if on_shutdown:
            on_shutdown()
        raise SystemExit(0)

    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(signum, _handler)
        except ValueError:
            # Non registrabile fuori dal main thread: il runtime resta comunque operativo.
            logger.debug("Signal handler non registrato per %s", signum)
