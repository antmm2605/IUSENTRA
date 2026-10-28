import hashlib
import sqlite3

import pytest

from lex.normativa.biblioteca.lettura import leggi_articoli


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "biblioteca.sqlite"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE normative_documents(id INTEGER,collection_name TEXT,urn TEXT,redazione_id TEXT,vigenza TEXT,xml_sha256 TEXT,xml_entry TEXT)")
        c.execute("CREATE TABLE normative_articles(id INTEGER,document_id INTEGER,article_number TEXT,article_text TEXT)")
        for ident, key in [(1, "codice_procedura_penale"), (2, "reg_ue_2016_679")]:
            c.execute("INSERT INTO normative_documents VALUES(?,?,?,?,?,?,?)",(ident,"Lex fonti: "+key,"urn:fixture","2026-10-24","EDIZIONE_ACQUISITA","a"*64,"fixture.jsonl"))
        c.execute("INSERT INTO normative_articles VALUES(1,1,'5','Testo penale non giuridico.')")
        c.execute("INSERT INTO normative_articles VALUES(2,2,'5',?)",("Testo UE non giuridico. "*2000,))
        c.execute("INSERT INTO normative_articles VALUES(3,1,'473-bis.12','Testo bis non giuridico.')")
    return path


def test_read_full_text_correct_act_and_source_fingerprint(db):
    r = leggi_articoli(db,[{"chiave":"reg_ue_2016_679","articolo":"5"}])
    source = r["articoli"][0]
    assert len(source["testo"]) > 40000
    assert source["sha256_testo"] == hashlib.sha256(source["testo"].encode()).hexdigest()
    assert source["document_id"] == 2
    assert source["applicabilita_al_fascicolo"] == "da_verificare"
    assert r["lettura_completa"] and not r["fonti_approvate_per_il_fascicolo"]


def test_no_guessing_other_act_missing_article_or_editions(db):
    r = leggi_articoli(db,[{"chiave":"reg_ue_2016_679","articolo":"473bis.12"}])
    assert not r["articoli"] and not r["lettura_completa"]
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO normative_documents VALUES(3,'Lex fonti: codice_procedura_penale','urn:fixture','2025-01-01','EDIZIONE_ACQUISITA','b','fixture.jsonl')")
    assert not leggi_articoli(db,[{"chiave":"codice_procedura_penale","articolo":"5"}])["lettura_completa"]
    assert leggi_articoli(db,[{"chiave":"codice_procedura_penale","articolo":"5","edizione":"2026-10-24"}])["lettura_completa"]


def test_bis_and_changed_hash_are_not_silently_substituted(db):
    r = leggi_articoli(db,[{"chiave":"codice_procedura_penale","articolo":"473bis.12"}])
    assert r["articoli"][0]["articolo"] == "473-bis.12"
    r = leggi_articoli(db,[{"chiave":"codice_procedura_penale","articolo":"5","sha256_atteso":"0"*64}])
    assert not r["articoli"] and r["errori"][0]["motivo"] == "Impronta del testo cambiata"


def test_read_only_and_invalid_identity(db):
    before = db.read_bytes()
    leggi_articoli(db,[{"chiave":"codice_procedura_penale","articolo":"5"}])
    assert db.read_bytes() == before
    with pytest.raises(ValueError):
        leggi_articoli(db,[{"chiave":"../../altra-cartella","articolo":"5"}])
