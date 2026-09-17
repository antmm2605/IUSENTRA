"""Runtime OCR persistente per l'app Flask."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pct.ocr import estensione_supportata as ocr_supportato
from pct.ocr_jobs import OCRJobStore, default_ocr_queue_db
from pct.ocr_worker import serve_ocr_worker
from pct.runtime_env import is_managed_cloud_runtime


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
        self._embedded_stop_event: threading.Event | None = None
        self._embedded_thread: threading.Thread | None = None

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
    ) -> int | None:
        """Accoda un job OCR persistente se il file e' di un tipo supportato e non e' gia' stato letto."""
        if not ocr_supportato(nome_doc):
            return
        tenant_id, registro_path = _registro_per_job(id_fasc, id_doc, hash_sha256)
        if tenant_id is None:
            return
        return self.store.enqueue(
            percorso=percorso,
            hash_sha256=hash_sha256,
            id_fasc=id_fasc,
            id_doc=id_doc,
            nome_doc=nome_doc,
            tipo_doc=tipo_doc,
            index_path=index_path,
            tenant_id=tenant_id,
            registro_path=registro_path,
        )

    def status_snapshot(self) -> dict[str, Any]:
        snapshot = self.store.status_snapshot()
        if self._embedded_thread is not None:
            snapshot["embedded_worker"] = self._embedded_thread.is_alive()
        return snapshot

    def start_embedded_worker(self) -> bool:
        if self._embedded_thread is not None and self._embedded_thread.is_alive():
            return False
        self._embedded_stop_event = threading.Event()
        self._embedded_thread = threading.Thread(
            target=serve_ocr_worker,
            name="embedded-ocr-worker",
            kwargs={
                "stop_event": self._embedded_stop_event,
                "queue_db_path": str(self.store.db_path),
            },
            daemon=True,
        )
        self._embedded_thread.start()
        return True


def _registro_per_job(id_fasc: str, id_doc: str, hash_sha256: str) -> tuple[str | None, str]:
    """Studio e percorso del registro per il job; (None, "") se il documento e' gia' letto dall'OCR."""
    try:
        from pct.registro_letture import Oggetto
        from web.services.registro_letture_runtime import percorso_registro, registro_corrente, tenant_corrente

        tenant = tenant_corrente()
        registro = registro_corrente()
        oggetto = registro.oggetto(tenant, id_fasc, "documento", id_doc)
        if oggetto is None:
            oggetto = Oggetto(tipo="documento", oggetto_id=str(id_doc), sha256_archivio=str(hash_sha256 or ""))
        if str(hash_sha256 or "").strip().lower() == str(oggetto.sha256_archivio or "").strip().lower():
            if not registro.da_leggere(tenant, id_fasc, "ocr", oggetti=[oggetto]):
                return None, ""
        return tenant, percorso_registro()
    except Exception:
        return "", ""


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def build_ocr_runtime(
    *,
    queue_db_path: str | None = None,
    search_index_path: str = "",
    auto_start_embedded: bool | None = None,
) -> OCRRuntime:
    """Factory esplicita per il runtime OCR persistente."""
    resolved_queue_path = queue_db_path or default_ocr_queue_db(search_index_path)
    Path(resolved_queue_path).parent.mkdir(parents=True, exist_ok=True)
    runtime = OCRRuntime(queue_db_path=resolved_queue_path)
    if auto_start_embedded is None:
        auto_start_embedded = (
            is_managed_cloud_runtime()
            and str(os.getenv("PCT_EMBEDDED_OCR", "1") or "1").strip().lower() not in {"0", "false", "no"}
        )
    if auto_start_embedded:
        runtime.start_embedded_worker()
    return runtime
