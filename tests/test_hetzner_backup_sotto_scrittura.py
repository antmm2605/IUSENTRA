"""Il backup preventivo finisce anche se un altro processo scrive di continuo (deploy del 01/11/2026).

A blocchi con pausa SQLite ricominciava la copia a ogni scrittura: durante il recupero delle letture il backup
superava i 290 secondi e fermava il deploy.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing

from deploy.hetzner.backup_structured import _backup_sqlite


def test_backup_completo_mentre_un_altro_scrive(tmp_path):
    sorgente = tmp_path / "registro.db"
    with closing(sqlite3.connect(sorgente)) as conn:
        conn.execute("CREATE TABLE righe (testo TEXT)")
        conn.executemany("INSERT INTO righe VALUES (?)", [("x" * 2000,) for _ in range(20000)])
        conn.commit()
    ferma = threading.Event()

    def scrittore():
        with closing(sqlite3.connect(sorgente, timeout=30)) as conn:
            while not ferma.is_set():
                conn.execute("INSERT INTO righe VALUES ('nuova')")
                conn.commit()
                time.sleep(0.001)

    filo = threading.Thread(target=scrittore, daemon=True)
    filo.start()
    try:
        inizio = time.monotonic()
        esito = _backup_sqlite(sorgente, tmp_path / "copia" / "registro.db")
        durata = time.monotonic() - inizio
    finally:
        ferma.set()
        filo.join(timeout=5)
    assert esito["quick_check"] == "ok"
    assert durata < 30
    with closing(sqlite3.connect(tmp_path / "copia" / "registro.db")) as copia:
        assert copia.execute("SELECT COUNT(*) FROM righe").fetchone()[0] >= 20000
