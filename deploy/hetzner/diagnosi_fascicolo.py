"""Diagnosi della lettura di UN fascicolo, eseguita DENTRO il container scheduler-worker (sola lettura).

Stato dell'evento di lettura, ultimi esiti, stato per lettore e documenti in attesa. Escono solo identificativi,
stati, conteggi e messaggi d'errore tecnici troncati con identificativi mascherati: nessun testo dei documenti,
nessun nome. Con ``RIACCODA=1`` mette in coda un nuovo evento prioritario per quel solo fascicolo, come il
pulsante «Leggi i nuovi» della Lettura (nessuna lettura qui: la esegue il giro della coda).

Uso: docker compose ... exec -T -e FASCICOLO=<id> [-e RIACCODA=1] scheduler-worker python - < deploy/hetzner/diagnosi_fascicolo.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import sqlite3
import sys

MARCATORE = "DIAGNOSI_FASCICOLO_JSON:"
_ID = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def _breve(testo) -> str:
    return _ID.sub("<email>", str(testo or "").strip().splitlines()[0] if str(testo or "").strip() else "")[:200]


def _righe(conn, sql, parametri=()):
    try:
        cur = conn.execute(sql, parametri)
        nomi = [d[0] for d in cur.description]
        return [dict(zip(nomi, r)) for r in cur.fetchall()]
    except Exception as exc:
        return [{"errore": _breve(f"{type(exc).__name__}: {exc}")}]


def main() -> int:
    fascicolo = re.sub(r"[^0-9A-Za-z_-]", "", os.getenv("FASCICOLO", ""))
    if not fascicolo:
        print(MARCATORE + json.dumps({"errore": "FASCICOLO mancante"}))
        return 1
    percorsi = sorted(glob.glob("/data/**/intelligence/registro_letture.db", recursive=True), key=os.path.getsize, reverse=True)
    esito = {"fascicolo": fascicolo, "registri": []}
    for percorso in percorsi:
        conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=10)
        oggetti = _righe(conn, "SELECT tenant_id FROM letture_oggetti WHERE fascicolo_id=? LIMIT 1", (fascicolo,))
        if not oggetti or "tenant_id" not in oggetti[0]:
            conn.close()
            continue
        tenant = oggetti[0]["tenant_id"]
        voce = {"registro_mb": round(os.path.getsize(percorso) / 1e6, 1)}
        voce["eventi"] = [{k: (_breve(v) if isinstance(v, str) and k in ("errore", "error", "ultimo_errore", "last_error") else v)
                           for k, v in r.items() if k not in ("tenant_id",)}
                          for r in _righe(conn, "SELECT * FROM letture_eventi WHERE fascicolo_id=?", (fascicolo,))]
        voce["ultimi_esiti"] = [{k: (_breve(v) if k == "errore" else v) for k, v in r.items() if k not in ("tenant_id", "id")}
                                for r in _righe(conn, "SELECT * FROM letture_eventi_esiti WHERE fascicolo_id=? ORDER BY iniziato_il DESC LIMIT 8", (fascicolo,))]
        voce["lettori_fascicolo"] = _righe(conn, "SELECT lettore, stato, oggetti_totali, oggetti_letti, versione_lettore, aggiornato_il "
                                                 "FROM letture_fascicoli WHERE fascicolo_id=?", (fascicolo,))
        voce["da_leggere_per_lettore"] = _righe(conn, """
            SELECT l.lettore, COUNT(*) AS da_leggere FROM letture_oggetti o
            JOIN (SELECT DISTINCT lettore FROM letture WHERE fascicolo_id=?) l
            WHERE o.fascicolo_id=? AND o.presente=1 AND NOT EXISTS (SELECT 1 FROM letture x WHERE x.fascicolo_id=o.fascicolo_id
              AND x.tipo=o.tipo AND x.oggetto_id=o.oggetto_id AND x.sha256=o.sha256 AND x.lettore=l.lettore AND x.stato<>'in_corso')
            GROUP BY l.lettore""", (fascicolo, fascicolo))
        voce["letture_non_concluse"] = [{**r, "esito_json": _breve(r.get("esito_json"))} for r in _righe(conn,
            "SELECT tipo, oggetto_id, lettore, stato, versione_lettore, aggiornato_il, esito_json FROM letture "
            "WHERE fascicolo_id=? AND stato IN ('errore','in_corso') ORDER BY aggiornato_il DESC LIMIT 20", (fascicolo,))]
        conn.close()
        if os.getenv("RIACCODA") == "1":
            sys.path.insert(0, "/app")
            from pct.registro_letture.repository import RegistroLetture

            generazione = RegistroLetture(percorso).accoda_evento(tenant, fascicolo, forza=True, prioritario=True)
            voce["riaccodato"] = {"generazione": generazione}
        esito["registri"].append(voce)
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
