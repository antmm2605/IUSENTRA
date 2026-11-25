"""Archivio della Gazzetta Ufficiale (SQLite accanto agli archivi delle fonti ufficiali, comune a tutti gli studi).

Tabelle: `atti` (una riga per atto del sommario ufficiale), `fascicoli` (i fascicoli già letti, per non
rileggerli), `serie_stato` (esito dell'ultima lettura di ogni serie, mostrato all'avvocato), `testi` (il testo
completo dell'atto letto dalla pagina ufficiale, compresso), `testi_errori` (atti il cui testo non si è potuto
leggere, con i tentativi), `storico` (gli elenchi annuali dell'archivio ufficiale già letti) e l'indice full-text
`atti_fts` (FTS5: titolo, ente, testo; accenti e apostrofi ignorati) per la ricerca per parole con ordinamento per
pertinenza e frasi fra virgolette. Le ricerche e i filtri si fanno qui in SQL con paginazione: la pagina non
carica mai l'intero archivio.

L'archivio conserva tutto dal 01/01/2022 (``DATA_INIZIO_ARCHIVIO``, così c'è anche la riforma del processo civile
del d.lgs. 149/2022, GU 17/10/2022): prima teneva solo due anni.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable
import zlib

CONSERVAZIONE_GIORNI = 730
DATA_INIZIO_ARCHIVIO = "2022-01-01"
# Pesi dell'ordinamento per pertinenza (bm25): il titolo conta più dell'ente, l'ente più del testo.
PESI_PERTINENZA = (0.0, 10.0, 3.0, 1.0)

# La data nell’intestazione è utilizzabile per l’ordine se compatibile con la pubblicazione.
_DATA_ATTO_O_PUBBLICAZIONE = "CASE WHEN data_atto <> '' AND data_atto <= data_gu THEN data_atto ELSE data_gu END"

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
    f"CREATE INDEX IF NOT EXISTS atti_data_cronologica ON atti ({_DATA_ATTO_O_PUBBLICAZIONE}, data_gu)",
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
    CREATE TABLE IF NOT EXISTS testi (
        id TEXT PRIMARY KEY,
        testo_z BLOB NOT NULL,
        intestazione TEXT NOT NULL DEFAULT '',
        sha256 TEXT NOT NULL,
        url_testo TEXT NOT NULL,
        articoli INTEGER NOT NULL DEFAULT 0,
        caratteri INTEGER NOT NULL DEFAULT 0,
        letto_il TEXT NOT NULL,
        fonte TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS testi_errori (
        id TEXT PRIMARY KEY,
        tentativi INTEGER NOT NULL DEFAULT 0,
        messaggio TEXT NOT NULL DEFAULT '',
        quando TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS storico (
        serie TEXT NOT NULL,
        anno INTEGER NOT NULL,
        fascicoli INTEGER NOT NULL DEFAULT 0,
        completo INTEGER NOT NULL DEFAULT 0,
        letto_il TEXT NOT NULL,
        PRIMARY KEY (serie, anno)
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
    "data_atto_recenti": f"{_DATA_ATTO_O_PUBBLICAZIONE} DESC, data_gu DESC, {_ORDINE_SERIE}, posizione, atti.id",
    "data_atto_meno_recenti": f"{_DATA_ATTO_O_PUBBLICAZIONE} ASC, data_gu ASC, {_ORDINE_SERIE}, posizione, atti.id",
    "pertinenza": f"data_gu DESC, {_ORDINE_SERIE}, posizione",  # con una ricerca per parole: vedi ``cerca``
    "recenti": f"data_gu DESC, {_ORDINE_SERIE}, posizione",
    "meno_recenti": f"data_gu ASC, {_ORDINE_SERIE}, posizione",
}
_SCHEMA_FTS = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS atti_fts USING fts5(id UNINDEXED, titolo, ente, testo, "
    "tokenize = 'unicode61 remove_diacritics 2')"
)
_PAROLA_RICERCA = re.compile(r"[0-9A-Za-zÀ-ÿ]+")
# Parole troppo comuni per restringere una ricerca negli atti.
_VUOTE = frozenset({"il", "lo", "la", "i", "gli", "le", "un", "una", "di", "a", "da", "in", "con", "su", "per", "tra",
                    "fra", "e", "o", "del", "della", "dei", "delle", "al", "alla", "nel", "nella", "che", "dell", "all",
                    "nell", "sull", "dall", "l", "d"})


def riga_fts(atto_id: str) -> int:
    """La riga dell'indice di un atto: dall'impronta dell'identificativo, così l'aggiornamento non scorre l'indice."""
    import hashlib

    if re.fullmatch(r"gu_[0-9a-f]{24}", atto_id or ""):
        return int(atto_id[3:18], 16)
    return int(hashlib.sha256(str(atto_id).encode("utf-8")).hexdigest()[:15], 16)


