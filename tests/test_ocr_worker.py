from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

from pct.ocr_jobs import OCRJobStore
from pct.ocr_worker import serve_ocr_worker
from web.services.ocr_runtime import build_ocr_runtime


def test_ocr_runtime_persistente_accoda_job(tmp_path: Path):
    search_index = tmp_path / "search" / "index.db"
    queue_db = tmp_path / "search" / "ocr_jobs.db"
    runtime = build_ocr_runtime(queue_db_path=str(queue_db), search_index_path=str(search_index))

    runtime.enqueue(
        percorso=str(tmp_path / "documento.pdf"),
        hash_sha256="hash-001",
        id_fasc="FASC1",
        id_doc="DOC1",
        nome_doc="documento.pdf",
        tipo_doc="ATTO",
        index_path=str(search_index),
    )

    snapshot = runtime.status_snapshot()
    assert snapshot["enabled"] is True
    assert snapshot["in_coda"] == 1
    assert queue_db.exists()


def test_ocr_worker_processa_job_e_marca_completato(tmp_path: Path, monkeypatch):
    queue_db = tmp_path / "search" / "ocr_jobs.db"
    store = OCRJobStore(str(queue_db))
    index_path = tmp_path / "search" / "index.db"
    documento = tmp_path / "fascicoli" / "documenti" / "atto.pdf"
    documento.parent.mkdir(parents=True, exist_ok=True)
    documento.write_bytes(b"pdf-bytes")

    store.enqueue(
        percorso=str(documento),
        hash_sha256="hash-doc-ocr",
        id_fasc="FASC2",
        id_doc="DOC2",
        nome_doc="atto.pdf",
        tipo_doc="ATTO",
        index_path=str(index_path),
    )

    monkeypatch.setattr("pct.ocr_worker.ocr_estrai_testo", lambda payload, nome: "Testo OCR di prova")
    os.environ["PCT_OCR_QUEUE_DB"] = str(queue_db)
    os.environ["PCT_OCR_WORKERS"] = "1"

    stop_event = threading.Event()
    worker_thread = threading.Thread(target=serve_ocr_worker, kwargs={"stop_event": stop_event}, daemon=True)
    worker_thread.start()

    deadline = time.time() + 10
    snapshot = {}
    while time.time() < deadline:
        snapshot = store.status_snapshot()
        if snapshot["completati"] >= 1:
            break
        time.sleep(0.2)

    stop_event.set()
    worker_thread.join(timeout=5)
    os.environ.pop("PCT_OCR_QUEUE_DB", None)
    os.environ.pop("PCT_OCR_WORKERS", None)

    assert snapshot["completati"] >= 1
    assert snapshot["in_coda"] == 0
    assert snapshot["errori"] == 0


def test_ocr_job_store_fallback_su_delete_quando_wal_non_disponibile(monkeypatch, tmp_path: Path):
    commands: list[str] = []

    class FakeConnection:
        def __init__(self):
            self.row_factory = None

        def execute(self, sql, *args, **kwargs):
            commands.append(sql)
            if sql == "PRAGMA journal_mode = WAL":
                raise sqlite3.OperationalError("database is locked")
            return self

        def executescript(self, script):
            commands.append(script)
            return None

        def commit(self):
            return None

    monkeypatch.setattr("pct.ocr_jobs.sqlite3.connect", lambda *args, **kwargs: FakeConnection())

    OCRJobStore(str(tmp_path / "search" / "ocr_jobs.db"))

    assert "PRAGMA busy_timeout = 5000" in commands
    assert "PRAGMA journal_mode = WAL" in commands
    assert "PRAGMA journal_mode = DELETE" in commands
