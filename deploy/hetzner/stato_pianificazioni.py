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


def _riepilogo_letture(percorso: str) -> dict[str, Any]:
    """Sola lettura: per lettore letti, da leggere, errori e riletture senza variazioni (solo conteggi)."""

    import sqlite3

    da24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    da48 = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    try:
        conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=10)
    except Exception as exc:
        return {"errore": _breve(f"{type(exc).__name__}: {exc}")}
    try:
        esito: dict[str, Any] = {
            "fascicoli": conn.execute("SELECT COUNT(DISTINCT fascicolo_id) FROM letture_oggetti WHERE presente = 1").fetchone()[0],
            "oggetti_presenti": dict(conn.execute(
                "SELECT tipo, COUNT(*) FROM letture_oggetti WHERE presente = 1 GROUP BY tipo").fetchall()),
            "lettori": {},
        }
        # Solo i lettori censiti: le righe storiche di lettori tolti dal censimento (sentenza_da_archiviare,
        # presidio_pec, sostituiti da proposta_definizione e motore_pec) non sono code reali.
        try:
            from pct.registro_letture.lettori import LETTORI as censiti
        except Exception:
            censiti = None
        lettori = [r[0] for r in conn.execute("SELECT DISTINCT lettore FROM letture").fetchall() if censiti is None or r[0] in censiti]
        for lettore in lettori:
            # Tipi che il lettore legge davvero: un lettore PEC non deve risultare «indietro» sui documenti.
            tipi = [r[0] for r in conn.execute("SELECT DISTINCT tipo FROM letture WHERE lettore = ?", (lettore,)).fetchall()]
            segnaposto = ",".join("?" * len(tipi))
            stati = dict(conn.execute(
                f"SELECT l.stato, COUNT(*) FROM letture_oggetti o JOIN letture l ON l.tenant_id = o.tenant_id "
                f"AND l.fascicolo_id = o.fascicolo_id AND l.tipo = o.tipo AND l.oggetto_id = o.oggetto_id AND l.sha256 = o.sha256 "
                f"AND l.lettore = ? WHERE o.presente = 1 AND o.tipo IN ({segnaposto}) GROUP BY l.stato", (lettore, *tipi)).fetchall())
            da_leggere = conn.execute(
                f"SELECT COUNT(*) FROM letture_oggetti o WHERE o.presente = 1 AND o.tipo IN ({segnaposto}) AND NOT EXISTS ("
                f"SELECT 1 FROM letture l WHERE l.tenant_id = o.tenant_id AND l.fascicolo_id = o.fascicolo_id AND l.tipo = o.tipo "
                f"AND l.oggetto_id = o.oggetto_id AND l.sha256 = o.sha256 AND l.lettore = ?)", (*tipi, lettore)).fetchone()[0]
            # Riletture senza variazioni: lettura aggiornata nelle ultime 24 ore su un oggetto invariato da oltre 48 ore,
            # già letto con la stessa impronta prima di 48 ore fa.
            riletti = conn.execute(
                "SELECT COUNT(*) FROM letture l JOIN letture_oggetti o ON l.tenant_id = o.tenant_id AND l.fascicolo_id = o.fascicolo_id "
                "AND l.tipo = o.tipo AND l.oggetto_id = o.oggetto_id AND l.sha256 = o.sha256 "
                "WHERE l.lettore = ? AND l.aggiornato_il >= ? AND l.letto_il < ? AND o.aggiornato_il < ?",
                (lettore, da24, da48, da48)).fetchone()[0]
            fascicoli = dict(conn.execute(
                "SELECT stato, COUNT(*) FROM letture_fascicoli WHERE lettore = ? GROUP BY stato", (lettore,)).fetchall())
            esito["lettori"][lettore] = {
                "tipi": tipi, "esiti": stati, "da_leggere": da_leggere, "riletti_24h_senza_variazioni": riletti,
                "fascicoli": fascicoli, "letti_24h": conn.execute(
                    "SELECT COUNT(*) FROM letture WHERE lettore = ? AND aggiornato_il >= ?", (lettore, da24)).fetchone()[0],
            }
        return esito
    except Exception as exc:
        return {"errore": _breve(f"{type(exc).__name__}: {exc}")}
    finally:
        conn.close()


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
            fallita = conn.execute(
                "SELECT started_at, error_message FROM scheduled_job_runs WHERE job_id = ? AND status = 'failed' "
                "ORDER BY id DESC LIMIT 1", (job_id,),
            ).fetchone()
            if fallita:
                voce["ultimo_fallimento"] = {"inizio": fallita[0], "errore": _breve(fallita[1])}
            pianificazioni.append(voce)
        notti = []
        try:  # la catena notturna delle ultime due sere (le prove «prova-…» escluse)
            for sera, conclusa, aggiornata in conn.execute(
                "SELECT sera, conclusa, aggiornata FROM notte_avanzamento WHERE sera NOT LIKE 'prova-%' ORDER BY sera DESC LIMIT 2"
            ).fetchall():
                passi = [
                    {"fase": r[0], "lavoro": r[1], "esito": r[2], "secondi": round(float(r[3] or 0), 1), "messaggio": _breve(r[4])}
                    for r in conn.execute(
                        "SELECT fase, lavoro, esito, secondi, messaggio FROM notte_passi WHERE sera = ? ORDER BY indice", (sera,)
                    ).fetchall()
                ]
                notti.append({"sera": sera, "conclusa": bool(conclusa), "aggiornata": aggiornata, "passi": passi})
        except Exception as exc:
            notti.append({"errore": _breve(f"{type(exc).__name__}: {exc}")})
    registri = []
    import glob
    import sqlite3
    for percorso in sorted(set(glob.glob("/data/**/intelligence/registro_letture.db", recursive=True))):
        voce = {"file_mb": round(os.path.getsize(percorso) / 1e6, 1)}
        wal = percorso + "-wal"
        voce["wal_mb"] = round(os.path.getsize(wal) / 1e6, 1) if os.path.exists(wal) else None
        try:  # sola lettura: la domanda non cambia la modalità
            conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=5)
            voce["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
            conn.close()
        except Exception as exc:
            voce["journal_mode"] = _breve(f"{type(exc).__name__}: {exc}")
        voce["letture"] = _riepilogo_letture(percorso)
        registri.append(voce)
    disaccordi = []
    if os.getenv("DISACCORDI"):
        # Solo identificativi opachi e voci del catalogo: nessun nome, testo o dato del cliente.
        for percorso in sorted(set(glob.glob("/data/**/intelligence/classificatore_disaccordi.json", recursive=True))):
            for voce in json.loads(open(percorso, encoding="utf-8").read()):
                disaccordi.append({k: voce.get(k) for k in ("document_id", "fascicolo_id", "voce_regole",
                                                              "confidenza_regole", "voce_modello", "probabilita")})
    print(MARCATORE + json.dumps({"accese": accese, "avviati": avviati, "registri_letture": registri, "notti": notti, "disaccordi": disaccordi, "pianificazioni": pianificazioni}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
