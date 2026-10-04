"""Integrazione dell'archivio Normattiva con le leggi ordinarie essenziali per lo studio.

Normattiva Open Data distribuisce gli atti in collezioni predefinite per tipo (codici, testi unici,
decreti legislativi, d.P.R., decreti-legge con leggi di conversione, leggi costituzionali, leggi delega,
di ratifica, di bilancio): **le leggi ordinarie non hanno una collezione**. Nell'archivio mancano quindi
la Costituzione, la l. 241/1990, la l. 53/1994 (notifiche degli avvocati), la l. 742/1969 (sospensione
feriale), la l. 689/1981, le leggi sulle locazioni, il divorzio, lo Statuto dei lavoratori e altre.

Questo modulo le inserisce nello stesso database e nello stesso formato degli altri atti (documento,
articoli, chunk, indice FTS), partendo da un file JSONL con un articolo per riga:

    {"chiave": "legge_53_1994", "atto": "l. 53/1994", "articolo": "3bis", "rubrica": "", "testo": "Art. 3-bis. ...",
     "titolo_atto": "Facolta' di notificazioni ...", "data_atto": "1994-01-21", "urn": "urn:nir:stato:legge:1994-01-21;53",
     "fonte_testo": "edizionieuropee.it", "url": "https://..."}

Il file di riferimento e' ``lex/normativa/integrazioni/leggi_essenziali.jsonl`` (testi vigenti raccolti e
controllati il 03/10/2026). L'operazione e' idempotente: un atto gia' presente con lo stesso contenuto viene
saltato; se il contenuto cambia, la versione precedente viene sostituita (chunk, articoli, indice FTS).
I vettori dei nuovi chunk li calcola il passaggio notturno ``indice_vettoriale aggiorna`` (o ``--vettori``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from lex.normativa.normattiva_importer import (
    ArticleRecord,
    DocumentRecord,
    ensure_schema,
    insert_articles_and_chunks,
    insert_document,
)

logger = logging.getLogger(__name__)

COLLEZIONE = "Integrazione leggi essenziali"
FILE_PREDEFINITO = Path(__file__).resolve().parent / "integrazioni" / "leggi_essenziali.jsonl"
VIGENZA = "VIGENTE"

_TIPO_DA_URN = {
    "legge": "Legge",
    "decreto.legge": "Decreto-legge",
    "decreto.legislativo": "Decreto legislativo",
    "decreto.del.presidente.della.repubblica": "Decreto del Presidente della Repubblica",
    "regio.decreto": "Regio decreto",
    "costituzione": "Costituzione",
    "regolamento": "Regolamento (UE)",
    "codice.deontologico": "Codice deontologico",
}


@dataclass
class EsitoIntegrazione:
    atti_letti: int = 0
    atti_inseriti: int = 0
    atti_sostituiti: int = 0
    atti_gia_presenti: int = 0
    atti_saltati: int = 0
    articoli_inseriti: int = 0
    chunk_inseriti: int = 0
    fts_indicizzati: int = 0
    dettagli: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "dettagli"} | {"dettagli": list(self.dettagli or [])}


def leggi_jsonl(percorso: Path) -> dict[str, list[dict[str, Any]]]:
    """Righe raggruppate per chiave dell'atto, nell'ordine del file."""

    gruppi: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with Path(percorso).open(encoding="utf-8") as f:
        for numero_riga, riga in enumerate(f, start=1):
            riga = riga.strip()
            if not riga:
                continue
            try:
                dato = json.loads(riga)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{percorso}: riga {numero_riga} non e' JSON valido ({exc})") from exc
            for campo in ("chiave", "atto", "articolo", "testo", "titolo_atto", "data_atto", "urn"):
                if not str(dato.get(campo) or "").strip():
                    raise ValueError(f"{percorso}: riga {numero_riga} senza campo '{campo}'")
            gruppi[str(dato["chiave"])].append(dato)
    return dict(gruppi)


def _numero_e_tipo(urn: str) -> tuple[str | None, str | None]:
    """'urn:nir:stato:legge:1994-01-21;53' -> ('53', 'Legge'); la Costituzione non ha numero."""

    m = re.match(r"urn:nir:(?:stato|unione\.europea|consiglio\.nazionale\.forense):([a-z.]+):(\d{4}-\d{2}-\d{2})(?:;(\d+))?",
                 urn.strip().lower())
    if not m:
        return None, None
    tipo = _TIPO_DA_URN.get(m.group(1), m.group(1).replace(".", " ").title())
    return (m.group(3) or None), tipo


def _etichetta_numero_articolo(valore: str) -> str:
    """'3bis' -> 'Art. 3-bis.' (stesso formato dei <num> di Normattiva)."""

    v = str(valore).strip().lower().replace(" ", "")
    m = re.fullmatch(r"(\d+)([a-z]*)", v)
    if not m:
        return f"Art. {valore}."
    return f"Art. {m.group(1)}{'-' + m.group(2) if m.group(2) else ''}."


def impronta_atto(righe: Iterable[dict[str, Any]]) -> str:
    """SHA-256 del contenuto (articoli e testi): cambia solo se cambia il testo."""

    canonico = json.dumps(
        [[str(r.get("articolo")), str(r.get("rubrica") or ""), str(r.get("testo"))] for r in righe],
        ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def documento_da_righe(chiave: str, righe: list[dict[str, Any]]) -> DocumentRecord:
    prima = righe[0]
    urn = str(prima["urn"]).strip()
    numero, tipo = _numero_e_tipo(urn)
    data_atto = str(prima["data_atto"]).strip()
    articoli = [
        ArticleRecord(
            article_number=_etichetta_numero_articolo(str(r["articolo"])),
            article_title=str(r.get("rubrica") or "").strip() or None,
            article_text=str(r["testo"]).strip(),
            topics=[],
            relevance_score=5.0,
        )
        for r in righe
    ]
    nome_voce = f"{(tipo or 'Atto').upper().replace(' ', '_')}_{data_atto.replace('-', '')}_{numero or '0'}.json"
    return DocumentRecord(
        collection_name=COLLEZIONE,
        zip_path=f"integrazione:{chiave}",
        xml_entry=nome_voce,
        tipo_atto=tipo,
        numero=numero,
        data_atto=data_atto,
        data_pubblicazione=None,
        titolo=str(prima["titolo_atto"]).strip(),
        urn=urn,
        redazione_id=None,
        vigenza=VIGENZA,
        xml_sha256=impronta_atto(righe),
        text_content=" ".join(a.article_text for a in articoli),
        topics=["integrazione_leggi_essenziali"],
        relevance_score=5.0,
        is_relevant=True,
        articles=articoli,
    )


def _rimuovi_documento(conn: sqlite3.Connection, document_id: int) -> None:
    """Toglie documento, articoli, chunk e righe dell'indice FTS (contentless: cancellazione esplicita)."""

    from lex.ricerca_giuridica.indice_fts import _SELEZIONE_CHUNK, _info_chunk, indice_fts_presente

    ids = [int(r[0]) for r in conn.execute("SELECT id FROM normative_chunks WHERE document_id = ?", (document_id,))]
    if ids and indice_fts_presente(conn):
        precedente = conn.row_factory
        conn.row_factory = sqlite3.Row
        try:
            for inizio in range(0, len(ids), 500):
                parte = ids[inizio:inizio + 500]
                segnaposti = ",".join("?" for _ in parte)
                righe = conn.execute(_SELEZIONE_CHUNK + f" WHERE c.id IN ({segnaposti})", parte).fetchall()
                info = [_info_chunk(r) for r in righe]
                indicizzati = {int(r[0]) for r in conn.execute(
                    f"SELECT chunk_id FROM normative_fts_info WHERE chunk_id IN ({segnaposti})", parte)}
                conn.executemany(
                    "INSERT INTO normative_fts(normative_fts, rowid, titolo, testo) VALUES ('delete', ?, ?, ?)",
                    [(i["chunk_id"], i["titolo_indice"], i["testo_indice"]) for i in info if i["chunk_id"] in indicizzati],
                )
                conn.execute(f"DELETE FROM normative_fts_info WHERE chunk_id IN ({segnaposti})", parte)
        finally:
            conn.row_factory = precedente
    conn.execute("DELETE FROM normative_chunks WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM normative_articles WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM normative_documents WHERE id = ?", (document_id,))


