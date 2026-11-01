"""Il registro delle letture non si blocca mentre un altro processo scrive (verifica del 01/11/2026).

Senza WAL una scrittura lunga del giro di lettura faceva fallire con «database is locked» l'apertura del
registro nella Panoramica, nelle discordanze e nelle letture stesse.
"""

from __future__ import annotations

import sqlite3

from pct.registro_letture import repository as modulo
from pct.registro_letture.repository import RegistroLetture


def test_il_registro_usa_il_wal_e_prepara_lo_schema_una_volta(tmp_path, monkeypatch):
    percorso = tmp_path / "registro_letture.db"
    RegistroLetture(percorso)
    with sqlite3.connect(percorso) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    chiamate = []
    monkeypatch.setattr(modulo, "_allinea_vincolo_categorie", lambda *a: chiamate.append(a))
    RegistroLetture(percorso)
    assert chiamate == []  # schema già pronto in questo processo: nessuna DDL a ogni apertura


def test_si_apre_e_si_legge_mentre_un_altro_scrive(tmp_path):
    percorso = tmp_path / "registro_letture.db"
    RegistroLetture(percorso)
    scrittore = sqlite3.connect(percorso, isolation_level=None)
    try:
        scrittore.execute("BEGIN IMMEDIATE")
        scrittore.execute("CREATE TABLE prova_scrittura_lunga (x INTEGER)")
        modulo._SQLITE_PRONTI.clear()  # come un processo appena avviato
        registro = RegistroLetture(percorso)
        with registro.connection() as conn:
            conn.execute("PRAGMA busy_timeout = 1000")
            assert conn.execute("SELECT COUNT(*) FROM letture").fetchone()[0] == 0
    finally:
        scrittore.execute("ROLLBACK")
        scrittore.close()