def comprimi(testo: str) -> bytes:
    return zlib.compress(testo.encode("utf-8"), 6)


def decomprimi(dato: bytes) -> str:
    return zlib.decompress(dato).decode("utf-8")


def _radice(parola: str) -> str:
    """La parola per l'indice: oltre le 4 lettere si toglie la vocale finale e si cercano tutte le desinenze
    («civile» trova «civili», «processo» trova «processi» e «processuale»)."""
    piatta = parola.casefold()
    if len(piatta) >= 5 and piatta[-1] in "aeiouàèéìòù":
        return f"{piatta[:-1]}*"
    return f'"{piatta}"'


def espressione_fts(q: str) -> tuple[str, str]:
    """(espressione di ricerca, espressione «parole vicine» per la pertinenza); stringhe vuote se nulla da cercare.

    Le frasi fra virgolette si cercano come frasi esatte; le altre parole devono esserci tutte (in qualunque campo).
    """
    frasi = [" ".join(_PAROLA_RICERCA.findall(f)) for f in re.findall(r'"([^"]+)"', q or "")]
    frasi = [f.casefold() for f in frasi if f]
    resto = re.sub(r'"[^"]*"', " ", q or "")
    parole = [p for p in _PAROLA_RICERCA.findall(resto) if p.casefold() not in _VUOTE][:8]
    termini = [f'"{f}"' for f in frasi] + [_radice(p) for p in parole]
    if not termini:
        return "", ""
    vicine = f"NEAR({' '.join(_radice(p) for p in parole)}, 3)" if len(parole) > 1 else ""
    return " AND ".join(termini), vicine


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