def integra(
    db_path: str | Path,
    *,
    jsonl: str | Path = FILE_PREDEFINITO,
    vigenza_archivio: str = VIGENZA,
    jsonl_chunk: str | Path | None = None,
    solo_chiavi: Iterable[str] | None = None,
) -> EsitoIntegrazione:
    """Inserisce (o aggiorna) nel database gli atti del file JSONL. Aggiorna l'indice FTS."""

    esito = EsitoIntegrazione(dettagli=[])
    if str(vigenza_archivio or VIGENZA).strip().upper() != VIGENZA:
        esito.dettagli.append(f"archivio in vigenza {vigenza_archivio}: i testi integrati sono VIGENTI, nessuna modifica")
        return esito
    gruppi = leggi_jsonl(Path(jsonl))
    scelte = set(solo_chiavi or [])
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn)
    percorso_chunk = Path(jsonl_chunk) if jsonl_chunk else db_path.parent / "index" / "integrazione_leggi_chunks.jsonl"
    percorso_chunk.parent.mkdir(parents=True, exist_ok=True)
    try:
        with percorso_chunk.open("a", encoding="utf-8") as jf:
            for chiave, righe in gruppi.items():
                if scelte and chiave not in scelte:
                    continue
                esito.atti_letti += 1
                doc = documento_da_righe(chiave, righe)
                esistenti = conn.execute(
                    "SELECT id, xml_sha256 FROM normative_documents WHERE urn = ? AND collection_name = ?",
                    (doc.urn, COLLEZIONE),
                ).fetchall()
                if any(str(r[1]) == doc.xml_sha256 for r in esistenti):
                    esito.atti_gia_presenti += 1
                    esito.dettagli.append(f"{righe[0]['atto']}: gia' presente ({len(righe)} articoli)")
                    continue
                # un atto dello stesso URN importato da Open Data (collezione diversa) non si tocca:
                # se Normattiva un giorno lo distribuira', convivono come versioni e vince il punteggio
                sostituito = False
                for r in esistenti:
                    _rimuovi_documento(conn, int(r[0]))
                    sostituito = True
                doc_id = insert_document(conn, doc, store_full_text=False)
                if doc_id is None:
                    esito.atti_saltati += 1
                    esito.dettagli.append(f"{righe[0]['atto']}: impronta gia' presente in un'altra collezione, saltato")
                    continue
                n_art, n_chunk = insert_articles_and_chunks(
                    conn, doc_id, doc, jsonl_file=jf, max_chunk_chars=1800, only_relevant_articles=False,
                )
                esito.articoli_inseriti += n_art
                esito.chunk_inseriti += n_chunk
                if sostituito:
                    esito.atti_sostituiti += 1
                    esito.dettagli.append(f"{righe[0]['atto']}: aggiornato ({n_art} articoli, {n_chunk} chunk)")
                else:
                    esito.atti_inseriti += 1
                    esito.dettagli.append(f"{righe[0]['atto']}: inserito ({n_art} articoli, {n_chunk} chunk)")
                conn.commit()
        if esito.atti_inseriti or esito.atti_sostituiti:
            from lex.ricerca_giuridica.indice_fts import sincronizza_fts

            esito.fts_indicizzati = sincronizza_fts(conn).indicizzati
        conn.commit()
    finally:
        conn.close()
    return esito


