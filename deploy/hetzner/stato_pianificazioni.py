"""Stato delle pianificazioni dello scheduler, eseguito DENTRO il container scheduler-worker.

Per ogni pianificazione: attiva o spenta, ultima esecuzione (esito, inizio, fine, durata) e conteggio degli esiti
nelle ultime 48 ore. Nessun dato del cliente: dell'errore esce solo la prima riga, con identificativi mascherati.

Con la variabile ``ATTIVA`` (identificativi separati da virgola) riaccende pianificazioni spente, come
l'interruttore della console. Con la variabile ``ESEGUI`` (identificativi separati da virgola) chiede un'esecuzione manuale, come il pulsante
«Esegui» della console «Pianificazioni»; il worker la avvia entro un minuto.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T -e ESEGUI=... scheduler-worker python - < deploy/hetzner/stato_pianificazioni.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

MARCATORE = "STATO_PIANIFICAZIONI_JSON:"
_ID = re.compile(r"\b[0-9A-Fa-f]{8,}\b|\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def _breve(testo: Any) -> str:
    riga = str(testo or "").strip().splitlines()[0] if str(testo or "").strip() else ""
    return _ID.sub("<ID>", riga)[:160]


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_registry import scheduler_registry_repository
    from pct.scheduler_worker import create_scheduler_app

    app = create_scheduler_app()
    repo = scheduler_registry_repository(app.config)
    accese = []
    for job_id in [j.strip() for j in os.getenv("ATTIVA", "").split(",") if j.strip()]:
        try:
            repo.save_job(job_id, {"enabled": True}, updated_by="verifica-claude")
            accese.append({"job": job_id, "esito": "attivata"})
        except Exception as exc:  # pianificazione sconosciuta
            accese.append({"job": job_id, "esito": _breve(f"{type(exc).__name__}: {exc}")})
    richieste = [j.strip() for j in os.getenv("ESEGUI", "").split(",") if j.strip()]
    avviati = []
    for job_id in richieste:
        try:
            esito = repo.request_manual_run(job_id, requested_by="verifica-claude", dedupe_open=True)
            avviati.append({"job": job_id, "esito": _breve(esito.get("status") or esito.get("message") or "richiesto")})
        except Exception as exc:  # pianificazione sconosciuta o già in corso
            avviati.append({"job": job_id, "esito": _breve(f"{type(exc).__name__}: {exc}")})
    dal = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    pianificazioni = []
    with repo.connect() as conn:  # sola lettura
        for job in repo.list_jobs(include_disabled=True):
            job_id = str(job.get("job_id") or "")
            ultima = conn.execute(
                "SELECT origin, status, started_at, finished_at, duration_ms, message, error_message FROM scheduled_job_runs "
                "WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,),
            ).fetchone()
            conteggi = {r[0]: r[1] for r in conn.execute(
                "SELECT status, COUNT(*) FROM scheduled_job_runs WHERE job_id = ? AND created_at >= ? GROUP BY status",
                (job_id, dal),
            ).fetchall()}
            voce: dict[str, Any] = {
                "job": job_id, "nome": str(job.get("name") or ""), "attiva": bool(job.get("enabled")),
                "orario": " ".join(str(job.get(k) or "") for k in ("day_of_week", "hour", "minute")).strip(),
                "ultime_48h": conteggi,
            }
            if ultima:
                voce["ultima"] = {
                    "origine": ultima[0], "esito": ultima[1], "inizio": ultima[2], "fine": ultima[3],
                    "durata_s": round(int(ultima[4] or 0) / 1000, 1), "messaggio": _breve(ultima[5]), "errore": _breve(ultima[6]),
                }
            pianificazioni.append(voce)
    print(MARCATORE + json.dumps({"accese": accese, "avviati": avviati, "pianificazioni": pianificazioni}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
