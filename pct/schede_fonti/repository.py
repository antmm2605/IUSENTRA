"""Stato delle norme delle schede e proposte di revisione (SQLite dedicato, nella cartella dati della biblioteca).

- ``norme``: per (scheda, atto, articolo) l'ultima verifica (stato, impronta, URL, data) e l'impronta APPROVATA
  dall'avvocato con il testo approvato, cosi' una modifica successiva si mostra come differenza di testo;
- ``proposte``: una per evento (norma cambiata, abrogata, assente, fonte suggerita), aperta finche' l'avvocato decide.
  Una proposta gia' aperta per la stessa norma e la stessa impronta non si duplica.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from contextlib import closing
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS norme (
  scheda TEXT NOT NULL, atto TEXT NOT NULL, articolo TEXT NOT NULL,
  stato TEXT NOT NULL, sha256 TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
  aggiornato_al TEXT NOT NULL DEFAULT '', verificato_il TEXT NOT NULL,
  sha256_approvato TEXT NOT NULL DEFAULT '', testo_approvato TEXT NOT NULL DEFAULT '',
  approvato_da TEXT NOT NULL DEFAULT '', approvato_il TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (scheda, atto, articolo));
CREATE TABLE IF NOT EXISTS proposte (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scheda TEXT NOT NULL, atto TEXT NOT NULL, articolo TEXT NOT NULL, tipo TEXT NOT NULL,
  motivo TEXT NOT NULL, differenze TEXT NOT NULL DEFAULT '', sha256 TEXT NOT NULL DEFAULT '',
  stato TEXT NOT NULL DEFAULT 'aperta', creata_il TEXT NOT NULL,
  decisa_da TEXT NOT NULL DEFAULT '', decisa_il TEXT NOT NULL DEFAULT '', nota TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_proposte_aperte ON proposte(stato, scheda);
"""
DECISIONI = ("approvata", "respinta")


def _ora() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class RepositorySchedeFonti:
    def __init__(self, percorso: Path):
        self.percorso = Path(percorso)
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as c, c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.percorso, timeout=15)
        c.row_factory = sqlite3.Row
        return c

    def norma(self, scheda: str, atto: str, articolo: str) -> dict | None:
        with closing(self._conn()) as c:
            r = c.execute("SELECT * FROM norme WHERE scheda=? AND atto=? AND articolo=?", (scheda, atto, articolo)).fetchone()
        return dict(r) if r else None

    def norme_scheda(self, scheda: str) -> list[dict]:
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute("SELECT * FROM norme WHERE scheda=? ORDER BY atto, articolo", (scheda,))]

    def registra_verifica(self, scheda: str, atto: str, articolo: str, *, stato: str, sha256: str, url: str,
                          aggiornato_al: str) -> None:
        with closing(self._conn()) as c, c:
            c.execute(
                "INSERT INTO norme (scheda, atto, articolo, stato, sha256, url, aggiornato_al, verificato_il) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(scheda, atto, articolo) DO UPDATE SET stato=excluded.stato, "
                "sha256=excluded.sha256, url=excluded.url, aggiornato_al=excluded.aggiornato_al, "
                "verificato_il=excluded.verificato_il", (scheda, atto, articolo, stato, sha256, url, aggiornato_al, _ora()))

    def approva_norma(self, scheda: str, atto: str, articolo: str, *, avvocato: str, testo: str, sha256: str) -> None:
        if not str(avvocato).strip():
            raise ValueError("serve il nome dell'avvocato che approva")
        with closing(self._conn()) as c, c:
            n = c.execute("UPDATE norme SET sha256_approvato=?, testo_approvato=?, approvato_da=?, approvato_il=? "
                          "WHERE scheda=? AND atto=? AND articolo=? AND sha256=?",
                          (sha256, testo, avvocato.strip(), _ora(), scheda, atto, articolo, sha256)).rowcount
        if not n:
            raise ValueError("la norma non e' stata verificata con questa impronta: rieseguire la verifica")

    def proposta_aperta(self, scheda: str, atto: str, articolo: str, tipo: str, sha256: str) -> bool:
        with closing(self._conn()) as c:
            return c.execute("SELECT 1 FROM proposte WHERE scheda=? AND atto=? AND articolo=? AND tipo=? AND sha256=? "
                             "AND stato='aperta'", (scheda, atto, articolo, tipo, sha256)).fetchone() is not None

    def apri_proposta(self, scheda: str, atto: str, articolo: str, *, tipo: str, motivo: str, differenze: str = "",
                      sha256: str = "") -> int | None:
        if self.proposta_aperta(scheda, atto, articolo, tipo, sha256):
            return None
        with closing(self._conn()) as c, c:
            return int(c.execute("INSERT INTO proposte (scheda, atto, articolo, tipo, motivo, differenze, sha256, creata_il) "
                                 "VALUES (?,?,?,?,?,?,?,?)", (scheda, atto, articolo, tipo, motivo, differenze, sha256,
                                                              _ora())).lastrowid)

    def proposte(self, stato: str = "aperta", scheda: str = "") -> list[dict]:
        q, a = "SELECT * FROM proposte WHERE stato=?", [stato]
        if scheda:
            q, a = q + " AND scheda=?", [*a, scheda]
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute(q + " ORDER BY id", a)]

    def decidi_proposta(self, proposta_id: int, decisione: str, *, avvocato: str, nota: str = "") -> None:
        if decisione not in DECISIONI or not str(avvocato).strip():
            raise ValueError("decisione 'approvata' o 'respinta' con il nome dell'avvocato")
        with closing(self._conn()) as c, c:
            if not c.execute("UPDATE proposte SET stato=?, decisa_da=?, decisa_il=?, nota=? WHERE id=? AND stato='aperta'",
                             (decisione, avvocato.strip(), _ora(), nota, proposta_id)).rowcount:
                raise ValueError("proposta inesistente o gia' decisa")
