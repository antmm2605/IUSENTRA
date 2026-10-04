"""Riallinea gli articoli di un archivio Normattiva gia' importato con la vecchia divisione testuale.

Difetti riconosciuti (vedi ``lex/normativa/articoli_testuali.py``):

* frammenti che iniziano con un rimando («art. 1284. Per la determinazione ...»): l'articolo precedente e'
  troncato (art. 2317, 1815 c.c.) e il frammento e' finito sotto un numero sbagliato;
* articoli che contengono le intestazioni di altri articoli (669-terdecies dentro 669 c.p.c., 5-bis dentro 5
  d.lgs. 28/2010, gli artt. 26-54 del c.p.a. dentro l'art. 25);
* nodi con il solo titolo («Art. 29 - Azione di annullamento») mentre il testo sta altrove.

Per ogni documento con almeno un difetto si ricompone il testo degli articoli nell'ordine dell'archivio, lo si
ridivide con le intestazioni corrette e, se i controlli di coerenza passano (nessun numero d'articolo perso,
testo complessivo conservato), si sostituiscono articoli, chunk e righe FTS del documento. Il documento resta
lo stesso (stesso id e impronta). Il riallineamento e' idempotente: su un archivio gia' corretto non fa nulla.
I chunk nuovi entrano nell'indice vettoriale con ``indice_vettoriale aggiorna`` (quelli tolti vengono marcati).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lex.normativa.articoli_testuali import (
    Segmento,
    chiave_numero,
    deduplica,
    dividi_in_articoli,
    inizia_con_rimando,
    solo_intestazione,
)

COLLEZIONI_ESCLUSE = {"Integrazione leggi essenziali"}
QUOTA_TESTO_MINIMA = 0.85      # il testo riallineato deve conservare almeno l'85% dei caratteri unici
QUOTA_NUMERI_PERSI = 0.02      # al massimo il 2% dei numeri d'articolo puo' sparire (frammenti spuri)


@dataclass
class EsitoRiallineamento:
    documenti_esaminati: int = 0
    documenti_con_difetti: int = 0
    documenti_riallineati: int = 0
    documenti_saltati: int = 0
    articoli_prima: int = 0
    articoli_dopo: int = 0
    chunk_inseriti: int = 0
    fts_indicizzati: int = 0
    secondi: float = 0.0
    dettagli: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Analisi:
    difetti: dict[str, int]
    segmenti: list[Segmento] | None
    motivo_salto: str = ""


def _con_intestazione(numero: str | None, testo: str) -> str:
    """Il testo di un nodo NIR puo' non iniziare con «Art. N»: si aggiunge per non perdere il confine."""

    t = str(testo or "").strip()
    if re.match(r"^(?:Art\.|ART\.|Articolo|ARTICOLO)\s*\d", t) or inizia_con_rimando(t):
        return t
    chiave = chiave_numero(numero or "")
    if not chiave:
        return t
    m = re.match(r"(\d+)([a-z]*)(?:\.(\d+))?", chiave)
    etichetta = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "") + (f".{m.group(3)}" if m.group(3) else "")
    return f"Art. {etichetta}. {t}"


def difetti_articoli(articoli: list[tuple[int, str | None, str]]) -> dict[str, int]:
    conta = {"rimando_iniziale": 0, "articoli_fusi": 0, "solo_titolo": 0}
    titoli: list[str] = []
    interni: set[str] = set()
    for _id, numero, testo in articoli:
        if inizia_con_rimando(testo):
            conta["rimando_iniziale"] += 1
            continue
        if solo_intestazione(testo):
            titoli.append(chiave_numero(numero or testo))
            continue
        proprio = chiave_numero(numero or "")
        segmenti = dividi_in_articoli(testo)
        altri = {chiave_numero(s.numero) for s in segmenti[1:]} - {proprio}
        if altri:
            conta["articoli_fusi"] += 1
            interni |= altri
    # un titolo senza testo e' un difetto solo se il testo di quell'articolo sta dentro un altro articolo
    conta["solo_titolo"] = sum(1 for chiave in titoli if chiave in interni)
    return conta


