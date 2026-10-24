"""Coda persistente per studio: acquisizione pubblica senza approvare la scheda."""
from base64 import b64decode
from binascii import Error as Base64Error
from hashlib import sha256
from pathlib import Path
from threading import Lock, Thread
from time import sleep

from pct.legal_update_job_queue import LegalUpdateJobQueue
from pct.openga_recupero import recupera_testo
from web.services.openga_search import document_identity

_LOCK = Lock()
_RUNNING = set()


def _queue(db_path):
    # db_path viene dal manager tenant-aware, mai dal payload del browser.
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError("Archivio dello studio non configurato.")
    return LegalUpdateJobQueue(path.with_name(path.stem + "-letture-ufficiali.db"))


def start(app, *, db_path, payload):
    identity = document_identity(payload, app.config)
    queue = _queue(db_path)
    key = sha256(("openga-lettura-v1:" + payload["relazione_id"] + ":" +
                  payload["resource_id"] + ":" + payload["resource_sha256"]).encode()).hexdigest()
    job = queue.enqueue(source_code="openga_testo", dedupe_key=key,
        payload={"identita": identity, "catalogo": {k: payload[k] for k in
                 ("relazione_id", "resource_id", "resource_sha256")}},
        max_attempts=3, timeout_seconds=180)
    _ensure_worker(app, db_path)
    return status(db_path, job.job_id)


def status(db_path, job_id):
    queue = _queue(db_path)
    job = queue.get(job_id)
    if job is None or job.source_code != "openga_testo":
        raise KeyError("Lettura non presente in questo studio.")
    if job.status == "completed":
        result = dict(job.result or {})
        if "documento" in result:
            doc = result["documento"]
            try:
                raw = b64decode(doc["originale_base64"], validate=True)
                valid = (sha256(raw).hexdigest() == doc["raw_sha256"]
                         and sha256(doc["testo"].encode()).hexdigest() == doc["provenienza"]["sha256"])
            except (KeyError, TypeError, ValueError, Base64Error):
                valid = False
            if not valid:
                return {"ok": False, "job_id": job.job_id, "stato": "intervento_necessario",
                        "message": "Integrità della lettura non riscontrata: ripetere la verifica."}
            result["documento"] = {k: v for k, v in doc.items() if k != "originale_base64"}
        return {"ok": True, "job_id": job.job_id, **result}
    if job.status in {"failed", "timeout"}:
        return {"ok": False, "job_id": job.job_id, "stato": "intervento_necessario",
                "message": "Lettura interrotta: nessun testo è stato certificato."}
    return {"ok": True, "job_id": job.job_id, "stato": "in_corso",
            "message": "Recupero e verifica del testo ufficiale in corso."}


def _ensure_worker(app, db_path):
    with _LOCK:
        if db_path in _RUNNING:
            return
        _RUNNING.add(db_path)
    Thread(target=_run, args=(app, db_path), daemon=True, name="lettura-ufficiale").start()


def resume(app, db_path):
    # Il polling riattiva soltanto i job già autorizzati, mai nuove acquisizioni.
    _ensure_worker(app, db_path)


def _run(app, db_path):
    queue = _queue(db_path)
    try:
        with app.app_context():
            while job := queue.claim_next(worker_id="openga-lettura"):
                try:
                    result = recupera_testo(job.payload["identita"])
                    if result.get("stato") == "in_attesa":
                        queue.fail(job.job_id, error="Fonte temporaneamente occupata.")
                        sleep(2)
                        continue
                    queue.complete(job.job_id, result=result)
                except (OSError, ValueError, RuntimeError, KeyError):
                    queue.fail(job.job_id, error="Acquisizione non completata.")
                    app.logger.warning("Lettura ufficiale non completata, job %s", job.job_id)
    finally:
        with _LOCK:
            _RUNNING.discard(db_path)
