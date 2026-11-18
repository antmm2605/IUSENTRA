"""Archivio della Gazzetta Ufficiale (SQLite accanto agli archivi delle fonti ufficiali, comune a tutti gli studi).

Tre tabelle: `atti` (una riga per atto del sommario ufficiale), `fascicoli` (i fascicoli già letti, per non
rileggerli) e `serie_stato` (esito dell'ultima lettura di ogni serie, mostrato all'avvocato). Le ricerche e i
filtri si fanno qui in SQL con paginazione: la pagina non carica mai l'intero archivio.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from typing import Any, Iterable

CONSERVAZIONE_GIORNI = 730

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS atti (
        id TEXT PRIMARY KEY,
        serie TEXT NOT NULL,
        numero_gu TEXT NOT NULL,
        data_gu TEXT NOT NULL,
        rubrica TEXT NOT NULL DEFAULT '',
        emittente TEXT NOT NULL DEFAULT '',
        intestazione TEXT NOT NULL DEFAULT '',
        tipo TEXT NOT NULL,
        numero_atto TEXT NOT NULL DEFAULT '',
        data_atto TEXT NOT NULL DEFAULT '',
        descrizione TEXT NOT NULL DEFAULT '',
        codice_redazionale TEXT NOT NULL DEFAULT '',
        pagina TEXT NOT NULL DEFAULT '',
        posizione INTEGER NOT NULL DEFAULT 0,
        url TEXT NOT NULL,
        url_sommario TEXT NOT NULL,
        testo_ricerca TEXT NOT NULL DEFAULT '',
        acquisito_il TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS atti_data ON atti (data_gu DESC, serie, posizione)",
    "CREATE INDEX IF NOT EXISTS atti_serie ON atti (serie, data_gu DESC)",
    "CREATE INDEX IF NOT EXISTS atti_tipo ON atti (tipo, data_gu DESC)",
    """
    CREATE TABLE IF NOT EXISTS fascicoli (
        serie TEXT NOT NULL,
        numero TEXT NOT NULL,
        data TEXT NOT NULL,
        url_sommario TEXT NOT NULL,
        atti INTEGER NOT NULL DEFAULT 0,
        letto_il TEXT NOT NULL,
        PRIMARY KEY (serie, data, numero)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS serie_stato (
        serie TEXT PRIMARY KEY,
        ultimo_tentativo TEXT NOT NULL,
        ultimo_esito_ok INTEGER NOT NULL,
        ultimo_successo TEXT NOT NULL DEFAULT '',
        messaggio TEXT NOT NULL DEFAULT ''
    )
    """,
)
_CAMPI = (
    "id", "serie", "numero_gu", "data_gu", "rubrica", "emittente", "intestazione", "tipo", "numero_atto",
    "data_atto", "descrizione", "codice_redazionale", "pagina", "posizione", "url", "url_sommario",
    "testo_ricerca", "acquisito_il",
)
# A parità di data, le serie nell'ordine ufficiale (Generale, poi 1ª … 5ª Serie speciale) e gli atti nell'ordine del sommario.
_ORDINE_SERIE = "CASE serie WHEN 'SG' THEN 0 WHEN 'S1' THEN 1 WHEN 'S2' THEN 2 WHEN 'S3' THEN 3 WHEN 'S4' THEN 4 ELSE 5 END"
ORDINAMENTI = {
    "recenti": f"data_gu DESC, {_ORDINE_SERIE}, posizione",
    "meno_recenti": f"data_gu ASC, {_ORDINE_SERIE}, posizione",
}


def testo_ricerca(atto: dict[str, Any]) -> str:
    campi = ("intestazione", "descrizione", "emittente", "rubrica", "codice_redazionale", "numero_atto")
    return " ".join(str(atto.get(c) or "") for c in campi).casefold()


@dataclass
class Filtri:
    q: str = ""
    serie: tuple[str, ...] = ()
    tipo: tuple[str, ...] = ()
    rubrica: str = ""
    emittente: str = ""
    dal: str = ""
    al: str = ""
    numero_gu: str = ""
    ordine: str = "recenti"
    pagina: int = 1
    per_pagina: int = 25
    escludi: tuple[str, ...] = field(default_factory=tuple)  # dimensioni da non filtrare (per i conteggi)


def _condizioni(filtri: Filtri, *, senza: str = "") -> tuple[str, list[Any]]:
    parti: list[str] = []
    valori: list[Any] = []
    for parola in [p for p in filtri.q.casefold().split() if p][:8]:
        parti.append("instr(testo_ricerca, ?) > 0")
        valori.append(parola)
    if filtri.serie and senza != "serie":
        parti.append("serie IN (" + ",".join("?" for _ in filtri.serie) + ")")
        valori.extend(filtri.serie)
    if filtri.tipo and senza != "tipo":
        parti.append("tipo IN (" + ",".join("?" for _ in filtri.tipo) + ")")
        valori.extend(filtri.tipo)
    if filtri.rubrica and senza != "rubrica":
        parti.append("rubrica = ?")
        valori.append(filtri.rubrica)
    if filtri.emittente:
        parti.append("emittente = ?")
        valori.append(filtri.emittente)
    if filtri.dal:
        parti.append("data_gu >= ?")
        valori.append(filtri.dal)
    if filtri.al:
        parti.append("data_gu <= ?")
        valori.append(filtri.al)
    if filtri.numero_gu:
        parti.append("numero_gu = ?")
        valori.append(filtri.numero_gu)
    return (" WHERE " + " AND ".join(parti)) if parti else "", valori


class ArchivioGazzetta:
    def __init__(self, percorso: str | Path, *, sola_lettura: bool = False):
        self.percorso = Path(percorso)
        self.sola_lettura = sola_lettura
        if not sola_lettura:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connetti()) as conn:
                for istruzione in _SCHEMA:
                    conn.execute(istruzione)
                conn.commit()

    @classmethod
    def in_lettura(cls, percorso: str | Path) -> "ArchivioGazzetta | None":
        return cls(percorso, sola_lettura=True) if Path(percorso).is_file() else None

    def _connetti(self) -> sqlite3.Connection:
        if self.sola_lettura:
            conn = sqlite3.connect(f"file:{self.percorso}?mode=ro", uri=True, timeout=10)
        else:
            conn = sqlite3.connect(str(self.percorso), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    # --- scrittura (lavoro pianificato e pulsante «Aggiorna») ---
    def salva_fascicolo(
        self, fascicolo: dict[str, Any], atti: Iterable[dict[str, Any]], *, solo_se_nuovo: bool = False,
    ) -> int:
        """Sostituisce gli atti del fascicolo con quelli del sommario appena letto; restituisce quanti atti."""
        righe = [{**atto, "testo_ricerca": testo_ricerca(atto)} for atto in atti]
        with closing(self._connetti()) as conn:
            if solo_se_nuovo:
                conn.execute("BEGIN IMMEDIATE")
                gia_letto = conn.execute(
                    "SELECT 1 FROM fascicoli WHERE serie = ? AND data = ? AND numero = ?",
                    (fascicolo["serie"], fascicolo["data"], fascicolo["numero"]),
                ).fetchone()
                if gia_letto:
                    return 0
            conn.execute(
                "DELETE FROM atti WHERE serie = ? AND data_gu = ? AND numero_gu = ?",
                (fascicolo["serie"], fascicolo["data"], fascicolo["numero"]),
            )
            conn.executemany(
                "INSERT OR REPLACE INTO atti (" + ", ".join(_CAMPI) + ") VALUES (" + ", ".join("?" for _ in _CAMPI) + ")",
                [tuple(riga.get(campo, "") for campo in _CAMPI) for riga in righe],
            )
            conn.execute(
                "INSERT OR REPLACE INTO fascicoli (serie, numero, data, url_sommario, atti, letto_il) VALUES (?, ?, ?, ?, ?, ?)",
                (fascicolo["serie"], fascicolo["numero"], fascicolo["data"], fascicolo["url_sommario"], len(righe), fascicolo["letto_il"]),
            )
            conn.commit()
        return len(righe)

    def registra_esito(
        self, serie: str, *, ok: bool, quando: str, messaggio: str = "", completo: bool = True,
    ) -> None:
        with closing(self._connetti()) as conn:
            successo = quando if ok and completo else ""
            conn.execute(
                """
                INSERT INTO serie_stato (serie, ultimo_tentativo, ultimo_esito_ok, ultimo_successo, messaggio)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(serie) DO UPDATE SET
                    ultimo_tentativo = MAX(serie_stato.ultimo_tentativo, excluded.ultimo_tentativo),
                    ultimo_esito_ok = CASE WHEN excluded.ultimo_tentativo >= serie_stato.ultimo_tentativo
                        THEN excluded.ultimo_esito_ok ELSE serie_stato.ultimo_esito_ok END,
                    ultimo_successo = MAX(serie_stato.ultimo_successo, excluded.ultimo_successo),
                    messaggio = CASE WHEN excluded.ultimo_tentativo >= serie_stato.ultimo_tentativo
                        THEN excluded.messaggio ELSE serie_stato.messaggio END
                """,
                (serie, quando, 1 if ok else 0, successo, messaggio),
            )
            conn.commit()

    def pota(self, *, oggi: date, giorni: int = CONSERVAZIONE_GIORNI) -> int:
        limite = (oggi - timedelta(days=giorni)).isoformat()
        with closing(self._connetti()) as conn:
            cancellati = conn.execute("DELETE FROM atti WHERE data_gu < ?", (limite,)).rowcount
            conn.execute("DELETE FROM fascicoli WHERE data < ?", (limite,))
            conn.commit()
        return int(cancellati or 0)

    # --- lettura ---
    def fascicoli_letti(self, serie: str) -> set[str]:
        with closing(self._connetti()) as conn:
            righe = conn.execute("SELECT data, numero FROM fascicoli WHERE serie = ?", (serie,)).fetchall()
        return {f"{serie}|{riga['data']}|{riga['numero']}" for riga in righe}

    def stato_serie(self) -> dict[str, dict[str, Any]]:
        with closing(self._connetti()) as conn:
            stati = {riga["serie"]: dict(riga) for riga in conn.execute("SELECT * FROM serie_stato")}
            ultimi = {
                riga["serie"]: dict(riga)
                for riga in conn.execute(
                    "SELECT f.* FROM fascicoli f JOIN (SELECT serie, MAX(data) AS data FROM fascicoli GROUP BY serie) u "
                    "ON u.serie = f.serie AND u.data = f.data"
                )
            }
            conteggi = dict(conn.execute("SELECT serie, COUNT(*) FROM atti GROUP BY serie").fetchall())
        return {
            codice: {**stati.get(codice, {}), "ultimo_fascicolo": ultimi.get(codice), "atti": int(conteggi.get(codice, 0))}
            for codice in set(stati) | set(ultimi)
        }

    def cerca(self, filtri: Filtri) -> dict[str, Any]:
        dove, valori = _condizioni(filtri)
        ordine = ORDINAMENTI.get(filtri.ordine, ORDINAMENTI["recenti"])
        inizio = (max(1, filtri.pagina) - 1) * filtri.per_pagina
        with closing(self._connetti()) as conn:
            totale = conn.execute("SELECT COUNT(*) FROM atti" + dove, valori).fetchone()[0]
            righe = conn.execute(
                f"SELECT * FROM atti{dove} ORDER BY {ordine} LIMIT ? OFFSET ?", (*valori, filtri.per_pagina, inizio)
            ).fetchall()
            conteggi = {}
            for dimensione in ("serie", "tipo", "rubrica"):
                dove_d, valori_d = _condizioni(filtri, senza=dimensione)
                conteggi[dimensione] = conn.execute(
                    f"SELECT {dimensione}, COUNT(*) FROM atti{dove_d} GROUP BY {dimensione}", valori_d
                ).fetchall()
            date_estreme = conn.execute("SELECT MIN(data_gu), MAX(data_gu), COUNT(*) FROM atti").fetchone()
        return {
            "totale": int(totale),
            "atti": [dict(riga) for riga in righe],
            "conteggi": {chiave: {str(r[0]): int(r[1]) for r in righe_d} for chiave, righe_d in conteggi.items()},
            "dal": date_estreme[0] or "",
            "al": date_estreme[1] or "",
            "in_archivio": int(date_estreme[2] or 0),
        }

    def enti(self, filtri: Filtri, *, limite: int = 40) -> list[tuple[str, int]]:
        """Enti emananti più frequenti con gli altri filtri applicati (suggerimenti del campo «Ente»)."""
        dove, valori = _condizioni(Filtri(**{**filtri.__dict__, "emittente": ""}))
        dove = dove + (" AND " if dove else " WHERE ") + "emittente <> ''"
        with closing(self._connetti()) as conn:
            righe = conn.execute(
                f"SELECT emittente, COUNT(*) AS n FROM atti{dove} GROUP BY emittente ORDER BY n DESC, emittente LIMIT ?",
                (*valori, limite),
            ).fetchall()
        return [(str(r[0]), int(r[1])) for r in righe]


__all__ = ["ArchivioGazzetta", "CONSERVAZIONE_GIORNI", "Filtri", "ORDINAMENTI", "testo_ricerca"]
