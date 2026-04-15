"""Runtime OCR asincrono per l'app Flask."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Callable

from pct.ocr import estensione_supportata as ocr_supportato
from pct.ocr import estrai_testo as ocr_estrai_testo
from pct.search_index import IndiceRicerca


class OCRRuntime:
    """Incapsula coda, statistiche e worker OCR."""

    def __init__(self, *, decrypt_doc: Callable[[bytes], bytes]) -> None:
        self._decrypt_doc = decrypt_doc
        self.queue: queue.Queue = queue.Queue()
        self.stats = {"totale": 0, "completati": 0, "errori": 0, "in_coda": 0}
        self.stats_lock = threading.Lock()
        self._thread = threading.Thread(target=self._ocr_worker, daemon=True, name="ocr-worker")
        self._thread.start()

    def _ocr_worker(self) -> None:
        """Thread daemon che processa i job OCR in background."""
        import logging

        log = logging.getLogger("ocr_worker")
        while True:
            job = self.queue.get()
            if job is None:
                break
            percorso, hash_sha256, id_fasc, id_doc, nome_doc, tipo_doc, index_path = job
            with self.stats_lock:
                self.stats["in_coda"] = self.queue.qsize()
            try:
                idx = IndiceRicerca(index_path=index_path)
                testo = idx.get_ocr_cache(hash_sha256)
                if testo is None:
                    raw = Path(percorso).read_bytes()
                    decifrato = self._decrypt_doc(raw)
                    testo = ocr_estrai_testo(decifrato, nome_doc)
                    idx.set_ocr_cache(hash_sha256, testo)
                if testo:
                    idx.indicizza_documento(id_fasc, id_doc, nome_doc, testo, tipo_doc)
                with self.stats_lock:
                    self.stats["completati"] += 1
            except Exception as exc:
                log.warning("Errore OCR documento %s/%s: %s", id_fasc, id_doc, exc)
                with self.stats_lock:
                    self.stats["errori"] += 1
            finally:
                self.queue.task_done()
                with self.stats_lock:
                    self.stats["in_coda"] = self.queue.qsize()

    def enqueue(
        self,
        *,
        percorso: str,
        hash_sha256: str,
        id_fasc: str,
        id_doc: str,
        nome_doc: str,
        tipo_doc: str,
        index_path: str,
    ) -> None:
        """Accoda un job OCR se il file e' di un tipo supportato."""
        if not ocr_supportato(nome_doc):
            return
        with self.stats_lock:
            self.stats["totale"] += 1
            self.stats["in_coda"] = self.queue.qsize() + 1
        self.queue.put((percorso, hash_sha256, id_fasc, id_doc, nome_doc, tipo_doc, index_path))


def build_ocr_runtime(*, decrypt_doc: Callable[[bytes], bytes]) -> OCRRuntime:
    """Factory esplicita per il runtime OCR."""
    return OCRRuntime(decrypt_doc=decrypt_doc)