def analizza(articoli: list[tuple[int, str | None, str]]) -> Analisi:
    """Difetti del documento e, se ce ne sono, i nuovi articoli (None se i controlli non passano)."""

    difetti = difetti_articoli(articoli)
    if not any(difetti.values()):
        return Analisi(difetti, None)
    pezzi: list[str] = []
    for _id, numero, testo in articoli:
        if solo_intestazione(testo):
            continue
        t = _con_intestazione(numero, testo)
        if pezzi and inizia_con_rimando(t) and (pezzi[-1].endswith("'") or pezzi[-1].endswith("’")):
            pezzi[-1] = pezzi[-1] + t
        else:
            pezzi.append(t)
    nuovi = deduplica(dividi_in_articoli(" ".join(pezzi)))
    if not nuovi:
        return Analisi(difetti, None, "nessun articolo riconosciuto")

    vecchi_numeri = {chiave_numero(n or t) for _i, n, t in articoli if not inizia_con_rimando(t)} - {""}
    nuovi_numeri = {chiave_numero(s.numero) for s in nuovi}
    persi = vecchi_numeri - nuovi_numeri
    if vecchi_numeri and len(persi) > max(1, int(len(vecchi_numeri) * QUOTA_NUMERI_PERSI)):
        return Analisi(difetti, None, f"numeri d'articolo persi: {sorted(persi)[:8]}")
    vecchio_testo = deduplica([Segmento(n or "", t) for _i, n, t in articoli if not solo_intestazione(t)])
    caratteri_prima = sum(len(s.testo) for s in vecchio_testo)
    caratteri_dopo = sum(len(s.testo) for s in nuovi)
    if caratteri_prima and caratteri_dopo < caratteri_prima * QUOTA_TESTO_MINIMA:
        return Analisi(difetti, None, f"testo ridotto: {caratteri_dopo}/{caratteri_prima} caratteri")
    return Analisi(difetti, nuovi)


