"""Semaforo su SQLite condiviso: un titolare con affitto e una coda ordinata per priorità e arrivo."""

from __future__ import annotations

import os
import socket
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS semaforo (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    titolare TEXT NOT NULL, motore TEXT NOT NULL, processo TEXT NOT NULL,
    priorita INTEGER NOT NULL, preso_alle REAL NOT NULL, scade_alle REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS coda (
    titolare TEXT PRIMARY KEY, motore TEXT NOT NULL, processo TEXT NOT NULL,
    priorita INTEGER NOT NULL, entrato_alle REAL NOT NULL, scade_alle REAL NOT NULL
);
"""


def processo_corrente() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class Semaforo:
    def __init__(self, db_path: str | Path, *, affitto_secondi: float = 120.0, orologio=time.time) -> None:
        self.db_path = Path(db_path)
        self.affitto = float(affitto_secondi)
        self.orologio = orologio
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _pulisci(self, conn: sqlite3.Connection, ora: float) -> None:
        conn.execute("DELETE FROM semaforo WHERE scade_alle < ?", (ora,))
        conn.execute("DELETE FROM coda WHERE scade_alle < ?", (ora,))

    def prova(self, titolare: str, motore: str, priorita: int) -> bool:
        """Entra (o resta) in coda; prende il semaforo se è libero e si è i primi della coda."""
        ora = self.orologio()
        with closing(self._conn()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._pulisci(conn, ora)
                attuale = conn.execute("SELECT titolare FROM semaforo WHERE id=1").fetchone()
                if attuale and attuale["titolare"] == titolare:
                    conn.execute("UPDATE semaforo SET scade_alle=? WHERE id=1", (ora + self.affitto,))
                    conn.execute("COMMIT")
                    return True
                conn.execute(
                    "INSERT INTO coda VALUES (?,?,?,?,?,?) ON CONFLICT(titolare) DO UPDATE SET scade_alle=excluded.scade_alle",
                    (titolare, motore, processo_corrente(), int(priorita), ora, ora + self.affitto),
                )
                primo = conn.execute("SELECT titolare FROM coda ORDER BY priorita, entrato_alle LIMIT 1").fetchone()
                preso = attuale is None and primo is not None and primo["titolare"] == titolare
                if preso:
                    conn.execute("DELETE FROM coda WHERE titolare=?", (titolare,))
                    conn.execute("INSERT INTO semaforo VALUES (1,?,?,?,?,?,?)",
                                 (titolare, motore, processo_corrente(), int(priorita), ora, ora + self.affitto))
                conn.execute("COMMIT")
                return preso
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def rinnova(self, titolare: str) -> bool:
        ora = self.orologio()
        with closing(self._conn()) as conn:
            cur = conn.execute("UPDATE semaforo SET scade_alle=? WHERE id=1 AND titolare=?", (ora + self.affitto, titolare))
            return cur.rowcount == 1

    def rilascia(self, titolare: str) -> None:
        with closing(self._conn()) as conn:
            conn.execute("DELETE FROM semaforo WHERE titolare=?", (titolare,))
            conn.execute("DELETE FROM coda WHERE titolare=?", (titolare,))

    def stato(self) -> dict[str, Any]:
        ora = self.orologio()
        with closing(self._conn()) as conn:
            attuale = conn.execute("SELECT * FROM semaforo WHERE id=1 AND scade_alle>=?", (ora,)).fetchone()
            coda = conn.execute("SELECT * FROM coda WHERE scade_alle>=? ORDER BY priorita, entrato_alle", (ora,)).fetchall()
        in_corso = attuale["motore"] if attuale else ""
        attesa = [r["motore"] for r in coda]
        testo = f"In corso: {in_corso or 'nessun motore'}; in coda: {', '.join(attesa) if attesa else 'nessuno'}."
        return {
            "in_corso": in_corso,
            "da_secondi": round(ora - attuale["preso_alle"]) if attuale else 0,
            "processo": attuale["processo"] if attuale else "",
            "in_coda": attesa,
            "testo": testo,
        }
