"""Completa l'indice FTS di Normattiva nel container applicativo (incrementale, nessun dato dello studio).

Serve quando un aggiornamento degli archivi normativi si interrompe dopo aver aggiunto testi ma prima di
indicizzarli: la verifica «cataloghi normativi» del deploy fallisce con «indice FTS incompleto». Stampa solo
i conteggi.

Uso: docker exec -i iusentra-app python - < deploy/hetzner/sincronizza_fts_lex.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys


def main() -> int:
    sys.path.insert(0, "/app")
    from lex.ricerca_giuridica.indice_fts import sincronizza_fts

    db = os.environ.get("PCT_NORMATTIVA_DB") or "/data/normativa/normattiva.sqlite"
    conn = sqlite3.connect(db, timeout=120)
    try:
        conn.execute("PRAGMA busy_timeout = 120000")
        esito = sincronizza_fts(conn, blocco=2000)
        chunk = int(conn.execute("SELECT COUNT(*) FROM normative_chunks").fetchone()[0])
        fts = int(conn.execute("SELECT COUNT(*) FROM normative_fts_info").fetchone()[0])
    finally:
        conn.close()
    print(json.dumps({"indicizzati": esito.indicizzati, "orfani": esito.orfani, "chunk": chunk, "chunk_fts": fts,
                      "secondi": round(esito.secondi, 1)}))
    return 0 if chunk == fts else 1


if __name__ == "__main__":
    raise SystemExit(main())
