"""Indice lessicale FTS5 sui chunk Normattiva, nello stesso database dell'importer.

Tabelle (create in modo idempotente da ``assicura_schema_fts``):

- ``normative_fts``: FTS5 senza contenuto (``content=''``), ``rowid`` = id del chunk, colonne
  ``titolo`` (titolo dell'atto e rubrica dell'articolo) e ``testo`` (testo del chunk), entrambe già
  ridotte a radici italiane senza stopword (``testo.testo_indice``); tokenizer ``unicode61`` con
  rimozione degli accenti;
- ``normative_fts_info``: per ogni chunk indicizzato articolo normalizzato, codice, estremi
  dell'atto, vigenza e parte dell'articolo, per il riferimento esatto e la priorità della versione
  vigente;
- ``normative_indici_meta``: versione dell'analizzatore con cui l'indice è stato costruito.

L'aggiornamento è incrementale: ``sincronizza_fts`` indicizza solo i chunk non ancora presenti.
I chunk Normattiva non cambiano testo (la chiave contiene l'impronta dell'XML): un documento
modificato produce chunk nuovi, che entrano alla sincronizzazione successiva.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .testo import (
    CODICI_PER_CHIAVE,
    VERSIONE_ANALIZZATORE,
    AnalisiDomanda,
    articolo_normalizzato,
    codice_da_atto,
    testo_indice,
)

logger = logging.getLogger(__name__)

PESO_TITOLO = 3.0
PESO_TESTO = 1.0
BONUS_ESATTO = 2.0
BONUS_ARTICOLO_SENZA_CODICE = 0.35
BONUS_VIGENTE = 0.08
_PARTE_RE = re.compile(r":chunk(\d+)$")
_ARTICOLO_IN_TESTO_RE = re.compile(r"^\s*Art\.\s*(\d{1,4}(?:[\s.-]*(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|nonies|decies))?)", re.I)


def assicura_schema_fts(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS normative_fts USING fts5(
            titolo,
            testo,
            content='',
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE TABLE IF NOT EXISTS normative_fts_info (
            chunk_id INTEGER PRIMARY KEY,
            document_id INTEGER NOT NULL,
            articolo TEXT NOT NULL DEFAULT '',
            parte INTEGER NOT NULL DEFAULT 1,
            codice TEXT NOT NULL DEFAULT '',
            atto_numero TEXT NOT NULL DEFAULT '',
            atto_anno TEXT NOT NULL DEFAULT '',
            vigenza TEXT NOT NULL DEFAULT '',
            identita TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_normative_fts_info_codice ON normative_fts_info(codice, articolo);
        CREATE INDEX IF NOT EXISTS idx_normative_fts_info_atto ON normative_fts_info(atto_numero, atto_anno, articolo);
        CREATE INDEX IF NOT EXISTS idx_normative_fts_info_documento ON normative_fts_info(document_id);
        CREATE TABLE IF NOT EXISTS normative_indici_meta (
            chiave TEXT PRIMARY KEY,
            valore TEXT NOT NULL
        );
        """
    )


def indice_fts_presente(conn: sqlite3.Connection) -> bool:
    try:
        riga = conn.execute(
            "SELECT valore FROM normative_indici_meta WHERE chiave = 'fts_analizzatore'"
        ).fetchone()
    except sqlite3.Error:
        return False
    if not riga or riga[0] != VERSIONE_ANALIZZATORE:
        return False
    try:
        return bool(conn.execute("SELECT 1 FROM normative_fts_info LIMIT 1").fetchone())
    except sqlite3.Error:
        return False


def _leggi_meta(conn: sqlite3.Connection, chiave: str) -> str:
    try:
        riga = conn.execute("SELECT valore FROM normative_indici_meta WHERE chiave = ?", (chiave,)).fetchone()
    except sqlite3.Error:
        return ""
    return str(riga[0]) if riga else ""


def _scrivi_meta(conn: sqlite3.Connection, chiave: str, valore: str) -> None:
    conn.execute(
        "INSERT INTO normative_indici_meta(chiave, valore) VALUES (?, ?) "
        "ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore",
        (chiave, valore),
    )


