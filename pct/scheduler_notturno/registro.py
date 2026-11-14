"""Registro dell'avanzamento notturno su SQLite: dove è arrivata la catena, esito e durata di ogni passo."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS notte_avanzamento (
    sera TEXT PRIMARY KEY,
    partenza INTEGER NOT NULL DEFAULT 0,
    indice INTEGER NOT NULL DEFAULT 0,
    passo_avviato_alle TEXT NOT NULL DEFAULT '',
    ripresa_da TEXT NOT NULL DEFAULT '',
    conclusa INTEGER NOT NULL DEFAULT 0,
    aggiornata TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS notte_passi (
    sera TEXT NOT NULL,
    indice INTEGER NOT NULL,
    fase INTEGER NOT NULL,
    lavoro TEXT NOT NULL,
    esito TEXT NOT NULL,
    messaggio TEXT NOT NULL DEFAULT '',
    avvio TEXT NOT NULL DEFAULT '',
    fine TEXT NOT NULL DEFAULT '',
    secondi REAL NOT NULL DEFAULT 0,
    memoria_libera_mb INTEGER NOT NULL DEFAULT 0,
    risultato_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (sera, indice)
);
CREATE TABLE IF NOT EXISTS ai_esiti (
    quando TEXT NOT NULL,
    principale TEXT NOT NULL,
    riserva TEXT NOT NULL,
    esito TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT ''
);
"""

ESITI_ITALIANI = {
    "completato": "Completato",
    "fallito": "Non riuscito",
    "saltato": "Non previsto stanotte",
    "spento": "Pianificazione spenta",
    "rinviato": "Rinviato",
    "in_corso": "In corso",
}


class RegistroNotte:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as conn:
            conn.executescript(SCHEMA)
            if not self._ha_risultati(conn):
                conn.execute("BEGIN IMMEDIATE")
                if not self._ha_risultati(conn):
                    conn.execute("ALTER TABLE notte_passi ADD COLUMN risultato_json TEXT NOT NULL DEFAULT '{}'")
            conn.commit()

    @staticmethod
    def _ha_risultati(conn: sqlite3.Connection) -> bool:
        return any(colonna[1] == "risultato_json" for colonna in conn.execute("PRAGMA table_info(notte_passi)"))

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def avanzamento(self, sera: str) -> dict[str, Any] | None:
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT * FROM notte_avanzamento WHERE sera=?", (sera,)).fetchone()
        return dict(row) if row else None

    def ultima_notte_prima(self, sera: str) -> dict[str, Any] | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT * FROM notte_avanzamento WHERE sera<? ORDER BY sera DESC LIMIT 1", (sera,)
            ).fetchone()
        return dict(row) if row else None

    def apri_notte(self, sera: str, partenza: int, ripresa_da: str, adesso: str) -> dict[str, Any]:
        with closing(self._conn()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notte_avanzamento (sera, partenza, ripresa_da, aggiornata) VALUES (?,?,?,?)",
                (sera, partenza, ripresa_da, adesso),
            )
            conn.commit()
        return self.avanzamento(sera) or {}

    def aggiorna(self, sera: str, adesso: str, **campi: Any) -> None:
        if not campi:
            return
        assegna = ", ".join(f"{k}=?" for k in campi)
        with closing(self._conn()) as conn:
            conn.execute(
                f"UPDATE notte_avanzamento SET {assegna}, aggiornata=? WHERE sera=?",
                (*campi.values(), adesso, sera),
            )
            conn.commit()

    def scrivi_passo(self, sera: str, indice: int, fase: int, lavoro: str, esito: str, *, messaggio: str = "",
                     avvio: str = "", fine: str = "", secondi: float = 0.0, memoria_libera_mb: int = 0,
                     avanza: bool = False, conclusa: bool = False, risultato: dict[str, Any] | None = None) -> None:
        with closing(self._conn()) as conn:
            if avanza:
                cursor = conn.execute(
                    "UPDATE notte_avanzamento SET indice=?,passo_avviato_alle='',conclusa=?,aggiornata=? "
                    "WHERE sera=? AND indice=?",
                    (indice + 1, int(conclusa), fine, sera, indice),
                )
                if cursor.rowcount != 1:
                    return
            conn.execute(
                "INSERT OR REPLACE INTO notte_passi "
                "(sera,indice,fase,lavoro,esito,messaggio,avvio,fine,secondi,memoria_libera_mb,risultato_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sera, indice, fase, lavoro, esito, messaggio[:500], avvio, fine, round(secondi, 1), memoria_libera_mb,
                 json.dumps(risultato or {}, ensure_ascii=False)),
            )
            conn.commit()

    def scrivi_esito_ai(self, quando: str, esito: dict[str, Any]) -> None:
        """Passaggio dell'AI locale al modello di riserva (vedi pct/ai_riserva.py)."""
        motivo = " | ".join(str(esito.get(k) or "") for k in ("motivo", "motivo_riserva") if esito.get(k))
        with closing(self._conn()) as conn:
            conn.execute("INSERT INTO ai_esiti VALUES (?,?,?,?,?)",
                         (quando, str(esito.get("principale") or ""), str(esito.get("riserva") or ""),
                          str(esito.get("esito") or ""), motivo[:500]))
            conn.commit()

    def esiti_ai(self, limite: int = 20) -> list[dict[str, Any]]:
        with closing(self._conn()) as conn:
            rows = conn.execute("SELECT * FROM ai_esiti ORDER BY quando DESC LIMIT ?", (limite,)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _passo(row: sqlite3.Row) -> dict[str, Any]:
        dato = dict(row)
        dato["risultato"] = json.loads(dato.pop("risultato_json") or "{}")
        return dato

    def passo(self, sera: str, indice: int) -> dict[str, Any]:
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT * FROM notte_passi WHERE sera=? AND indice=?", (sera, indice)).fetchone()
        return self._passo(row) if row else {}

    def passi(self, sera: str) -> list[dict[str, Any]]:
        with closing(self._conn()) as conn:
            rows = conn.execute("SELECT * FROM notte_passi WHERE sera=? ORDER BY indice", (sera,)).fetchall()
        return [self._passo(row) for row in rows]

    def durate_medie(self, notti: int = 7) -> dict[str, float]:
        with closing(self._conn()) as conn:
            rows = conn.execute(
                "SELECT lavoro, AVG(secondi) AS media FROM notte_passi WHERE esito='completato' AND sera IN "
                "(SELECT sera FROM notte_avanzamento ORDER BY sera DESC LIMIT ?) GROUP BY lavoro", (notti,)
            ).fetchall()
        return {r["lavoro"]: round(float(r["media"] or 0), 1) for r in rows}

