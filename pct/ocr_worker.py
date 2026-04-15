"""Worker dedicato alla pipeline OCR con pool di worker thread."""

from __future__ import annotations

import logging
import os
import signal
import threading
from pathlib import Path
from time import sleep
from typing import Any

from pct.ocr import estrai_testo as ocr_estrai_testo
from pct.ocr_jobs import OCRJobStore, default_ocr_queue_db
from pct.search_index import IndiceRicerca
from web.services.document_crypto import decrypt_doc


logger = logging.getLogger("pct.ocr_worker")


def _queue_db_path() -> str:
    explicit = str(os.getenv("PCT_OCR_QUEUE_DB", "")).strip()
    if explicit:
        return explicit
    search_index = str(os.getenv("PCT_SEARCH_INDEX", "./search/index.db")).strip()
    return default_ocr_queue_db(search_index)


def _process_job(store: OCRJobStore, worker_id: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        job = store.claim_next(worker_id=worker_id)
        if job is None:
            sleep(1.0)
            continue
        try:
            idx = IndiceRicerca(index_path=job.index_path)
            testo = idx.get_ocr_cache(job.hash_sha256)
            if testo is None:
                raw = Path(job.percorso).read_bytes()
                decifrato = decrypt_doc(raw)
                testo = ocr_estrai_testo(decifrato, job.nome_doc)
                idx.set_ocr_cache(job.hash_sha256, testo)
            if testo:
                idx.indicizza_documento(job.id_fasc, job.id_doc, job.nome_doc, testo, job.tipo_doc)
            store.complete(job.id)
        except Exception as exc:
            logger.warning("Errore OCR su job %s (%s/%s): %s", job.id, job.id_fasc, job.id_doc, exc)
            store.fail(job.id, str(exc))


def serve_ocr_worker(*, stop_event: threading.Event | None = None) -> int:
    queue_db_path = _queue_db_path()
    workers = max(1, int(os.getenv("PCT_OCR_WORKERS", "2") or "2"))
    shutdown_event = stop_event or threading.Event()
    store = OCRJobStore(queue_db_path)

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("OCR worker: ricevuto segnale %s, arresto in corso.", signum)
        shutdown_event.set()

    if threading.current_thread() is threading.main_thread():
        for signal_name in ("SIGTERM", "SIGINT"):
            signum = getattr(signal, signal_name, None)
            if signum is not None:
                signal.signal(signum, _handle_signal)

    threads = [
        threading.Thread(
            target=_process_job,
            name=f"ocr-worker-{index + 1}",
            args=(store, f"ocr-worker-{index + 1}", shutdown_event),
            daemon=True,
        )
        for index in range(workers)
    ]
    for thread in threads:
        thread.start()

    logger.info("OCR worker pool avviato: %s thread, queue=%s", workers, queue_db_path)
    try:
        while not shutdown_event.wait(60):
            continue
    finally:
        shutdown_event.set()
        for thread in threads:
            thread.join(timeout=2)
    return 0


def main() -> int:
    return serve_ocr_worker()


if __name__ == "__main__":
    raise SystemExit(main())