def elimina_indice_fts(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS normative_fts;
        DROP TABLE IF EXISTS normative_fts_info;
        DELETE FROM normative_indici_meta WHERE chiave LIKE 'fts_%';
        """
    )


def _identita(codice: str, atto_numero: str, atto_anno: str, urn: str, titolo: str, document_id: int) -> str:
    """Stessa norma in versioni diverse (VIGENTE, ORIGINALE) → stessa identità."""

    if codice:
        return f"codice:{codice}"
    if atto_numero and atto_anno:
        return f"atto:{atto_numero}/{atto_anno}"
    if urn and urn.strip() not in {"urn:", ""}:
        return f"urn:{urn.strip().lower()}"
    if titolo:
        return "titolo:" + re.sub(r"\s+", " ", titolo.strip().lower())[:160]
    return f"doc:{document_id}"


@dataclass(slots=True)
class EsitoSincronizzazione:
    indicizzati: int = 0
    gia_presenti: int = 0
    orfani: int = 0
    ricostruito: bool = False
    secondi: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicizzati": self.indicizzati,
            "gia_presenti": self.gia_presenti,
            "orfani": self.orfani,
            "ricostruito": self.ricostruito,
            "secondi": round(self.secondi, 2),
        }


def _info_chunk(riga: sqlite3.Row) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    try:
        metadata = json.loads(riga["metadata_json"] or "{}")
    except (TypeError, ValueError):
        metadata = {}
    articolo_grezzo = riga["article_number"] or metadata.get("article_number") or ""
    if not articolo_grezzo:
        trovato = _ARTICOLO_IN_TESTO_RE.match(riga["chunk_text"] or "")
        articolo_grezzo = trovato.group(1) if trovato else ""
    articolo = articolo_normalizzato(articolo_grezzo)
    numero = str(riga["numero"] or "").strip()
    data_atto = str(riga["data_atto"] or "").strip()
    codice = codice_da_atto(numero, data_atto, riga["titolo"])
    atto_numero = ""
    atto_anno = ""
    if numero.isdigit() and len(data_atto) >= 4:
        atto_numero = str(int(numero))
        atto_anno = data_atto[:4]
    parte = 1
    trovato = _PARTE_RE.search(str(riga["chunk_key"] or ""))
    if trovato:
        parte = int(trovato.group(1))
    vigenza = str(riga["vigenza"] or "").strip().upper()
    titolo_atto = str(riga["titolo"] or "")
    etichetta = CODICI_PER_CHIAVE[codice].etichetta if codice in CODICI_PER_CHIAVE else ""
    rubrica = str(riga["article_title"] or metadata.get("article_title") or "")
    return {
        "chunk_id": int(riga["chunk_id"]),
        "document_id": int(riga["document_id"]),
        "articolo": articolo,
        "parte": parte,
        "codice": codice,
        "atto_numero": atto_numero,
        "atto_anno": atto_anno,
        "vigenza": vigenza,
        "identita": _identita(codice, atto_numero, atto_anno, str(riga["urn"] or ""), titolo_atto, int(riga["document_id"])),
        "titolo_indice": testo_indice(" ".join(part for part in (etichetta, titolo_atto, rubrica) if part)),
        "testo_indice": testo_indice(riga["chunk_text"] or ""),
    }


_SELEZIONE_CHUNK = """
    SELECT c.id AS chunk_id, c.document_id, c.chunk_key, c.chunk_text, c.metadata_json,
           a.article_number, a.article_title, d.titolo, d.numero, d.data_atto, d.vigenza, d.urn
    FROM normative_chunks c
    JOIN normative_documents d ON d.id = c.document_id
    LEFT JOIN normative_articles a ON a.id = c.article_id
"""


def sincronizza_fts(
    conn: sqlite3.Connection,
    *,
    ricostruisci: bool = False,
    blocco: int = 2000,
    progresso: Callable[[int, int], None] | None = None,
) -> EsitoSincronizzazione:
    """Indicizza i chunk Normattiva non ancora presenti nell'indice FTS5 (incrementale).

    Ricostruisce da zero se richiesto o se l'analizzatore è cambiato rispetto all'indice esistente.
    """

    inizio = time.monotonic()
    esito = EsitoSincronizzazione()
    assicura_schema_fts(conn)
    versione = _leggi_meta(conn, "fts_analizzatore")
    ha_righe = bool(conn.execute("SELECT 1 FROM normative_fts_info LIMIT 1").fetchone())
    if ricostruisci or (ha_righe and versione != VERSIONE_ANALIZZATORE):
        elimina_indice_fts(conn)
        assicura_schema_fts(conn)
        esito.ricostruito = True
    _scrivi_meta(conn, "fts_analizzatore", VERSIONE_ANALIZZATORE)
    conn.commit()

    conn_row_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        totale_da_fare = int(
            conn.execute(
                "SELECT COUNT(*) FROM normative_chunks c "
                "WHERE NOT EXISTS (SELECT 1 FROM normative_fts_info i WHERE i.chunk_id = c.id)"
            ).fetchone()[0]
        )
        esito.gia_presenti = int(conn.execute("SELECT COUNT(*) FROM normative_fts_info").fetchone()[0])
        ultimo_id = 0
        while True:
            righe = conn.execute(
                _SELEZIONE_CHUNK
                + " WHERE c.id > ? AND NOT EXISTS (SELECT 1 FROM normative_fts_info i WHERE i.chunk_id = c.id)"
                + " ORDER BY c.id LIMIT ?",
                (ultimo_id, max(1, int(blocco))),
            ).fetchall()
            if not righe:
                break
            info = [_info_chunk(riga) for riga in righe]
            conn.executemany(
                "INSERT INTO normative_fts(rowid, titolo, testo) VALUES (?, ?, ?)",
                [(item["chunk_id"], item["titolo_indice"], item["testo_indice"]) for item in info],
            )
            conn.executemany(
                """
                INSERT OR REPLACE INTO normative_fts_info
                (chunk_id, document_id, articolo, parte, codice, atto_numero, atto_anno, vigenza, identita)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["chunk_id"], item["document_id"], item["articolo"], item["parte"], item["codice"],
                        item["atto_numero"], item["atto_anno"], item["vigenza"], item["identita"],
                    )
                    for item in info
                ],
            )
            conn.commit()
            esito.indicizzati += len(info)
            ultimo_id = info[-1]["chunk_id"]
            if progresso is not None:
                progresso(esito.indicizzati, totale_da_fare)
        esito.orfani = int(
            conn.execute(
                "SELECT COUNT(*) FROM normative_fts_info i "
                "WHERE NOT EXISTS (SELECT 1 FROM normative_chunks c WHERE c.id = i.chunk_id)"
            ).fetchone()[0]
        )
        if esito.orfani:
            logger.warning(
                "Indice FTS Normattiva: %s chunk indicizzati non esistono piu' nel database; "
                "vengono ignorati in ricerca (ricostruire con --ricostruisci per eliminarli).",
                esito.orfani,
            )
    finally:
        conn.row_factory = conn_row_factory
    esito.secondi = time.monotonic() - inizio
    return esito


