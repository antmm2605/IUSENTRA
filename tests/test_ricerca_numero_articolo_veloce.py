"""Codici e leggi: la ricerca del numero d'articolo su «Tutti gli atti» non scorre i testi.

Collaudo del 21/11/2026: sui testi vigenti (126.664 articoli, 1,9 GB) la ricerca
dell'art. 2043 senza atto superava i 240 secondi e bloccava un thread del server.
"""
import io
import sqlite3
import time
from contextlib import closing

import pytest

from lex import tempo_ricerca
from lex.normativa import cerdef_biblioteca
from lex.normativa.biblioteca.identita import filtro_numero_articolo
from lex.ricerca_giuridica.indice_fts import sincronizza_fts
from lex.normativa.normattiva_importer import (
    ArticleRecord,
    DocumentRecord,
    ensure_schema,
    insert_articles_and_chunks,
    insert_document,
)


def _archivio(tmp_path, *, atti=3, articoli=40, indice=True):
    database = tmp_path / "normattiva.sqlite"
    index = tmp_path / "indice.sqlite"
    documenti = []
    with closing(sqlite3.connect(database)) as connection:
        ensure_schema(connection)
        for numero in range(1, atti + 1):
            records = [ArticleRecord(f"Art. {n}.", f"Rubrica {n}", f"Art. {n}. Testo dell'articolo {n} dell'atto {numero}.", [], 1)
                       for n in range(1, articoli + 1)]
            document = DocumentRecord(
                collection_name="Normattiva", zip_path="", xml_entry=f"LEGGE_2020_{numero}/v.xml", tipo_atto="legge",
                numero=str(numero), data_atto="2020-01-02", data_pubblicazione="2020-01-03",
                titolo=f"Legge numero {numero}", urn=f"urn:nir:stato:legge:2020-01-02;{numero}", redazione_id="2020-01-03",
                vigenza="VIGENTE", xml_sha256=f"{numero:064d}", text_content="testo", topics=[], relevance_score=1,
                is_relevant=True, articles=records,
            )
            ident = insert_document(connection, document, store_full_text=True)
            insert_articles_and_chunks(connection, ident, document, jsonl_file=io.StringIO(), max_chunk_chars=1800,
                                       only_relevant_articles=False)
            documenti.append((ident, document))
        sincronizza_fts(connection)
        if indice:
            connection.execute("CREATE INDEX idx_consultazione_doc_article ON normative_articles(document_id, article_number)")
        connection.commit()
    with closing(sqlite3.connect(index)) as connection:
        connection.execute("CREATE TABLE atti(document_id INTEGER PRIMARY KEY, sha256 TEXT, cerdef_id TEXT UNIQUE, tipo TEXT, articoli INTEGER)")
        connection.executemany("INSERT INTO atti VALUES (?,?,?,?,?)",
                               [(i, d.xml_sha256, f"f-{i}", "legge", articoli) for i, d in documenti])
        connection.commit()
    return database, index


@pytest.fixture
def vigente(tmp_path, monkeypatch):
    database, index = _archivio(tmp_path)
    monkeypatch.setenv("IUSENTRA_BIBLIOTECA_VIGENTE_DB", str(database))
    monkeypatch.setenv("IUSENTRA_BIBLIOTECA_VIGENTE_INDICE", str(index))
    return database, index


def test_numero_su_tutti_gli_atti_passa_dall_indice(vigente):
    database, _ = vigente
    with closing(sqlite3.connect(database)) as connection:
        condizione = filtro_numero_articolo(connection)
        piano = " ".join(r[3] for r in connection.execute(
            "EXPLAIN QUERY PLAN SELECT a.id FROM normative_articles a WHERE length(a.article_text)>0 AND " + condizione, ("12",)))
    assert "COVERING INDEX idx_consultazione_doc_article" in piano
    assert "SCAN a" not in piano  # i testi non si leggono più tutti


def test_risultati_uguali_e_veloci(vigente):
    inizio = time.monotonic()
    risultato = cerdef_biblioteca.linked_articles(0, article="art. 12", vigente=True)
    assert time.monotonic() - inizio < 2
    assert risultato["total"] == 3
    assert {item["number"] for item in risultato["items"]} == {"12"}


def test_conteggio_limitato(vigente, monkeypatch):
    monkeypatch.setattr(cerdef_biblioteca, "LIMITE_CONTEGGIO", 50)
    risultato = cerdef_biblioteca.linked_articles(0, query="testo", vigente=True)
    assert risultato["total"] == 50 and risultato["total_oltre"] is True


def test_senza_indice_resta_corretto(tmp_path, monkeypatch):
    database, index = _archivio(tmp_path, indice=False)
    monkeypatch.setenv("IUSENTRA_BIBLIOTECA_VIGENTE_DB", str(database))
    monkeypatch.setenv("IUSENTRA_BIBLIOTECA_VIGENTE_INDICE", str(index))
    assert cerdef_biblioteca.linked_articles(0, article="7", vigente=True)["total"] == 3


def test_tempo_massimo_interrompe_con_messaggio_chiaro(vigente, monkeypatch):
    monkeypatch.setattr(tempo_ricerca, "_PASSO", 1)
    with tempo_ricerca.scadenza(0.000001):
        time.sleep(0.01)
        with pytest.raises(tempo_ricerca.RicercaTroppoLunga) as errore:
            cerdef_biblioteca.linked_articles(0, query="testo", vigente=True)
    assert "tempo massimo" in str(errore.value)
    assert not isinstance(errore.value, OSError)
