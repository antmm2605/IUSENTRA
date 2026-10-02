"""Test dell'indice lessicale FTS5 su normative_chunks (modulo 2A)."""

from __future__ import annotations

import io
import sqlite3
import sys
from pathlib import Path

import pytest

from lex.normativa import normattiva_importer as imp
from lex.ricerca_giuridica import indice_fts
from lex.ricerca_giuridica.testo import (
    STOPWORD,
    analizza_domanda,
    senza_accenti,
    stem,
    termini_indice,
)

CC = ("262", "1942-03-16", "Codice civile")


def _doc(sha, numero, data, titolo, vigenza, articoli):
    return imp.DocumentRecord(
        collection_name="test", zip_path="t.zip", xml_entry=f"{sha}.xml", tipo_atto="CODICE",
        numero=numero, data_atto=data, data_pubblicazione=data, titolo=titolo, urn=f"urn:{sha}",
        redazione_id=None, vigenza=vigenza, xml_sha256=sha, text_content="", topics=[],
        relevance_score=5.0, is_relevant=True,
        articles=[imp.ArticleRecord(n, r, t, [], 1.0) for n, r, t in articoli],
    )


def _importa(conn, doc):
    doc_id = imp.insert_document(conn, doc, store_full_text=False)
    out = io.StringIO()
    imp.insert_articles_and_chunks(
        conn, doc_id, doc, jsonl_file=out, max_chunk_chars=1800, only_relevant_articles=False
    )
    conn.commit()
    return doc_id


@pytest.fixture()
def conn(tmp_path):
    c = sqlite3.connect(str(tmp_path / "n.db"))
    imp.ensure_schema(c)
    _importa(c, _doc("a" * 8, *CC[:2], CC[2], "VIGENTE", [
        ("2043", "Risarcimento per fatto illecito",
         "Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga colui che ha commesso il fatto a risarcire il danno."),
        ("1453", "Risolubilita del contratto per inadempimento",
         "Nei contratti con prestazioni corrispettive, quando uno dei contraenti non adempie le sue obbligazioni, l'altro puo chiedere la risoluzione del contratto."),
        ("2946", "Prescrizione ordinaria", "Salvi i casi in cui la legge dispone diversamente, i diritti si estinguono per prescrizione con il decorso di dieci anni."),
        ("1490", "Garanzia per i vizi della cosa venduta", "Il venditore e tenuto a garantire che la cosa venduta sia immune da vizi."),
    ]))
    _importa(c, _doc("b" * 8, *CC[:2], CC[2], "ORIGINALE", [
        ("2043", "Risarcimento per fatto illecito", "Testo originario: qualunque fatto doloso o colposo che cagiona danno ingiusto obbliga al risarcimento."),
    ]))
    yield c
    c.close()


# --- normalizzazione, stopword, stemming ---------------------------------------------------------

def test_senza_accenti_e_stopword():
    assert senza_accenti("responsabilità") == "responsabilita"
    assert "il" in STOPWORD and "della" in STOPWORD
    termini = termini_indice("Il risarcimento della responsabilità")
    assert "il" not in termini and "della" not in termini


def test_stemming_unisce_forme_flesse():
    assert stem("responsabilità") == stem("responsabile")
    assert stem("risarcimento") == stem("risarcire") or stem("risarcimento").startswith("risarc")
    assert stem("risarcimento").startswith("risarc")


def test_numeri_conservati_e_sigle_compattate():
    assert "2043" in termini_indice("art. 2043")
    assert "cc" in termini_indice("art. 2043 c.c.")


def test_analisi_domanda_riferimento_esatto():
    a = analizza_domanda("Cosa dice l'art. 2043 c.c.?")
    assert a.articoli == ["2043"] and a.codice == "codice_civile" and a.riferimento_esatto
    assert "2043" not in a.termini


# --- indice ----------------------------------------------------------------------------------------

def test_costruzione_indice_e_incrementale(conn):
    assert not indice_fts.indice_fts_presente(conn)
    esito = indice_fts.sincronizza_fts(conn)
    assert esito.indicizzati == 5 and indice_fts.indice_fts_presente(conn)
    esito2 = indice_fts.sincronizza_fts(conn)
    assert esito2.indicizzati == 0 and esito2.gia_presenti == 5
    righe = conn.execute("SELECT codice, articolo, vigenza FROM normative_fts_info WHERE articolo='2043'").fetchall()
    assert {r[2] for r in righe} == {"VIGENTE", "ORIGINALE"}
    assert all(r[0] == "codice_civile" for r in righe)