@dataclass(slots=True)
class RisultatoLessicale:
    chunk_id: int
    punteggio: float
    bm25: float
    pertinenza: float
    esatto: bool
    articolo: str
    codice: str
    vigenza: str
    identita: str
    parte: int


def _termine_fts(radice: str) -> str:
    pulita = re.sub(r"[^0-9a-z]", "", radice.lower())
    if not pulita:
        return ""
    if len(pulita) >= 5 and not pulita.isdigit():
        return f'"{pulita}"*'
    return f'"{pulita}"'


def espressione_fts(termini: Iterable[str]) -> str:
    voci: list[str] = []
    for termine in termini:
        voce = _termine_fts(termine)
        if voce and voce not in voci:
            voci.append(voce)
    return " OR ".join(voci)


def _info_per_id(conn: sqlite3.Connection, ids: list[int]) -> dict[int, tuple]:
    risultato: dict[int, tuple] = {}
    for inizio in range(0, len(ids), 500):
        parte = ids[inizio : inizio + 500]
        segnaposti = ",".join("?" for _ in parte)
        for riga in conn.execute(
            f"SELECT chunk_id, articolo, codice, atto_numero, atto_anno, vigenza, identita, parte "
            f"FROM normative_fts_info WHERE chunk_id IN ({segnaposti})",
            parte,
        ).fetchall():
            risultato[int(riga[0])] = tuple(riga[1:])
    return risultato


