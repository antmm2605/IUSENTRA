"""Regressioni di identità tra corpo dell'atto e allegati ufficiali."""
import hashlib
import io
import json
import sqlite3
from pathlib import Path

from lex.normativa.normattiva_importer import (
    ensure_schema, migra_schema, parse_xml, insert_document, insert_articles_and_chunks,
)
from lex.normativa.versioni_importazione import rettifica_da_xml
from lex.ricerca_giuridica.indice_fts import sincronizza_fts

XML = b'''<NIR xmlns="http://www.normeinrete.it/nir/2.2/">
<Legge><meta><descrittori><urn valore="urn:nir:stato:legge:2020-01-01;1"/></descrittori></meta>
<intestazione><tipoDoc>legge</tipoDoc><dataDoc norm="20200101"/><numDoc>1</numDoc><titoloDoc>Atto di prova strutturale</titoloDoc></intestazione>
<articolato><articolo><num>Art. 1.</num><comma><num>1</num><corpo>Corpo principale da conservare integralmente e senza aggiunte.</corpo></comma></articolo></articolato>
<annessi><annesso><DocumentoNIR><contenitore nome="Allegato">MODIFICAZIONI IN SEDE DI CONVERSIONE. All'articolo 1 sono apportate modifiche al diverso atto richiamato.</contenitore></DocumentoNIR></annesso></annessi>
</Legge></NIR>'''


def documento():
    return parse_xml(XML,zip_path=Path("fonte.zip"),entry="LEGGE_20200101_1/atto.xml",collection_name="Prova")


def test_allegato_non_accodato_all_articolo_principale():
    doc=documento()
    assert len(doc.articles)==1
    assert "MODIFICAZIONI" not in doc.articles[0].article_text
    assert "Corpo principale" in doc.articles[0].article_text
    assert len(doc.componenti)==1
    assert "MODIFICAZIONI" in doc.componenti[0]["testo"]
    assert doc.componenti[0]["localizzatore_xml"]
    assert "MODIFICAZIONI" in doc.text_content


def test_rettifica_conserva_snapshot_e_fts_contentless_si_ricostruisce():
    conn=sqlite3.connect(":memory:")
    ensure_schema(conn);migra_schema(conn)
    doc=documento();did=insert_document(conn,doc,store_full_text=True)
    insert_articles_and_chunks(conn,did,doc,jsonl_file=io.StringIO(),max_chunk_chars=1800,only_relevant_articles=False)
    aid=conn.execute("SELECT id FROM normative_articles WHERE document_id=?",(did,)).fetchone()[0]
    previous="Art. 1. Corpo precedente con allegato erroneamente accodato."
    conn.execute("UPDATE normative_articles SET article_text=? WHERE id=?",(previous,aid))
    conn.commit();sincronizza_fts(conn)
    conn.execute("BEGIN")
    result=rettifica_da_xml(conn,document_id=did,documento=doc,jsonl_file=io.StringIO(),revisione_parser="partizioni-prova")
    conn.commit()
    assert result["rettificato"] is True
    assert conn.execute("SELECT id FROM normative_articles WHERE document_id=?",(did,)).fetchone()[0]==aid
    snapshot,sha=conn.execute("SELECT snapshot_json,snapshot_sha256 FROM normative_import_history").fetchone()
    assert hashlib.sha256(snapshot.encode()).hexdigest()==sha
    assert json.loads(snapshot)["articoli"][0]["article_text"]==previous
    assert conn.execute("SELECT article_text FROM normative_articles WHERE id=?",(aid,)).fetchone()[0]==doc.articles[0].article_text
    assert conn.execute("SELECT COUNT(*) FROM normative_components WHERE document_id=?",(did,)).fetchone()[0]==1
    # Non tentare DELETE SQL sulla tabella FTS5 contentless.
    synced=sincronizza_fts(conn,ricostruisci=True)
    assert synced.orfani==0
    assert conn.execute("SELECT COUNT(*) FROM normative_fts_info").fetchone()[0]==conn.execute("SELECT COUNT(*) FROM normative_chunks").fetchone()[0]


def test_importazione_conserva_localizzatori_e_non_si_risegmenta_di_notte(tmp_path):
    from lex.normativa.riallinea_articoli import riallinea

    path = tmp_path / "normattiva.sqlite"
    doc = documento()
    assert doc.articles[0].localizzatore_xml
    with sqlite3.connect(path) as conn:
        ensure_schema(conn)
        migra_schema(conn)
        did = insert_document(conn, doc, store_full_text=True)
        insert_articles_and_chunks(conn, did, doc, jsonl_file=io.StringIO(), max_chunk_chars=1800,
                                   only_relevant_articles=False)
        metadata = json.loads(conn.execute("SELECT metadata_json FROM normative_chunks WHERE article_id IS NOT NULL").fetchone()[0])
        assert metadata["localizzatore_xml"] == doc.articles[0].localizzatore_xml
        assert metadata["partizione_xml"] == doc.articles[0].partizione
        before = conn.execute("SELECT id, article_number, article_text FROM normative_articles").fetchall()
    result = riallinea(path)
    assert result.documenti_fonti_preservate == 1
    assert result.documenti_riallineati == 0
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT id, article_number, article_text FROM normative_articles").fetchall() == before
        assert conn.execute("SELECT count(*) FROM normative_components").fetchone()[0] == 1
