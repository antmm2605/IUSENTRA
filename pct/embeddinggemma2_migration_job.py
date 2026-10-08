"""Prima costruzione esplicita: lotti nativi brevi, senza cambiare il modello attivo."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from pct.embeddinggemma2 import runtime_profile

JOB_ID = "embeddinggemma2_initial_normattiva"


def enabled(config=None):
    value = (config or {}).get("IUSENTRA_EMBEDDING_INITIAL_BUILD")
    if value is None:
        value = os.environ.get("IUSENTRA_EMBEDDING_INITIAL_BUILD", "0")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def candidate_folder(db):
    revision, suffix = runtime_profile("litert")
    return Path(db).parent / ("vettori_normattiva_" + revision + "_" + suffix.replace("-", "_"))


def preparation_snapshot(config=None):
    """Solo metadati del candidato: nessuna scansione o inferenza nella GET."""
    config = config or {}
    db = config.get("NORMATTIVA_DB") or os.getenv("PCT_NORMATTIVA_DB") or "/data/normativa/normattiva.sqlite"
    path = candidate_folder(db) / "meta.json"
    if not path.is_file():
        return {"present": False}
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        state = meta.get("prima_costruzione") or {}
        rows, total = int(meta.get("righe", 0)), int(state.get("totale_iniziale", 0))
        if rows < 0 or total <= 0 or not state:
            raise ValueError("Metadati della preparazione non validi")
        stage = "building"
        if state.get("completa") is True:
            stage = "validation_required" if meta.get("riconvalida_finale_richiesta") is not False else "prepared"
        return {"present": True, "stage": stage, "rows": rows, "total": total,
                "local_only": True, "model": "EmbeddingGemma 2"}
    except (OSError, ValueError, TypeError, AttributeError):
        return {"present": True, "stage": "error",
                "message": "Avanzamento della preparazione non disponibile. Il motore operativo resta attivo."}


def run_registered_batch(config, repository):
    """L'autorizzazione SQL governa avvio, backoff persistente e arresto finale."""
    registered = repository.get_job(JOB_ID)
    if not registered or not registered.get("enabled"):
        return {"ok": True, "status": "disabled", "note": "Preparazione disattivata nel registro lavori"}
    base_interval = max(2, int(registered.get("interval_minutes") or 2))
    if registered.get("updated_by") == "embeddinggemma2:retry-backoff":
        with repository.connect() as conn:
            previous = conn.execute("SELECT result_json FROM scheduled_job_runs WHERE job_id=? AND status='failed' ORDER BY id DESC LIMIT 1", (JOB_ID,)).fetchone()
        if previous:
            base_interval = max(2, int(json.loads(previous[0]).get("base_interval_minutes", base_interval)))
    result = run_initial_batch({**config, "IUSENTRA_EMBEDDING_INITIAL_BUILD": True})
    if result["status"] == "awaiting_validation":
        repository.save_job(JOB_ID, {"enabled": False}, updated_by="embeddinggemma2:construction-finished")
    elif not result.get("ok"):
        interval = max(2, int(registered.get("interval_minutes") or 2))
        repository.save_job(JOB_ID, {"interval_minutes": min(60, interval * 2)},
                            updated_by="embeddinggemma2:retry-backoff")
        result["retry_minutes"] = min(60, interval * 2)
        result["base_interval_minutes"] = base_interval
    elif registered.get("updated_by") == "embeddinggemma2:retry-backoff":
        repository.save_job(JOB_ID, {"interval_minutes": base_interval}, updated_by="embeddinggemma2:retry-recovered")
    if not result.get("ok"):
        result["error"] = result["note"]
    return result


def run_initial_batch(config=None):
    """Lo scheduler registra ritorno ed errori nel proprio repository SQL."""
    config = config or {}
    if not enabled(config):
        return {"ok": True, "status": "disabled", "note": "Costruzione iniziale non attivata"}
    db = Path(config.get("NORMATTIVA_DB") or os.getenv("PCT_NORMATTIVA_DB")
              or "/data/normativa/normattiva.sqlite")
    folder = candidate_folder(db)
    if not db.is_file():
        return {"ok": False, "status": "error", "note": "Archivio normativo locale assente"}
    meta_path = folder / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        state = meta.get("prima_costruzione") or {}
        validating = state.get("completa") is True and meta.get("riconvalida_finale_richiesta") is not False
        if state.get("completa") is True and not validating:
            return {"ok": True, "status": "awaiting_validation", "rows": meta.get("righe", 0),
                    "note": "Prima costruzione conclusa; riconvalida finale e attivazione separate"}
        env = os.environ.copy()
        env.update(IUSENTRA_EMBEDDING_PROVIDER="embeddinggemma2_local",
                   IUSENTRA_EMBEDDING_RUNTIME="litert", LEX_EMBED_PARALLELI="1")
        # Il processo figlio importa il profilo candidato senza cambiare
        # l'ambiente o gli embedder già caricati nel worker dello studio.
        launcher = (
            "import sys; from pct.sync import FileLock; "
            "from lex.ricerca_giuridica.indice_vettoriale import main; "
            "\nwith FileLock(sys.argv[1]):\n    raise SystemExit(main(sys.argv[2:]))"
        )
        command = [sys.executable, "-c", launcher, str(folder / "meta.json"), "aggiorna",
                   "--db", str(db), "--out", str(folder),
                   "--riconvalida-finale" if validating else "--prima-costruzione",
                   "--tempo-massimo-s", "60", "--batch", "1", "--paralleli", "1"]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=240)
        if result.returncode:
            return {"ok": False, "status": "error", "returncode": result.returncode,
                    "note": (result.stderr or result.stdout)[-2000:]}
        # Il checkpoint iniziale può precedere un altro lotto in attesa del
        # lock. Il contatore nativo del processo figlio misura soltanto il
        # proprio lavoro; la differenza tra due metadati conterebbe anche
        # le consegne dell'altro processo.
        native = json.loads(result.stdout.strip().splitlines()[-1])
        added = native["nuovi"]
        if type(added) is not int or added < 0:
            raise ValueError("Esito del costruttore nativo non valido")
        after = json.loads(meta_path.read_text(encoding="utf-8"))
        return {"ok": True, "status": "validating" if validating else "building", "rows": int(after.get("righe", 0)),
                "added": added,
                "checkpoint": after.get("prima_costruzione"),
                "note": "Lotto salvato; il modello operativo resta invariato"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "note": "Lotto interrotto al limite; ripresa dal checkpoint nativo"}
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        return {"ok": False, "status": "error", "note": str(exc)}