def _condizioni(filtri: Filtri, *, senza: str = "", fts: bool = False) -> tuple[str, list[Any]]:
    parti: list[str] = []
    valori: list[Any] = []
    espressione = espressione_fts(filtri.q)[0] if fts else ""
    if espressione:
        parti.append("id IN (SELECT id FROM atti_fts WHERE atti_fts MATCH ?)")
        valori.append(espressione)
    for parola in ([] if espressione or fts else [p for p in filtri.q.casefold().split() if p][:8]):
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
                conn.execute(_SCHEMA_FTS)
                if "fonte" not in {r[1] for r in conn.execute("PRAGMA table_info(testi)")}:
                    # Da dove viene il testo: la pagina della Gazzetta o la biblioteca Normattiva (2.490.3).
                    conn.execute("ALTER TABLE testi ADD COLUMN fonte TEXT NOT NULL DEFAULT ''")
                if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'atti_indicizzati'").fetchone():
                    # Indice creato senza il registro degli atti indicizzati: si ricostruisce da capo.
                    conn.execute("DELETE FROM atti_fts")
                    conn.execute("CREATE TABLE atti_indicizzati (id TEXT PRIMARY KEY)")
                conn.commit()
                self._allinea_indice(conn)

    @classmethod
    def in_lettura(cls, percorso: str | Path) -> "ArchivioGazzetta | None":
        return cls(percorso, sola_lettura=True) if Path(percorso).is_file() else None

    def _connetti(self) -> sqlite3.Connection:
        if self.sola_lettura:
            conn = sqlite3.connect(f"file:{self.percorso}?mode=ro", uri=True, timeout=10)
        else:
            conn = sqlite3.connect(str(self.percorso), timeout=120)  # due scrittori: recupero e collegamento
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
            self._indicizza(conn, [riga["id"] for riga in righe])
            conn.commit()
        return len(righe)

    # --- indice full-text ---
    def _indicizza(self, conn: sqlite3.Connection, identificativi: list[str]) -> None:
        for inizio in range(0, len(identificativi), 400):
            lotto = identificativi[inizio:inizio + 400]
            segnaposto = ",".join("?" for _ in lotto)
            conn.executemany("DELETE FROM atti_fts WHERE rowid = ?", [(riga_fts(i),) for i in lotto])
            conn.executemany("INSERT OR IGNORE INTO atti_indicizzati (id) VALUES (?)", [(i,) for i in lotto])
            righe = conn.execute(
                f"SELECT a.id, a.intestazione, a.descrizione, a.emittente, a.rubrica, a.codice_redazionale, a.numero_atto, "
                f"t.testo_z FROM atti a LEFT JOIN testi t ON t.id = a.id WHERE a.id IN ({segnaposto})", lotto,
            ).fetchall()
            conn.executemany(
                "INSERT INTO atti_fts (rowid, id, titolo, ente, testo) VALUES (?, ?, ?, ?, ?)",
                [(riga_fts(r["id"]), r["id"], " ".join(str(r[c] or "") for c in ("intestazione", "descrizione", "codice_redazionale", "numero_atto")),
                  " ".join(str(r[c] or "") for c in ("emittente", "rubrica")),
                  decomprimi(r["testo_z"]) if r["testo_z"] else "") for r in righe],
            )

    def _allinea_indice(self, conn: sqlite3.Connection) -> int:
        """Indicizza gli atti già in archivio che non sono ancora nell'indice (archivi creati prima della 2.490.3)."""
        mancanti = [str(r[0]) for r in conn.execute(
            "SELECT id FROM atti WHERE id NOT IN (SELECT id FROM atti_indicizzati)").fetchall()]
        if mancanti:
            self._indicizza(conn, mancanti)
            conn.commit()
        return len(mancanti)

    def con_indice(self, conn: sqlite3.Connection) -> bool:
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'atti_fts'").fetchone())

    # --- testi completi ---
    def salva_testo(self, atto_id: str, *, testo: str, intestazione: str, sha256: str, url_testo: str,
                    articoli: int, letto_il: str, fonte: str = "") -> None:
        with closing(self._connetti()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO testi (id, testo_z, intestazione, sha256, url_testo, articoli, caratteri, letto_il, fonte) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (atto_id, comprimi(testo), intestazione, sha256, url_testo, int(articoli), len(testo), letto_il, fonte),
            )
            conn.execute("DELETE FROM testi_errori WHERE id = ?", (atto_id,))
            self._indicizza(conn, [atto_id])
            conn.commit()

    def registra_errore_testo(self, atto_id: str, *, messaggio: str, quando: str) -> None:
        with closing(self._connetti()) as conn:
            conn.execute(
                "INSERT INTO testi_errori (id, tentativi, messaggio, quando) VALUES (?, 1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET tentativi = tentativi + 1, messaggio = excluded.messaggio, quando = excluded.quando",
                (atto_id, messaggio[:500], quando),
            )
            conn.commit()

    def atti_senza_testo(self, *, limite: int = 50, tentativi_massimi: int = 3, dal: str = DATA_INIZIO_ARCHIVIO) -> list[dict[str, Any]]:
        """Gli atti ancora senza testo: prima Serie generale e Corte costituzionale, poi le altre; dai più recenti."""
        with closing(self._connetti()) as conn:
            righe = conn.execute(
                f"""SELECT a.id, a.serie, a.data_gu, a.url FROM atti a
                    WHERE a.data_gu >= ? AND a.id NOT IN (SELECT id FROM testi)
                      AND a.id NOT IN (SELECT id FROM testi_errori WHERE tentativi >= ?)
                    ORDER BY CASE a.serie WHEN 'SG' THEN 0 WHEN 'S1' THEN 0 WHEN 'S2' THEN 1 WHEN 'S3' THEN 1 ELSE 2 END,
                             a.data_gu DESC, {_ORDINE_SERIE}, a.posizione LIMIT ?""",
                (dal, int(tentativi_massimi), int(limite)),
            ).fetchall()
        return [dict(r) for r in righe]

    def testo(self, atto_id: str) -> dict[str, Any] | None:
        with closing(self._connetti()) as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'testi'").fetchone():
                return None
            riga = conn.execute(
                "SELECT a.*, t.*, t.intestazione AS intestazione_testo, t.letto_il AS testo_letto_il, a.id AS id "
                "FROM atti a LEFT JOIN testi t ON t.id = a.id WHERE a.id = ?", (atto_id,),
            ).fetchone()
        if riga is None:
            return None
        # Colonne omonime di atti e testi (id, intestazione): sqlite3.Row restituisce la prima, cioè quella dell'atto.
        dati = {k: riga[k] for k in riga.keys() if k != "testo_z"}
        dati["testo"] = decomprimi(riga["testo_z"]) if riga["testo_z"] else ""
        return dati

    # --- recupero dello storico ---
    def anni_letti(self, serie: str) -> dict[int, dict[str, Any]]:
        with closing(self._connetti()) as conn:
            return {int(r["anno"]): dict(r) for r in conn.execute("SELECT * FROM storico WHERE serie = ?", (serie,))}

    def registra_anno(self, serie: str, anno: int, *, fascicoli: int, completo: bool, quando: str) -> None:
        with closing(self._connetti()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO storico (serie, anno, fascicoli, completo, letto_il) VALUES (?, ?, ?, ?, ?)",
                (serie, int(anno), int(fascicoli), 1 if completo else 0, quando),
            )
            conn.commit()

    def copertura(self) -> dict[str, Any]:
        """Quanti atti e testi ci sono, dal primo all'ultimo fascicolo: lo stato del recupero storico."""
        with closing(self._connetti()) as conn:
            atti = conn.execute("SELECT serie, COUNT(*), MIN(data_gu), MAX(data_gu) FROM atti GROUP BY serie").fetchall()
            con_testo = dict(conn.execute(
                "SELECT a.serie, COUNT(*) FROM atti a JOIN testi t ON t.id = a.id GROUP BY a.serie").fetchall()) \
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'testi'").fetchone() else {}
        return {str(r[0]): {"atti": int(r[1]), "dal": r[2], "al": r[3], "con_testo": int(con_testo.get(r[0], 0))} for r in atti}

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
        """Toglie solo gli atti precedenti all'inizio dell'archivio (01/01/2022): l'archivio cresce, non scorre."""
        limite = min((oggi - timedelta(days=giorni)).isoformat(), DATA_INIZIO_ARCHIVIO)
        with closing(self._connetti()) as conn:
            if self.con_indice(conn):
                vecchi = [str(r[0]) for r in conn.execute("SELECT id FROM atti WHERE data_gu < ?", (limite,)).fetchall()]
                conn.executemany("DELETE FROM atti_fts WHERE rowid = ?", [(riga_fts(i),) for i in vecchi])
                conn.executemany("DELETE FROM atti_indicizzati WHERE id = ?", [(i,) for i in vecchi])
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

    def atti_del_fascicolo(self, atto_id: str) -> list[dict[str, Any]]:
        """Legge il sommario già archiviato, nello stesso ordine della fonte."""
        with closing(self._connetti()) as conn:
            testi = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'testi'").fetchone()
            con_testo = "EXISTS(SELECT 1 FROM testi WHERE testi.id = atti.id)" if testi else "0"
            righe = conn.execute(
                f"""SELECT atti.*, {con_testo} AS con_testo FROM atti
                    WHERE (serie, data_gu, numero_gu) = (
                        SELECT serie, data_gu, numero_gu FROM atti WHERE id = ?
                    )
                    ORDER BY posizione, id""",
                (atto_id,),
            ).fetchall()
        return [dict(riga) for riga in righe]

    def cerca(self, filtri: Filtri) -> dict[str, Any]:
        inizio = (max(1, filtri.pagina) - 1) * filtri.per_pagina
        with closing(self._connetti()) as conn:
            fts = self.con_indice(conn)
            testi = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'testi'").fetchone())
            dove, valori = _condizioni(filtri, fts=fts)
            espressione, vicine = espressione_fts(filtri.q) if fts else ("", "")
            con_testo = "(SELECT 1 FROM testi t WHERE t.id = atti.id) AS con_testo" if testi else "0 AS con_testo"
            totale = conn.execute("SELECT COUNT(*) FROM atti" + dove, valori).fetchone()[0]
            if espressione and filtri.ordine in ("pertinenza", ""):
                # Pertinenza: prima le parole vicine nel titolo, poi vicine in qualunque campo, poi il punteggio
                # bm25 (titolo 10, ente 3, testo 1), poi la data.
                pesi = ", ".join(str(p) for p in PESI_PERTINENZA)
                titolo_vicine = f"titolo : {vicine}" if vicine else f"titolo : ({espressione})"
                righe = conn.execute(
                    f"""WITH trovati AS (SELECT id AS fid, bm25(atti_fts, {pesi}) AS punteggio FROM atti_fts WHERE atti_fts MATCH ?),
                             nel_titolo AS (SELECT id FROM atti_fts WHERE atti_fts MATCH ?),
                             vicine AS (SELECT id FROM atti_fts WHERE atti_fts MATCH ?)
                        SELECT atti.*, {con_testo} FROM atti JOIN trovati ON trovati.fid = atti.id{dove}
                        ORDER BY (atti.id IN nel_titolo) DESC, (atti.id IN vicine) DESC, trovati.punteggio,
                                 {ORDINAMENTI['recenti']} LIMIT ? OFFSET ?""",
                    (espressione, titolo_vicine, vicine or espressione, *valori, filtri.per_pagina, inizio),
                ).fetchall()
            else:
                ordine = ORDINAMENTI.get(filtri.ordine, ORDINAMENTI["recenti"])
                righe = conn.execute(
                    f"SELECT atti.*, {con_testo} FROM atti{dove} ORDER BY {ordine} LIMIT ? OFFSET ?",
                    (*valori, filtri.per_pagina, inizio),
                ).fetchall()
            conteggi = {}
            for dimensione in ("serie", "tipo", "rubrica"):
                dove_d, valori_d = _condizioni(filtri, senza=dimensione, fts=fts)
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
        with closing(self._connetti()) as conn:
            dove, valori = _condizioni(Filtri(**{**filtri.__dict__, "emittente": ""}), fts=self.con_indice(conn))
            dove = dove + (" AND " if dove else " WHERE ") + "emittente <> ''"
            righe = conn.execute(
                f"SELECT emittente, COUNT(*) AS n FROM atti{dove} GROUP BY emittente ORDER BY n DESC, emittente LIMIT ?",
                (*valori, limite),
            ).fetchall()
        return [(str(r[0]), int(r[1])) for r in righe]


__all__ = ["ArchivioGazzetta", "CONSERVAZIONE_GIORNI", "DATA_INIZIO_ARCHIVIO", "Filtri", "ORDINAMENTI", "comprimi", "decomprimi",
           "espressione_fts", "testo_ricerca"]
