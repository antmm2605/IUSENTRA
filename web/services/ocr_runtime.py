"""Runtime OCR persistente per l'app Flask."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pct.ocr import estensione_supportata as ocr_supportato
from pct.ocr_jobs import OCRJobStore, default_ocr_queue_db


@dataclass(slots=True)
class OCRQueueProxy:
    store: OCRJobStore

    def qsize(self) -> int:
        return self.store.pending_count()


class OCRRuntime:
    """Incapsula la coda OCR persistente condivisa con il worker dedicato."""

    def __init__(self, *, queue_db_path: str) -> None:
        self.store = OCRJobStore(queue_db_path)
        self.queue = OCRQueueProxy(self.store)

    @property
    def stats(self) -> dict[str, Any]:
        return self.status_snapshot()

    @property
    def stats_lock(self):
        return _NullLock()

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
        """Accoda un job OCR persistente se il file e' di un tipo supportato."""
        if not ocr_supportato(nome_doc):
            return
        self.store.enqueue(
            percorso=percorso,
            hash_sha256=hash_sha256,
            id_fasc=id_fasc,
            id_doc=id_doc,
            nome_doc=nome_doc,
            tipo_doc=tipo_doc,
            index_path=index_path,
        )

    def status_snapshot(self) -> dict[str, Any]:
        return self.store.status_snapshot()


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def build_ocr_runtime(*, queue_db_path: str | None = None, search_index_path: str = "") -> OCRRuntime:
    """Factory esplicita per il runtime OCR persistente."""
    resolved_queue_path = queue_db_path or default_ocr_queue_db(search_index_path)
    Path(resolved_queue_path).parent.mkdir(parents=True, exist_ok=True)
    return OCRRuntime(queue_db_path=resolved_queue_path)