def candidati_esatti(conn: sqlite3.Connection, analisi: AnalisiDomanda, *, limite: int = 60) -> list[int]:
    if not analisi.articoli:
        return []
    segnaposti = ",".join("?" for _ in analisi.articoli)
    if analisi.codice:
        sql = f"SELECT chunk_id FROM normative_fts_info WHERE codice = ? AND articolo IN ({segnaposti}) LIMIT ?"
        parametri: list[Any] = [analisi.codice, *analisi.articoli, limite]
    elif analisi.atto_numero:
        sql = (
            f"SELECT chunk_id FROM normative_fts_info WHERE atto_numero = ? AND atto_anno = ? "
            f"AND articolo IN ({segnaposti}) LIMIT ?"
        )
        parametri = [analisi.atto_numero, analisi.atto_anno, *analisi.articoli, limite]
    else:
        sql = f"SELECT chunk_id FROM normative_fts_info WHERE articolo IN ({segnaposti}) LIMIT ?"
        parametri = [*analisi.articoli, limite]
    return [int(riga[0]) for riga in conn.execute(sql, parametri).fetchall()]


def cerca_fts(
    conn: sqlite3.Connection,
    analisi: AnalisiDomanda,
    *,
    limite: int = 50,
    candidati: int = 200,
    vigenza: str | None = None,
    usa_espansioni: bool = True,
) -> list[RisultatoLessicale]:
    """Ricerca lessicale: termini in OR con bm25, riferimento esatto in testa, versione vigente prima.

    ``vigenza`` («VIGENTE» o «ORIGINALE») filtra le versioni; senza filtro la versione vigente ha la
    priorità e le altre versioni dello stesso articolo vengono scartate.
    """

    termini = list(analisi.termini) + (list(analisi.espansioni) if usa_espansioni else [])
    espressione = espressione_fts(termini)
    bm25_per_id: dict[int, float] = {}
    if espressione:
        try:
            for rowid, valore in conn.execute(
                f"SELECT rowid, bm25(normative_fts, {PESO_TITOLO}, {PESO_TESTO}) AS r "
                "FROM normative_fts WHERE normative_fts MATCH ? ORDER BY r LIMIT ?",
                (espressione, max(1, int(candidati))),
            ).fetchall():
                bm25_per_id[int(rowid)] = float(valore)
        except sqlite3.OperationalError as exc:
            logger.warning("Ricerca FTS Normattiva non eseguibile (%s): %s", espressione, exc)
    esatti = set(candidati_esatti(conn, analisi))
    ids = list(dict.fromkeys([*esatti, *bm25_per_id.keys()]))
    if not ids:
        return []
    info = _info_per_id(conn, ids)
    migliore = min(bm25_per_id.values()) if bm25_per_id else -1.0
    filtro = str(vigenza or "").strip().upper()
    risultati: list[RisultatoLessicale] = []
    for chunk_id in ids:
        dati = info.get(chunk_id)
        if dati is None:
            continue  # chunk orfano
        articolo, codice, atto_numero, atto_anno, vig, identita, parte = dati
        if filtro and vig != filtro:
            continue
        valore_bm25 = bm25_per_id.get(chunk_id, 0.0)
        pertinenza = (valore_bm25 / migliore) if (valore_bm25 < 0 and migliore < 0) else 0.0
        esatto = chunk_id in esatti and bool(analisi.codice or analisi.atto_numero)
        punteggio = pertinenza
        if chunk_id in esatti:
            punteggio += BONUS_ESATTO if esatto else BONUS_ARTICOLO_SENZA_CODICE
            if int(parte or 1) > 1:
                punteggio -= 0.02 * min(10, int(parte) - 1)
        if vig == "VIGENTE":
            punteggio += BONUS_VIGENTE
        elif vig == "ORIGINALE":
            punteggio -= BONUS_VIGENTE
        risultati.append(
            RisultatoLessicale(
                chunk_id=chunk_id,
                punteggio=round(punteggio, 6),
                bm25=valore_bm25,
                pertinenza=round(pertinenza, 6),
                esatto=esatto,
                articolo=articolo,
                codice=codice,
                vigenza=vig,
                identita=identita,
                parte=int(parte or 1),
            )
        )
    risultati.sort(key=lambda r: (-r.punteggio, r.chunk_id))
    return deduplica_versioni(risultati)[: max(1, int(limite))]


