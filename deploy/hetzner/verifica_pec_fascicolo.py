"""Verifica del flusso «PEC → documenti del fascicolo», eseguita DENTRO il container scheduler-worker.

Per ogni studio attivo stampa solo conteggi: PEC collegate, messaggi completati, in attesa della conferma
dell'avvocato, ancora da elaborare, documenti ed .eml salvati, già presenti, scartati per motivo, errori,
ultimo salvataggio e ultimo giro del recupero; poi l'ultima esecuzione della pianificazione
``pec_fascicolo_documenti_recupero`` dalla console «Pianificazioni». Nessun dato del cliente: gli studi sono
numerati, non nominati, e degli errori esce solo il tipo.

Con la variabile ``RECUPERO=1`` esegue subito un lotto del recupero storico (``LIMITE`` messaggi per studio,
predefinito 50) prima di stampare lo stato, come il giro notturno.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T scheduler-worker python - < deploy/hetzner/verifica_pec_fascicolo.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

MARCATORE = "VERIFICA_PEC_FASCICOLO_JSON:"
JOB = "pec_fascicolo_documenti_recupero"


def _ultima_esecuzione(app: Any) -> dict[str, Any]:
    from pct.scheduler_registry import scheduler_registry_repository

    repo = scheduler_registry_repository(app.config)
    with repo.connect() as conn:  # sola lettura
        riga = conn.execute(
            "SELECT origin, status, started_at, finished_at, duration_ms FROM scheduled_job_runs WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (JOB,),
        ).fetchone()
    if not riga:
        return {"eseguita": False}
    return {"eseguita": True, "origine": riga[0], "esito": riga[1], "inizio": riga[2], "fine": riga[3],
            "durata_s": round(int(riga[4] or 0) / 1000, 1)}


def _diagnosi_collegamenti(repo: Any) -> dict[str, Any]:
    """Solo conteggi: perché una PEC non risulta collegata (ultimo esito del linker, famiglia dell'evento)."""
    t = repo.tenant_id
    ultimo = (
        "SELECT l.message_id, l.status, l.fascicolo_id FROM pec_fascicolo_links l "
        "JOIN (SELECT message_id, MAX(created_at) c FROM pec_fascicolo_links GROUP BY message_id) u "
        "ON u.message_id=l.message_id AND u.c=l.created_at"
    )
    with repo.connect() as conn:
        def gruppi(sql: str) -> dict[str, int]:
            return {str(r[0] or "(vuoto)"): int(r[1]) for r in conn.execute(sql, (t,)).fetchall()}

        return {
            "messaggi": int(conn.execute("SELECT COUNT(*) FROM pec_messages WHERE tenant_id=?", (t,)).fetchone()[0]),
            "per_stato_messaggio": gruppi("SELECT status, COUNT(*) FROM pec_messages WHERE tenant_id=? GROUP BY status"),
            "ultimo_esito_linker": gruppi(
                f"SELECT x.status || CASE WHEN x.fascicolo_id<>'' THEN ' (con fascicolo)' ELSE '' END, COUNT(*) "
                f"FROM ({ultimo}) x JOIN pec_messages m ON m.id=x.message_id WHERE m.tenant_id=? GROUP BY 1"),
            "senza_esito_linker": int(conn.execute(
                "SELECT COUNT(*) FROM pec_messages m WHERE m.tenant_id=? AND NOT EXISTS "
                "(SELECT 1 FROM pec_fascicolo_links l WHERE l.message_id=m.id)", (t,)).fetchone()[0]),
            "famiglia_non_collegate": gruppi(
                "SELECT e.family, COUNT(DISTINCT m.id) FROM pec_messages m JOIN pec_legal_events e ON e.message_id=m.id "
                "WHERE m.tenant_id=? AND m.linked_fascicolo_id='' GROUP BY e.family ORDER BY 2 DESC LIMIT 15"),
            "riconvalida_esiti": gruppi(
                "SELECT esito, COUNT(*) FROM pec_collegamento_certo_verifiche WHERE tenant_id=? GROUP BY esito ORDER BY 2 DESC")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='pec_collegamento_certo_verifiche'").fetchone() else {},
            "famiglia_collegate": gruppi(
                "SELECT e.family, COUNT(DISTINCT m.id) FROM pec_messages m JOIN pec_legal_events e ON e.message_id=m.id "
                "WHERE m.tenant_id=? AND m.linked_fascicolo_id<>'' GROUP BY e.family ORDER BY 2 DESC LIMIT 15"),
        }


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_worker import create_scheduler_app
    from web.services.pec_fascicolo_documenti_runtime import recupero_per_studi, stato_per_studi, studi_attivi
    from web.services.pec_pipeline_runtime import repository_from_paths

    app = create_scheduler_app()
    with app.app_context():
        studi = studi_attivi(app.config)
        recupero: dict[str, Any] = {}
        if os.getenv("RECUPERO", "").strip() == "1":
            esito = recupero_per_studi(studi, limite=max(1, int(os.getenv("LIMITE", "50") or 50)))
            recupero = {"ok": esito["ok"], "totali": esito["totals"]}
        stato = []
        for numero, voce in enumerate(stato_per_studi(studi), start=1):
            voce.pop("studio", None)
            stato.append({"studio": f"studio_{numero}", **voce})
        if os.getenv("DIAGNOSI", "").strip() == "1":
            for numero, (etichetta, paths) in enumerate(studi, start=1):
                try:
                    stato[min(numero, len(stato)) - 1]["diagnosi"] = _diagnosi_collegamenti(repository_from_paths(paths, tenant_label=etichetta))
                except Exception as exc:
                    stato[min(numero, len(stato)) - 1]["diagnosi"] = {"errore": type(exc).__name__}
        try:
            pianificazione = _ultima_esecuzione(app)
        except Exception as exc:  # registro delle pianificazioni non raggiungibile
            pianificazione = {"errore": type(exc).__name__}
    print(MARCATORE + json.dumps({"recupero": recupero, "studi": stato, "pianificazione": pianificazione}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
