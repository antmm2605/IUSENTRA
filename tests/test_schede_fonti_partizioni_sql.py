"""La scheda non può scegliere il primo articolo fra partizioni omonime."""
import sqlite3
import json
from datetime import date
from lex.normativa.normattiva_importer import ensure_schema, migra_schema
from types import SimpleNamespace

from pct.schede_fonti.verifica import verifica_schede


def _archivio(tmp_path, monkeypatch, duplicato):
    p = tmp_path / "biblioteca.sqlite"
    with sqlite3.connect(p) as c:
        ensure_schema(c)
        migra_schema(c)
        c.execute("INSERT INTO normative_documents(id,collection_name,redazione_id,urn,xml_sha256,imported_at,zip_path,xml_entry) VALUES(1,?,?,?,?,?,?,?)",
                  ("Lex fonti: codice_civile","2026-10-26","urn:nir:stato:regio.decreto:1942-03-16;262","a"*64,"2026-10-26 08:00:00","fonte.zip","atto.xml"))
        c.execute("INSERT INTO normative_articles(id,document_id,article_number,article_text) VALUES(10,1,'1',?)",
                  ("La capacità giuridica si acquista dal momento della nascita secondo le disposizioni del codice civile.",))
        if duplicato:
            c.execute("INSERT INTO normative_articles(id,document_id,article_number,article_text) VALUES(11,1,'1',?)",
                      ("Le fonti del diritto sono le leggi, i regolamenti e gli usi secondo le disposizioni preliminari.",))
    ref = SimpleNamespace(scheda="ATTO",atto="codice_civile",articolo="1",origine="base",perche="base normativa")
    monkeypatch.setattr("pct.schede_fonti.verifica.riferimenti_schede",lambda *a,**k:[ref])
    return p


def test_rifiuta_due_articoli_con_numero_identico(tmp_path, monkeypatch):
    p = _archivio(tmp_path,monkeypatch,True)
    result = verifica_schede(p)[0]
    assert result.stato == "articolo_ambiguo"
    assert result.testo == ""
    assert result.article_id is None


def test_conserva_identita_del_riscontro_unico(tmp_path, monkeypatch):
    p = _archivio(tmp_path,monkeypatch,False)
    result = verifica_schede(p)[0]
    assert result.stato == "presente"
    assert (result.document_id,result.article_id) == (1,10)
    assert result.sha256


def test_numero_xml_art_punto_e_data_non_inventata(tmp_path, monkeypatch):
    p = _archivio(tmp_path, monkeypatch, False)
    with sqlite3.connect(p) as c:
        c.execute("UPDATE normative_articles SET article_number='Art. 1.'")
    result = verifica_schede(p, alla_data=date(2026, 10, 26))[0]
    assert result.stato == "presente"
    assert result.acquisita_il == ""


def test_ricezione_documentata_prevale_su_import_recente_non_documentato(tmp_path, monkeypatch):
    p = _archivio(tmp_path, monkeypatch, False)
    with sqlite3.connect(p) as c:
        c.execute("UPDATE normative_documents SET redazione_id='2026-10-09', imported_at='2026-10-27'")
        c.execute("INSERT INTO normative_documents(id,collection_name,redazione_id,urn,xml_sha256,imported_at,zip_path,xml_entry) SELECT 2,collection_name,'2023-10-22',urn,'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','2026-10-26',zip_path,xml_entry FROM normative_documents WHERE id=1")
        c.execute("INSERT INTO normative_articles(id,document_id,article_number,article_text) SELECT 20,2,'Art. 1.',article_text FROM normative_articles WHERE id=10")
        md = {"consultazione_provenienza": {"acquisita_utc": "2026-10-26T05:15:52+00:00", "vigenza_richiesta": "2026-10-26", "sha256_payload_ufficiale": "b"*64}}
        c.execute("INSERT INTO normative_chunks(id,document_id,article_id,chunk_key,chunk_text,metadata_json) VALUES(20,2,20,'fixture','testo',?)", (json.dumps(md),))
    result = verifica_schede(p, alla_data=date(2026, 10, 26))[0]
    assert (result.document_id, result.article_id) == (2,20)
    assert result.aggiornato_al == "2023-10-22"
    assert result.acquisita_il == "2026-10-26"


def test_partizione_preleggi_deriva_dal_nome_xml_e_condivide_solo_atto():
    from lex.normativa.biblioteca.riferimenti import fonte_per_chiave, PARTIZIONI_CODICI
    assert fonte_per_chiave("preleggi").urn == fonte_per_chiave("codice_civile").urn
    assert PARTIZIONI_CODICI["preleggi"] == "Disposizioni sulla legge in generale"
    assert PARTIZIONI_CODICI["preleggi"] != PARTIZIONI_CODICI["codice_civile"]


def test_acquisizione_parti_omonime_usa_verificatore_nativo_per_ogni_corpo(monkeypatch):
    from lex.normativa.biblioteca.acquisizione import _versione_con_partizioni
    c=sqlite3.connect(":memory:")
    c.executescript("CREATE TABLE normative_akn_chains(id INTEGER,urn TEXT); CREATE TABLE normative_akn_editions(id INTEGER,chain_id INTEGER,dal TEXT); CREATE TABLE normative_akn_articles(edition_id INTEGER,partizione TEXT);")
    c.execute("INSERT INTO normative_akn_chains VALUES(1,'urn:prova')")
    c.execute("INSERT INTO normative_akn_editions VALUES(1,1,'2026-10-26')")
    c.executemany("INSERT INTO normative_akn_articles VALUES(1,?)", [('corpo_principale',),('Allegato A',)])
    calls=[]
    def native(conn, *, urn, data_riferimento, partizione):
        assert urn=='urn:prova' and data_riferimento=='2026-10-26'
        calls.append(partizione)
        return [] if partizione is None else [{"partizione":partizione,"numero":"Art. 1.","testo":"Verificato dal lettore nativo: "+partizione}]
    monkeypatch.setattr('lex.normativa.versioni_akn.leggi_versione',native)
    rows=_versione_con_partizioni(c,urn='urn:prova',target='2026-10-26',partizione=None)
    assert calls==[None,'Allegato A','corpo_principale']
    assert {x['partizione'] for x in rows}=={'Allegato A','corpo_principale'}
    assert len(rows)==2