def verifica(db_path: str | Path, *, jsonl: str | Path = FILE_PREDEFINITO) -> list[str]:
    """Per ogni atto del file: quanti articoli ha nel database e se un articolo di prova si trova con la ricerca."""

    from lex.ricerca_giuridica.ibrida import cerca_normattiva_indicizzata

    gruppi = leggi_jsonl(Path(jsonl))
    conn = sqlite3.connect(str(db_path))
    righe_out: list[str] = []
    try:
        for chiave, righe in gruppi.items():
            urn = str(righe[0]["urn"]).strip()
            n = conn.execute(
                "SELECT COUNT(*) FROM normative_articles a JOIN normative_documents d ON d.id = a.document_id "
                "WHERE d.urn = ? AND d.collection_name = ?", (urn, COLLEZIONE)).fetchone()[0]
            righe_out.append(f"{righe[0]['atto']:<18} articoli nel database: {n:>4} (nel file: {len(righe)})")
    finally:
        conn.close()
    prove = {
        "legge_53_1994": "notificazione a mezzo pec art. 3-bis legge 53/1994",
        "legge_742_1969": "sospensione feriale dei termini processuali dal 1 al 31 agosto",
        "costituzione": "art. 24 cost. diritto di difesa",
        "legge_241_1990": "termine di conclusione del procedimento amministrativo trenta giorni",
    }
    for chiave, domanda in prove.items():
        if chiave not in gruppi:
            continue
        risultati = cerca_normattiva_indicizzata(domanda, db_path, limite=3) or []
        titoli = [f"{(r.get('metadata') or {}).get('article_number', '?')} {str(r.get('titolo') or '')[:40]}" for r in risultati]
        righe_out.append(f"ricerca «{domanda}» -> {titoli}")
    return righe_out


__all__ = [
    "COLLEZIONE",
    "EsitoIntegrazione",
    "FILE_PREDEFINITO",
    "documento_da_righe",
    "impronta_atto",
    "integra",
    "leggi_jsonl",
    "verifica",
]