def deduplica_versioni(risultati: list[Any]) -> list[Any]:
    """Una sola versione di ogni articolo: la vigente quando c'è, con il punteggio migliore del gruppo.

    ``risultati`` è già ordinato per punteggio decrescente; l'ordine finale resta per punteggio.
    """

    gruppi: dict[tuple[str, str, int], list[Any]] = {}
    ordine: list[Any] = []
    for risultato in risultati:
        articolo = getattr(risultato, "articolo", "")
        identita = getattr(risultato, "identita", "")
        if not (articolo and identita):
            ordine.append(risultato)
            continue
        chiave = (identita, articolo, int(getattr(risultato, "parte", 1) or 1))
        if chiave not in gruppi:
            gruppi[chiave] = []
            ordine.append(chiave)
        gruppi[chiave].append(risultato)
    unici: list[Any] = []
    for voce in ordine:
        if not isinstance(voce, tuple):
            unici.append(voce)
            continue
        membri = gruppi[voce]
        scelto = next((m for m in membri if getattr(m, "vigenza", "") == "VIGENTE"), membri[0])
        migliore = max(float(getattr(m, "punteggio", 0.0) or 0.0) for m in membri)
        if scelto is not membri[0]:
            # La versione vigente prende il posto della migliore, con il suo punteggio di pertinenza.
            try:
                scelto.punteggio = migliore
            except AttributeError:
                pass
        unici.append(scelto)
    unici.sort(key=lambda r: -float(getattr(r, "punteggio", 0.0) or 0.0))
    return unici


def carica_chunk(conn: sqlite3.Connection, ids: list[int]) -> dict[int, dict[str, Any]]:
    """Righe complete dei chunk, nello stesso formato di ``search_normattiva``."""

    risultato: dict[int, dict[str, Any]] = {}
    precedente = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        for inizio in range(0, len(ids), 500):
            parte = ids[inizio : inizio + 500]
            segnaposti = ",".join("?" for _ in parte)
            for riga in conn.execute(
                f"""
                SELECT c.id AS chunk_id, c.chunk_key, c.chunk_text, c.metadata_json, d.id AS document_id,
                       d.titolo, d.data_atto, d.data_pubblicazione, d.urn, d.vigenza, d.zip_path,
                       d.xml_entry, d.xml_sha256, d.imported_at, a.article_number, a.article_title
                FROM normative_chunks c
                JOIN normative_documents d ON d.id = c.document_id
                LEFT JOIN normative_articles a ON a.id = c.article_id
                WHERE c.id IN ({segnaposti})
                """,
                parte,
            ).fetchall():
                metadata: dict[str, Any]
                try:
                    metadata = json.loads(riga["metadata_json"] or "{}")
                except (TypeError, ValueError):
                    metadata = {}
                topics = metadata.get("topics")
                risultato[int(riga["chunk_id"])] = {
                    "chunk_id": riga["chunk_key"] or riga["chunk_id"],
                    "chunk_rowid": int(riga["chunk_id"]),
                    "document_id": riga["document_id"],
                    "fonte": "Normattiva",
                    "titolo": riga["titolo"],
                    "data": riga["data_atto"] or riga["data_pubblicazione"],
                    "url_origine": riga["urn"] or riga["zip_path"],
                    "path_origine": riga["zip_path"],
                    "articolo_o_chunk": riga["article_number"] or metadata.get("article_number") or riga["chunk_id"],
                    "rubrica": riga["article_title"] or metadata.get("article_title") or "",
                    "testo": riga["chunk_text"],
                    "materia": topics[0] if isinstance(topics, list) and topics else "",
                    "vigenza": riga["vigenza"],
                    "livello_affidabilita": "ufficiale",
                    "data_acquisizione": riga["imported_at"],
                    "hash_sha256": riga["xml_sha256"],
                    "metadata": metadata,
                }
    finally:
        conn.row_factory = precedente
    return risultato


__all__ = [
    "EsitoSincronizzazione",
    "RisultatoLessicale",
    "assicura_schema_fts",
    "candidati_esatti",
    "carica_chunk",
    "cerca_fts",
    "deduplica_versioni",
    "elimina_indice_fts",
    "espressione_fts",
    "indice_fts_presente",
    "sincronizza_fts",
]