def _documento(conn: sqlite3.Connection, doc_id: int):
    from lex.normativa.normattiva_importer import ArticleRecord, DocumentRecord

    r = conn.execute(
        "SELECT collection_name, zip_path, xml_entry, tipo_atto, numero, data_atto, data_pubblicazione, titolo, urn, "
        "redazione_id, vigenza, xml_sha256, topics, relevance_score, is_relevant FROM normative_documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    try:
        topics = json.loads(r[12] or "[]")
    except (TypeError, ValueError):
        topics = []
    return DocumentRecord(
        collection_name=r[0], zip_path=r[1], xml_entry=r[2], tipo_atto=r[3], numero=r[4], data_atto=r[5],
        data_pubblicazione=r[6], titolo=r[7], urn=r[8], redazione_id=r[9], vigenza=r[10], xml_sha256=r[11],
        text_content="", topics=topics if isinstance(topics, list) else [], relevance_score=float(r[13] or 0),
        is_relevant=bool(r[14]), articles=[],
    ), ArticleRecord


def _togli_articoli(conn: sqlite3.Connection, doc_id: int) -> None:
    """Toglie articoli, chunk e righe FTS del documento (il documento resta)."""

    from lex.ricerca_giuridica.indice_fts import _SELEZIONE_CHUNK, _info_chunk, indice_fts_presente

    ids = [int(r[0]) for r in conn.execute("SELECT id FROM normative_chunks WHERE document_id = ?", (doc_id,))]
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
    conn.execute("DELETE FROM normative_chunks WHERE document_id = ?", (doc_id,))
    conn.execute("DELETE FROM normative_articles WHERE document_id = ?", (doc_id,))


def riallinea(
    db_path: str | Path,
    *,
    applica: bool = True,
    max_chunk_chars: int = 1800,
    solo_documenti: list[int] | None = None,
    limite_dettagli: int = 60,
) -> EsitoRiallineamento:
    from lex.normativa.normattiva_importer import (
        detect_topics,
        insert_articles_and_chunks,
        relevance_score,
        topic_names,
    )

    inizio = time.monotonic()
    esito = EsitoRiallineamento(dettagli=[])
    conn = sqlite3.connect(str(db_path))
    try:
        if solo_documenti:
            documenti = [(int(d),) for d in solo_documenti]
        else:
            segnaposti = ",".join("?" for _ in COLLEZIONI_ESCLUSE)
            documenti = conn.execute(
                f"SELECT id FROM normative_documents WHERE COALESCE(collection_name,'') NOT IN ({segnaposti}) ORDER BY id",
                tuple(COLLEZIONI_ESCLUSE),
            ).fetchall()
        with open(os.devnull, "w", encoding="utf-8") as nulla:
            for (doc_id,) in documenti:
                articoli = [
                    (int(r[0]), r[1], str(r[2] or ""))
                    for r in conn.execute(
                        "SELECT id, article_number, article_text FROM normative_articles WHERE document_id = ? ORDER BY id",
                        (doc_id,),
                    )
                ]
                if not articoli:
                    continue
                esito.documenti_esaminati += 1
                analisi = analizza(articoli)
                if not any(analisi.difetti.values()):
                    continue
                esito.documenti_con_difetti += 1
                titolo = (conn.execute("SELECT titolo FROM normative_documents WHERE id = ?", (doc_id,)).fetchone() or [""])[0]
                if analisi.segmenti is None:
                    esito.documenti_saltati += 1
                    if len(esito.dettagli) < limite_dettagli:
                        esito.dettagli.append(f"saltato doc {doc_id} ({str(titolo or '')[:60]}): {analisi.motivo_salto}")
                    continue
                esito.articoli_prima += len(articoli)
                esito.articoli_dopo += len(analisi.segmenti)
                if len(esito.dettagli) < limite_dettagli:
                    esito.dettagli.append(
                        f"doc {doc_id} ({str(titolo or '')[:60]}): {len(articoli)} -> {len(analisi.segmenti)} articoli, "
                        f"difetti {analisi.difetti}")
                if not applica:
                    continue
                doc, ArticleRecord = _documento(conn, doc_id)
                for seg in analisi.segmenti:
                    temi = detect_topics(doc.titolo or "", seg.testo, collection_name=doc.collection_name)
                    doc.articles.append(ArticleRecord(
                        article_number=f"Art. {seg.numero}.", article_title=None, article_text=seg.testo,
                        topics=topic_names(temi), relevance_score=relevance_score(temi)))
                try:
                    conn.execute("SAVEPOINT riallinea")
                    _togli_articoli(conn, doc_id)
                    _a, chunk = insert_articles_and_chunks(
                        conn, doc_id, doc, jsonl_file=nulla, max_chunk_chars=max_chunk_chars, only_relevant_articles=False)
                    conn.execute("RELEASE SAVEPOINT riallinea")
                    esito.chunk_inseriti += chunk
                    esito.documenti_riallineati += 1
                except sqlite3.Error as exc:
                    conn.execute("ROLLBACK TO SAVEPOINT riallinea")
                    conn.execute("RELEASE SAVEPOINT riallinea")
                    esito.documenti_saltati += 1
                    esito.dettagli.append(f"errore doc {doc_id}: {exc}")
                if esito.documenti_riallineati % 200 == 0:
                    conn.commit()
        conn.commit()
        if applica and esito.documenti_riallineati:
            from lex.ricerca_giuridica.indice_fts import sincronizza_fts

            esito.fts_indicizzati = sincronizza_fts(conn).indicizzati
            conn.commit()
    finally:
        conn.close()
    esito.secondi = round(time.monotonic() - inizio, 1)
    return esito


__all__ = ["Analisi", "EsitoRiallineamento", "analizza", "difetti_articoli", "riallinea"]
