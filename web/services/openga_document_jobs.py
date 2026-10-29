"""Coda persistente per studio: acquisizione pubblica senza approvare la scheda."""
import json
from base64 import b64decode
from binascii import Error as Base64Error
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock, Thread
from time import sleep

from pct import openga_documento, openga_html, openga_organi, openga_recupero
from pct.legal_update_job_queue import LegalUpdateJobQueue
from pct.openga_recupero import recupera_testo
from web.services.openga_search import document_identity


def _reader_fingerprint(paths):
    digest = sha256()
    for path in paths:
        digest.update(path.name.encode() + b"\\0" + path.read_bytes() + b"\\0")
    return digest.hexdigest()


# A parser hotfix must also invalidate old negative outcomes within the same
# release; successful documents remain reusable and are never discarded.
_READER_VERSION = _reader_fingerprint([
    Path(module.__file__) for module in (openga_documento, openga_html, openga_organi, openga_recupero)
] + [Path(__file__)])

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
                 ("relazione_id", "resource_id", "resource_sha256")},
                 "lettore_versione": _READER_VERSION},
        max_attempts=3, timeout_seconds=180)
    _retry_negative(queue, job.job_id, explicit=payload.get("riprova") is True)
    _ensure_worker(app, db_path)
    return status(db_path, job.job_id)



def _retry_negative(queue, job_id, *, explicit):
    # Atomic and scoped to this source. Preserve earlier outcomes, never reset
    # an acquired document, and never automatically retry the same reader twice.
    with queue.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM legal_update_jobs WHERE job_id=?",
                                 (job_id,)).fetchone()
        if not row or row["source_code"] != "openga_testo" or row["status"] not in {"completed", "failed", "timeout"}:
            return
        result = json.loads(row["result_json"])
        payload = json.loads(row["payload_json"])
        if result.get("stato") == "acquisito":
            return
        if not explicit and payload.get("lettore_versione") == _READER_VERSION:
            return
        history = payload.setdefault("tentativi_precedenti", [])
        history.append({"status": row["status"], "result": result,
                        "attempts": row["attempts"], "finished_at": row["finished_at"],
                        "last_error": row["last_error"],
                        "lettore_versione": payload.get("lettore_versione")})
        payload["lettore_versione"] = _READER_VERSION
        connection.execute(
            "UPDATE legal_update_jobs SET status='queued', attempts=0, result_json='{}', "
            "payload_json=?, last_error='', worker_id='', started_at='', finished_at='', updated_at=? "
            "WHERE job_id=?",
            (json.dumps(payload, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(), job_id))

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
