"""Archivio della prassi (SQLite con indice FTS5): un documento per circolare, risoluzione o messaggio.

Ogni documento ha ente, tipo, numero, data, oggetto, indirizzo ufficiale della pagina e del testo (PDF o scheda),
e il testo integrale letto dalla fonte. Lo stato (da leggere, letto, non disponibile) e i tentativi permettono di
riprendere la lettura da dove si era fermata.
"""
from __future__ import annotations

import hashlib
import sqlite3
import zlib
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TENTATIVI = 3
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS documenti (
        id TEXT PRIMARY KEY, ente TEXT NOT NULL, tipo TEXT NOT NULL, numero TEXT NOT NULL, data TEXT NOT NULL,
        oggetto TEXT NOT NULL DEFAULT '', url TEXT NOT NULL, url_testo TEXT NOT NULL DEFAULT '',
        stato TEXT NOT NULL DEFAULT 'da_leggere', tentativi INTEGER NOT NULL DEFAULT 0, messaggio TEXT NOT NULL DEFAULT '',
        testo_z BLOB, sha256 TEXT NOT NULL DEFAULT '', letto_il TEXT NOT NULL DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS documenti_coda ON documenti (stato, data DESC)",
    "CREATE INDEX IF NOT EXISTS documenti_estremi ON documenti (ente, tipo, data DESC)",
    "CREATE VIRTUAL TABLE IF NOT EXISTS documenti_fts USING fts5(id UNINDEXED, oggetto, testo, "
    "tokenize = 'unicode61 remove_diacritics 2')",
    "CREATE TABLE IF NOT EXISTS elenchi (chiave TEXT PRIMARY KEY, letto_il TEXT NOT NULL, documenti INTEGER NOT NULL)",
)


def identificativo(ente: str, tipo: str, numero: str, data: str) -> str:
    return f"{ente}|{tipo}|{data[:4]}|{numero}".lower()


class ArchivioPrassi:
    def __init__(self, percorso: str | Path, *, sola_lettura: bool = False):
        self.percorso = Path(percorso)
        self.sola_lettura = sola_lettura
        if not sola_lettura:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connetti()) as conn:
                for istruzione in _SCHEMA:
                    conn.execute(istruzione)
                conn.commit()

    def _connetti(self) -> sqlite3.Connection:
        if self.sola_lettura:
            conn = sqlite3.connect(f"file:{self.percorso}?mode=ro", uri=True, timeout=30)
        else:
            conn = sqlite3.connect(str(self.percorso), timeout=120)
            conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def aggiungi(self, documenti: Iterable[dict[str, Any]]) -> int:
        nuovi = 0
        with closing(self._connetti()) as conn:
            for d in documenti:
                ident = identificativo(d["ente"], d["tipo"], d["numero"], d["data"])
                nuovi += conn.execute(
                    "INSERT OR IGNORE INTO documenti (id, ente, tipo, numero, data, oggetto, url, url_testo) VALUES (?,?,?,?,?,?,?,?)",
                    (ident, d["ente"], d["tipo"], d["numero"], d["data"], d.get("oggetto") or "", d["url"],
                     d.get("url_testo") or "")).rowcount
            conn.commit()
        return nuovi

    def registra_elenco(self, chiave: str, documenti: int) -> None:
        with closing(self._connetti()) as conn:
            conn.execute("INSERT OR REPLACE INTO elenchi VALUES (?,?,?)",
                         (chiave, datetime.now(timezone.utc).replace(microsecond=0).isoformat(), documenti))
            conn.commit()

    def elenco_letto(self, chiave: str) -> bool:
        with closing(self._connetti()) as conn:
            return conn.execute("SELECT 1 FROM elenchi WHERE chiave=?", (chiave,)).fetchone() is not None

    def da_leggere(self, ente: str = "", limite: int = 20) -> list[dict[str, Any]]:
        with closing(self._connetti()) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM documenti WHERE stato='da_leggere' AND tentativi < ? AND (?='' OR ente=?) "
                "ORDER BY data DESC LIMIT ?", (TENTATIVI, ente, ente, limite))]

    def salva_testo(self, ident: str, testo: str) -> None:
        with closing(self._connetti()) as conn:
            riga = conn.execute("SELECT oggetto FROM documenti WHERE id=?", (ident,)).fetchone()
            conn.execute("UPDATE documenti SET stato='letto', testo_z=?, sha256=?, letto_il=?, messaggio='' WHERE id=?",
                         (zlib.compress(testo.encode("utf-8"), 6), hashlib.sha256(testo.encode()).hexdigest(),
                          datetime.now(timezone.utc).replace(microsecond=0).isoformat(), ident))
            conn.execute("DELETE FROM documenti_fts WHERE id=?", (ident,))
            conn.execute("INSERT INTO documenti_fts (id, oggetto, testo) VALUES (?,?,?)", (ident, riga[0] if riga else "", testo))
            conn.commit()

    def errore(self, ident: str, messaggio: str, *, definitivo: bool = False) -> None:
        with closing(self._connetti()) as conn:
            conn.execute("UPDATE documenti SET tentativi=tentativi+1, messaggio=?, stato=? WHERE id=?",
                         (messaggio[:300], "non_disponibile" if definitivo else "da_leggere", ident))
            conn.commit()

    def conteggi(self) -> dict[str, Any]:
        with closing(self._connetti()) as conn:
            return {f"{r[0]} {r[1]}": {"documenti": int(r[2]), "con_testo": int(r[3]), "dal": r[4], "al": r[5]}
                    for r in conn.execute("SELECT ente, tipo, COUNT(*), SUM(stato='letto'), MIN(data), MAX(data) "
                                          "FROM documenti GROUP BY ente, tipo")}

    def cerca(self, domanda: str, *, ente: str = "", limite: int = 20) -> list[dict[str, Any]]:
        """Documenti che contengono le parole (frasi fra virgolette), i più pertinenti per primi, con un brano."""
        from pct.gazzetta.archivio import espressione_fts

        espressione = espressione_fts(domanda)[0]
        if not espressione:
            return []
        with closing(self._connetti()) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT d.id, d.ente, d.tipo, d.numero, d.data, d.oggetto, d.url, d.url_testo, "
                "snippet(documenti_fts, 2, '«', '»', ' … ', 24) AS brano FROM documenti_fts f JOIN documenti d ON d.id=f.id "
                "WHERE documenti_fts MATCH ? AND (?='' OR d.ente=?) ORDER BY bm25(documenti_fts, 0, 4, 1), d.data DESC LIMIT ?",
                (espressione, ente, ente, limite))]

    def testo(self, ident: str) -> str:
        with closing(self._connetti()) as conn:
            riga = conn.execute("SELECT testo_z FROM documenti WHERE id=?", (ident,)).fetchone()
        return zlib.decompress(riga[0]).decode("utf-8") if riga and riga[0] else ""


__all__ = ["ArchivioPrassi", "identificativo"]
