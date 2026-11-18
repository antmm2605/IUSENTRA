"""Il database dedicato dei pannelli pronti di uno studio (``intelligence/pannelli_pronti.db``).

Vive fuori da ``studio.db`` perché salvare un payload non deve contendere il lock delle scritture dello studio.
Contiene:

- ``pannelli``: per ogni chiave (fascicolo, pannello, parametri normalizzati, profilo dei permessi) l'ultimo
  payload calcolato dal motore del pannello e l'impronta delle fonti con cui è stato calcolato;
- ``profili``: i dati di sessione minimi per rifare la stessa richiesta in sfondo con gli stessi permessi;
- ``aperture``: quando ogni fascicolo è stato aperto l'ultima volta;
- ``generazioni``: contatore per fascicolo incrementato da ogni richiesta di scrittura sul fascicolo.

Un payload è valido solo se la sua impronta coincide con quella attuale: il controllo è sempre di chi legge.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

NOME_FILE = "pannelli_pronti.db"
MAX_CORPO = 16 * 1024 * 1024
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS pannelli ("
    " chiave TEXT PRIMARY KEY, fascicolo_id TEXT NOT NULL, pannello TEXT NOT NULL, percorso TEXT NOT NULL,"
    " profilo TEXT NOT NULL, impronta TEXT NOT NULL DEFAULT '', stato INTEGER NOT NULL DEFAULT 0,"
    " tipo TEXT NOT NULL DEFAULT '', corpo BLOB, calcolato_il TEXT NOT NULL DEFAULT '',"
    " durata_ms INTEGER NOT NULL DEFAULT 0, richiesto_il TEXT NOT NULL, servito_il TEXT NOT NULL DEFAULT '',"
    " richieste INTEGER NOT NULL DEFAULT 0, errore TEXT NOT NULL DEFAULT '', tentata TEXT NOT NULL DEFAULT '')",
    "CREATE INDEX IF NOT EXISTS idx_pannelli_fascicolo ON pannelli(fascicolo_id, pannello)",
    "CREATE TABLE IF NOT EXISTS profili (profilo TEXT PRIMARY KEY, sessione_json TEXT NOT NULL, aggiornato_il TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS aperture (fascicolo_id TEXT PRIMARY KEY, aperto_il TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_aperture_quando ON aperture(aperto_il)",
    "CREATE TABLE IF NOT EXISTS generazioni (fascicolo_id TEXT PRIMARY KEY, generazione INTEGER NOT NULL)",
)
# Indici di copertura per i controlli dello scheduler e del calcolatore: le colonne lette stanno dopo ``corpo`` (fino a
# centinaia di KB per voce) e senza indice SQLite scorre le pagine di overflow di ogni payload a ogni controllo.
# Si creano solo fuori dalle richieste web (``prepara_indici``): la prima creazione legge l'archivio una volta.
_INDICI = (
    # ``stati`` legge anche il pannello (impronta propria del pannello): l'indice precedente non copre più la lettura.
    "DROP INDEX IF EXISTS idx_pannelli_stati",
    "CREATE INDEX IF NOT EXISTS idx_pannelli_stati_pannello ON pannelli(chiave, fascicolo_id, impronta, tentata, pannello)",
    "CREATE INDEX IF NOT EXISTS idx_pannelli_varianti_fascicoli ON pannelli(profilo, pannello, percorso, richieste,"
    " fascicolo_id)",
    "CREATE INDEX IF NOT EXISTS idx_pannelli_attesa ON pannelli(pannello, richiesto_il, richieste, calcolato_il, servito_il,"
    " fascicolo_id)",
    "CREATE INDEX IF NOT EXISTS idx_pannelli_voci ON pannelli(fascicolo_id, richiesto_il, chiave, pannello, percorso, profilo,"
    " impronta, tentata)",
)
_PREPARATI: set[str] = set()
_INDICIZZATI: set[str] = set()
_LOCK = threading.Lock()


def _adesso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def chiave(fascicolo_id: str, pannello: str, parametri: str, profilo: str) -> str:
    grezzo = "\x1f".join((str(fascicolo_id), str(pannello), str(parametri), str(profilo)))
    return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Voce:
    chiave: str
    fascicolo_id: str
    pannello: str
    percorso: str
    profilo: str
    impronta: str
    stato: int
    tipo: str
    corpo: bytes | None
    calcolato_il: str
    durata_ms: int
    richiesto_il: str
    tentata: str
    servito_il: str


class ArchivioPannelli:
    """Accesso al database dei pannelli pronti di uno studio."""

    def __init__(self, percorso: str | Path) -> None:
        self.percorso = str(percorso)

    @contextmanager
    def _conn(self, *, timeout: float = 10) -> Iterator[sqlite3.Connection]:
        if self.percorso not in _PREPARATI:
            Path(self.percorso).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.percorso, timeout=timeout, isolation_level=None)
        try:
            if self.percorso not in _PREPARATI:
                with _LOCK:
                    if self.percorso not in _PREPARATI:
                        conn.execute("PRAGMA journal_mode=WAL")
                        for istruzione in _SCHEMA:
                            conn.execute(istruzione)
                        _PREPARATI.add(self.percorso)
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _lettura(self) -> Iterator[sqlite3.Connection | None]:
        # Una consultazione di un archivio esistente non installa lo schema
        # e non compete con il worker per il lock di scrittura.
        percorso = Path(self.percorso)
        if not percorso.is_file():
            yield None
            return
        conn = sqlite3.connect(percorso.absolute().as_uri() + "?mode=ro", uri=True, timeout=2)
        try:
            yield conn
        except sqlite3.OperationalError as exc:
            if not str(exc).startswith("no such table:"):
                raise
        finally:
            conn.close()

    # ---- lettura -----------------------------------------------------------------------------------------

    def voce(self, chiave_voce: str) -> Voce | None:
        riga = None
        with self._lettura() as conn:
            if conn is None:
                return None
            riga = conn.execute(
                "SELECT chiave,fascicolo_id,pannello,percorso,profilo,impronta,stato,tipo,corpo,calcolato_il,durata_ms,richiesto_il,tentata,servito_il "
                "FROM pannelli WHERE chiave=?", (chiave_voce,)).fetchone()
        return Voce(*riga) if riga else None

    def generazione(self, fascicolo_id: str) -> int:
        riga = None
        with self._lettura() as conn:
            if conn is None:
                return 0
            riga = conn.execute("SELECT generazione FROM generazioni WHERE fascicolo_id=?", (str(fascicolo_id),)).fetchone()
        return int(riga[0]) if riga else 0

    def sessione(self, profilo: str) -> dict | None:
        with self._conn() as conn:
            riga = conn.execute("SELECT sessione_json FROM profili WHERE profilo=?", (profilo,)).fetchone()
        return json.loads(riga[0]) if riga else None

    def fascicoli_aperti_dal(self, ore: float) -> list[str]:
        soglia = (datetime.now(UTC) - timedelta(hours=float(ore))).isoformat(timespec="milliseconds")
        with self._conn() as conn:
            return [str(r[0]) for r in conn.execute(
                "SELECT fascicolo_id FROM aperture WHERE aperto_il>=? ORDER BY aperto_il DESC", (soglia,)).fetchall()]

    def fascicoli_in_attesa_di_lettura(self, *, minuti: float, pannelli: tuple[str, ...] = ("lettura",)) -> list[str]:
        """Fascicoli con una consultazione prioritaria dopo l’ultimo calcolo."""
        if not pannelli:
            return []
        soglia = (datetime.now(UTC) - timedelta(minutes=minuti)).isoformat(timespec="milliseconds")
        with self._conn() as conn:
            segnaposti = ",".join("?" for _ in pannelli)
            righe = conn.execute(
                f"SELECT fascicolo_id FROM pannelli WHERE pannello IN ({segnaposti}) AND richieste>0 "
                "AND richiesto_il>=? AND richiesto_il>calcolato_il AND richiesto_il>servito_il "
                "GROUP BY fascicolo_id ORDER BY MAX(richiesto_il) DESC",
                (*pannelli, soglia),
            ).fetchall()
        return [str(riga[0]) for riga in righe]

    def voci_del_fascicolo(self, fascicolo_id: str) -> list[tuple[str, str, str, str, str, str]]:
        """(chiave, pannello, percorso, profilo, impronta, impronta dell'ultimo tentativo non salvato)."""
        with self._conn() as conn:
            return [tuple(r) for r in conn.execute(
                "SELECT chiave,pannello,percorso,profilo,impronta,tentata FROM pannelli WHERE fascicolo_id=? "
                "ORDER BY richiesto_il DESC", (str(fascicolo_id),)).fetchall()]

    def profili_del_fascicolo(self, fascicolo_id: str) -> list[str]:
        with self._conn() as conn:
            return [str(r[0]) for r in conn.execute(
                "SELECT DISTINCT profilo FROM pannelli WHERE fascicolo_id=?", (str(fascicolo_id),)).fetchall()]

    # ---- copertura di tutti i fascicoli (una query per tutto lo studio) ------------------------------------

    def prepara_indici(self) -> None:
        """Gli indici di copertura dei controlli in sfondo (una volta per processo; mai in una richiesta web)."""
        if self.percorso in _INDICIZZATI:
            return
        try:
            with self._conn(timeout=30) as conn:
                for istruzione in _INDICI:
                    conn.execute(istruzione)
        except sqlite3.Error:
            return  # archivio occupato: i controlli funzionano anche senza, si riprova al giro successivo
        _INDICIZZATI.add(self.percorso)

    def generazioni(self) -> dict[str, int]:
        with self._lettura() as conn:
            if conn is None:
                return {}
            return {str(r[0]): int(r[1]) for r in conn.execute("SELECT fascicolo_id, generazione FROM generazioni")}

    def profili_attivi(self, *, giorni: float) -> list[str]:
        """I profili che hanno consultato almeno un pannello negli ultimi ``giorni``: i loro pannelli si preparano."""
        soglia = (datetime.now(UTC) - timedelta(days=float(giorni))).isoformat(timespec="milliseconds")
        with self._lettura() as conn:
            if conn is None:
                return []
            return [str(r[0]) for r in conn.execute(
                "SELECT profilo FROM profili WHERE aggiornato_il>=? ORDER BY aggiornato_il DESC", (soglia,))]

    def varianti_richieste(self, profilo: str) -> list[tuple[str, str]]:
        """(pannello, parametri) già chiesti dal profilo, i più richiesti per primi.

        Una variante con parametri vale per tutti i fascicoli solo se è stata chiesta per almeno due fascicoli diversi:
        parametri propri di un fascicolo (per esempio il cliente) non si applicano agli altri.
        """
        with self._lettura() as conn:
            if conn is None:
                return []
            return [(str(r[0]), str(r[1] or "")) for r in conn.execute(
                "SELECT pannello, CASE WHEN instr(percorso,'?')>0 THEN substr(percorso, instr(percorso,'?')+1) ELSE '' END q,"
                " SUM(richieste) n FROM pannelli WHERE profilo=? AND richieste>0 GROUP BY 1,2"
                " HAVING q='' OR COUNT(DISTINCT fascicolo_id)>1 ORDER BY n DESC", (profilo,))]

    def stati(self) -> dict[str, tuple[str, str, str, str]]:
        """chiave → (fascicolo, impronta salvata, impronta dell'ultimo tentativo, pannello) per tutte le voci.

        Il pannello serve a confrontare l'impronta salvata con quella propria del pannello (con o senza il giorno
        di consultazione, con la revisione del suo motore: ``pannelli_pronti_catalogo.impronta_del_pannello``)."""
        with self._lettura() as conn:
            if conn is None:
                return {}
            # Un'impronta si registra solo con il payload (``salva``): senza corpo resta vuota.
            return {str(r[0]): (str(r[1]), str(r[2] or ""), str(r[3] or ""), str(r[4] or "")) for r in conn.execute(
                "SELECT chiave, fascicolo_id, impronta, tentata, pannello FROM pannelli")}

    def conteggi(self) -> dict[str, int]:
        with self._conn() as conn:
            pronti = conn.execute("SELECT COUNT(*) FROM pannelli WHERE impronta<>''").fetchone()[0]
            totali = conn.execute("SELECT COUNT(*) FROM pannelli").fetchone()[0]
            fascicoli = conn.execute("SELECT COUNT(DISTINCT fascicolo_id) FROM pannelli").fetchone()[0]
        return {"voci": int(totali), "pronte": int(pronti), "fascicoli": int(fascicoli)}

    # ---- scrittura ---------------------------------------------------------------------------------------

    def registra_richiesta(self, *, chiave_voce: str, fascicolo_id: str, pannello: str, percorso: str,
                           profilo: str, sessione: dict, servito: bool, ritenta: bool = False, differibile: bool = True) -> None:
        adesso = _adesso()
        # Il browser riprova una richiesta in preparazione. Un altro
        # scrittore non deve trattenere la consultazione per secondi.
        with self._conn(timeout=0.075 if differibile and not servito else 0) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO pannelli(chiave,fascicolo_id,pannello,percorso,profilo,richiesto_il,richieste,servito_il) "
                "VALUES (?,?,?,?,?,?,1,?) ON CONFLICT(chiave) DO UPDATE SET richiesto_il=excluded.richiesto_il,"
                " richieste=richieste+1, servito_il=CASE WHEN ? THEN excluded.richiesto_il ELSE servito_il END,"
                " percorso=excluded.percorso, tentata=CASE WHEN ? THEN '' ELSE tentata END",
                (chiave_voce, str(fascicolo_id), pannello, percorso, profilo, adesso, adesso if servito else "",
                 int(servito), int(ritenta)))
            conn.execute("INSERT INTO profili(profilo,sessione_json,aggiornato_il) VALUES (?,?,?) "
                         "ON CONFLICT(profilo) DO UPDATE SET sessione_json=excluded.sessione_json,"
                         " aggiornato_il=excluded.aggiornato_il",
                         (profilo, json.dumps(sessione, sort_keys=True), adesso))
            conn.execute("INSERT INTO aperture(fascicolo_id,aperto_il) VALUES (?,?) "
                         "ON CONFLICT(fascicolo_id) DO UPDATE SET aperto_il=excluded.aperto_il", (str(fascicolo_id), adesso))

    def salva(self, *, chiave_voce: str, fascicolo_id: str, pannello: str, percorso: str, profilo: str,
              impronta: str, stato: int, tipo: str, corpo: bytes, durata_ms: int,
              timeout: float = 10, dipendenti: tuple[str, ...] = ()) -> bool:
        if len(corpo) > MAX_CORPO:
            return False
        adesso = _adesso()
        with self._conn(timeout=timeout) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            precedente = conn.execute(
                "SELECT corpo, impronta FROM pannelli WHERE chiave=?", (chiave_voce,),
            ).fetchone() if dipendenti else None
            conn.execute(
                "INSERT INTO pannelli(chiave,fascicolo_id,pannello,percorso,profilo,impronta,stato,tipo,corpo,"
                " calcolato_il,durata_ms,richiesto_il,errore) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'') "
                "ON CONFLICT(chiave) DO UPDATE SET impronta=excluded.impronta, stato=excluded.stato, tipo=excluded.tipo,"
                " corpo=excluded.corpo, calcolato_il=excluded.calcolato_il, durata_ms=excluded.durata_ms, errore='', tentata=''",
                (chiave_voce, str(fascicolo_id), pannello, percorso, profilo, impronta, int(stato), tipo, corpo, adesso,
                 int(durata_ms), adesso))
            if dipendenti and precedente != (corpo, impronta):
                self._invalida_voci(conn, fascicolo_id, dipendenti)
        return True

    def segna_tentativo(self, *, chiave_voce: str, fascicolo_id: str, pannello: str, percorso: str, profilo: str,
                        impronta: str, motivo: str) -> None:
        """Calcolo in sfondo senza payload salvabile (errore o lavoro in corso): non si ritenta con le stesse fonti."""
        adesso = _adesso()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO pannelli(chiave,fascicolo_id,pannello,percorso,profilo,richiesto_il,tentata,errore) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(chiave) DO UPDATE SET tentata=excluded.tentata,"
                " errore=excluded.errore, richiesto_il=excluded.richiesto_il",
                (chiave_voce, str(fascicolo_id), pannello, percorso, profilo, adesso, impronta, str(motivo)[:500]))

    def segnala_fonti_aggiornate(self, fascicolo_id: str) -> bool:
        """Rimette in lavorazione i pannelli di un fascicolo con profilo noto."""
        fid = str(fascicolo_id)
        with self._conn() as conn:
            return bool(conn.execute(
                "INSERT INTO aperture(fascicolo_id,aperto_il) "
                "SELECT ?,? WHERE EXISTS (SELECT 1 FROM pannelli WHERE fascicolo_id=?) "
                "ON CONFLICT(fascicolo_id) DO UPDATE SET aperto_il=excluded.aperto_il",
                (fid, _adesso(), fid),
            ).rowcount)

    def invalida_fascicolo(self, fascicolo_id: str) -> int:
        """Una scrittura sul fascicolo: nessun payload salvato prima vale più (la generazione entra nell'impronta)."""
        with self._conn() as conn:
            conn.execute("INSERT INTO generazioni(fascicolo_id,generazione) VALUES (?,1) "
                         "ON CONFLICT(fascicolo_id) DO UPDATE SET generazione=generazione+1", (str(fascicolo_id),))
            return int(conn.execute("SELECT generazione FROM generazioni WHERE fascicolo_id=?",
                                    (str(fascicolo_id),)).fetchone()[0])

    def invalida_pannelli(self, fascicolo_id: str, pannelli: tuple[str, ...]) -> int:
        """I pannelli che leggono il risultato di un altro pannello appena cambiato si ricalcolano."""
        if not pannelli:
            return 0
        with self._conn() as conn:
            return self._invalida_voci(conn, fascicolo_id, pannelli)

    @staticmethod
    def _invalida_voci(conn: sqlite3.Connection, fascicolo_id: str, pannelli: tuple[str, ...]) -> int:
        return int(conn.execute(
            "UPDATE pannelli SET impronta='', tentata='' WHERE fascicolo_id=? AND pannello IN ("
            + ",".join("?" for _ in pannelli) + ")", (str(fascicolo_id), *pannelli)).rowcount or 0)

    def ultimo_valido(self, fascicolo_id: str, pannello: str, impronta: str) -> bytes | None:
        """Il payload salvato del pannello, per qualunque profilo, se calcolato con l'impronta indicata."""
        riga = None
        with self._lettura() as conn:
            if conn is None:
                return None
            riga = conn.execute("SELECT corpo FROM pannelli WHERE fascicolo_id=? AND pannello=? AND impronta=? "
                                "AND corpo IS NOT NULL ORDER BY calcolato_il DESC LIMIT 1",
                                (str(fascicolo_id), pannello, impronta)).fetchone()
        return bytes(riga[0]) if riga else None

    def elimina_vecchie(self, *, giorni: int = 30) -> int:
        """Elimina le richieste abbandonate prive di un risultato consultabile."""
        soglia = (datetime.now(UTC) - timedelta(days=int(giorni))).isoformat(timespec="milliseconds")
        with self._conn() as conn:
            tolte = conn.execute(
                "DELETE FROM pannelli WHERE richiesto_il<? AND (corpo IS NULL OR stato<>200)",
                (soglia,),
            ).rowcount
            conn.execute("DELETE FROM aperture WHERE aperto_il<?", (soglia,))
        return int(tolte or 0)