def test_ricerca_or_bm25(conn):
    indice_fts.sincronizza_fts(conn)
    a = analizza_domanda("quali sono i presupposti della responsabilità per fatto illecito e danno ingiusto")
    ris = indice_fts.cerca_fts(conn, a, limite=5)
    assert ris and ris[0].articolo == "2043"
    # OR: basta un termine
    a2 = analizza_domanda("prescrizione xyzzyqq")
    assert indice_fts.cerca_fts(conn, a2, limite=5)[0].articolo == "2946"
    assert ris[0].bm25 < 0


def test_boost_articolo_esatto(conn):
    indice_fts.sincronizza_fts(conn)
    # il testo di 1453 parla di inadempimento, ma la domanda cita l'art. 2946 c.c.
    ris = indice_fts.cerca_fts(conn, analizza_domanda("art. 2946 c.c. inadempimento contratto"), limite=5)
    assert ris[0].articolo == "2946" and ris[0].esatto
    ris2 = indice_fts.cerca_fts(conn, analizza_domanda("art. 2043 c.c."), limite=5)
    assert ris2[0].articolo == "2043"


def test_priorita_vigente_e_filtro(conn):
    indice_fts.sincronizza_fts(conn)
    ris = indice_fts.cerca_fts(conn, analizza_domanda("fatto doloso colposo danno ingiusto"), limite=10)
    art2043 = [r for r in ris if r.articolo == "2043"]
    assert len(art2043) == 1 and art2043[0].vigenza == "VIGENTE"
    solo_orig = indice_fts.cerca_fts(conn, analizza_domanda("danno ingiusto"), limite=10, vigenza="ORIGINALE")
    assert solo_orig and all(r.vigenza == "ORIGINALE" for r in solo_orig)


def test_cambio_analizzatore_ricostruisce(conn):
    indice_fts.sincronizza_fts(conn)
    conn.execute("UPDATE normative_indici_meta SET valore='vecchio' WHERE chiave='fts_analizzatore'")
    conn.commit()
    esito = indice_fts.sincronizza_fts(conn)
    assert esito.ricostruito and esito.indicizzati == 5


# --- importer -------------------------------------------------------------------------------------

def test_importer_senza_duplicazione_su_import_ripetuti(conn):
    def conta(t):
        return conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    art, chunk = conta("normative_articles"), conta("normative_chunks")
    for _ in range(3):
        _importa(conn, _doc("a" * 8, *CC[:2], CC[2], "VIGENTE", [
            ("2043", "Risarcimento per fatto illecito",
             "Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga colui che ha commesso il fatto a risarcire il danno."),
        ]))
    assert conta("normative_articles") == art and conta("normative_chunks") == chunk


def test_migrazione_rimuove_doppioni_esistenti(tmp_path):
    c = sqlite3.connect(str(tmp_path / "vecchio.db"))
    c.executescript(
        """
        CREATE TABLE normative_documents (id INTEGER PRIMARY KEY, xml_sha256 TEXT UNIQUE);
        CREATE TABLE normative_articles (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL,
            article_number TEXT, article_title TEXT, article_text TEXT, topics TEXT, relevance_score REAL, embedding_id TEXT);
        CREATE TABLE normative_chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL,
            article_id INTEGER, chunk_key TEXT UNIQUE, chunk_text TEXT NOT NULL);
        INSERT INTO normative_documents VALUES (1, 'x');
        INSERT INTO normative_articles(document_id, article_number, article_text) VALUES (1,'1','t'),(1,'1','t'),(1,'2','u');
        INSERT INTO normative_chunks(document_id, article_id, chunk_key, chunk_text)
            VALUES (1,1,'normattiva:x:art1:chunk1','t'),(1,3,'normattiva:x:art3:chunk1','u');
        """
    )
    esito = imp.migra_schema(c)
    assert esito["articoli_doppi_rimossi"] == 1
    assert c.execute("SELECT COUNT(*) FROM normative_articles").fetchone()[0] == 2
    assert imp.migra_schema(c)["articoli_doppi_rimossi"] == 0  # idempotente
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO normative_articles(document_id, article_key) SELECT 1, article_key FROM normative_articles LIMIT 1")
