import io
import sqlite3
from contextlib import closing

import pytest

from lex.normativa import cerdef_biblioteca
from lex.normativa.normattiva_importer import (
    ArticleRecord,
    DocumentRecord,
    ensure_schema,
    insert_articles_and_chunks,
    insert_document,
)


@pytest.fixture
def linked_database(tmp_path, monkeypatch):
    database = tmp_path / "normattiva.sqlite"
    index = tmp_path / "collegamenti.sqlite"
    documents = []
    with closing(sqlite3.connect(database)) as connection:
        ensure_schema(connection)
        for number in (1, 2):
            body = f"Art. 1. Contenuto originale verificabile del provvedimento numero {number}."
            document = DocumentRecord(
                collection_name="Normattiva",
                zip_path="",
                xml_entry=f"LEGGE_20200102_{number}/originale.xml",
                tipo_atto="legge",
                numero=str(number),
                data_atto="2020-01-02",
                data_pubblicazione="2020-01-03",
                titolo=f"Provvedimento numero {number}",
                urn=f"urn:nir:stato:legge:2020-01-02;{number}",
                redazione_id="2020-01-03",
                vigenza="ORIGINALE",
                xml_sha256=str(number) * 64,
                text_content=body,
                topics=[],
                relevance_score=1,
                is_relevant=True,
                articles=[ArticleRecord("1", "Disposizioni", body, [], 1)],
            )
            document_id = insert_document(connection, document, store_full_text=True)
            insert_articles_and_chunks(
                connection,
                document_id,
                document,
                jsonl_file=io.StringIO(),
                max_chunk_chars=1800,
                only_relevant_articles=False,
            )
            documents.append((document_id, document))
        connection.commit()
    with sqlite3.connect(index) as connection:
        connection.execute(
            "CREATE TABLE atti(document_id INTEGER PRIMARY KEY, sha256 TEXT, "
            "cerdef_id TEXT UNIQUE, tipo TEXT, articoli INTEGER)"
        )
        connection.executemany(
            "INSERT INTO atti VALUES (?, ?, ?, ?, ?)",
            [(ident, doc.xml_sha256, f"fonte-{ident}", "legge", 1) for ident, doc in documents],
        )
    monkeypatch.setattr(cerdef_biblioteca, "runtime_general_path", lambda: database)
    monkeypatch.setenv("IUSENTRA_BIBLIOTECA_CERDEF_INDICE", str(index))
    monkeypatch.delenv("IUSENTRA_BIBLIOTECA_CERDEF_INDICE_ARCHIVIO", raising=False)
    return database, index, documents


def test_indice_precedente_resta_consultabile(linked_database):
    _, _, documents = linked_database
    assert {item["id"] for item in cerdef_biblioteca.linked_catalogue()} == {
        cerdef_biblioteca.ID_BASE + ident for ident, _ in documents
    }


def test_edizione_sostituita_scompare_solo_dal_catalogo(linked_database):
    _, index, documents = linked_database
    previous, document = documents[0]
    with sqlite3.connect(index) as connection:
        connection.execute("CREATE TABLE catalogo_sostituito(document_id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO catalogo_sostituito VALUES (?)", (previous,))

    items = cerdef_biblioteca.linked_catalogue()
    assert [item["id"] for item in items] == [cerdef_biblioteca.ID_BASE + documents[1][0]]
    articles = cerdef_biblioteca.linked_articles(cerdef_biblioteca.ID_BASE + previous)
    assert articles["total"] == 1
    article = cerdef_biblioteca.linked_article(articles["items"][0]["id"])
    assert article["text"] == document.articles[0].article_text


def test_sostituzione_estranea_non_nasconde_altri_atti(linked_database):
    _, index, _ = linked_database
    with sqlite3.connect(index) as connection:
        connection.execute("CREATE TABLE catalogo_sostituito(document_id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO catalogo_sostituito VALUES (999999)")
    assert len(cerdef_biblioteca.linked_catalogue()) == 2


def test_sha_discordante_non_risolve_un_altro_documento(linked_database):
    database, _, documents = linked_database
    ident, _ = documents[0]
    with sqlite3.connect(database) as connection:
        article_id = connection.execute(
            "SELECT id FROM normative_articles WHERE document_id=?", (ident,)
        ).fetchone()[0]
        connection.execute("UPDATE normative_documents SET xml_sha256=? WHERE id=?", ("f" * 64, ident))
    assert len(cerdef_biblioteca.linked_catalogue()) == 1
    assert cerdef_biblioteca.linked_article(cerdef_biblioteca.ID_BASE + article_id) is None


def test_avviso_abrogazione_non_promette_testo_storico(linked_database):
    _, index, documents = linked_database
    ident, _ = documents[0]
    with sqlite3.connect(index) as connection:
        connection.execute("CREATE TABLE catalogo_avvisi(document_id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO catalogo_avvisi VALUES (?)", (ident,))
    items = {row["id"]: row for row in cerdef_biblioteca.linked_catalogue()}
    assert "avviso di abrogazione; testo storico non incluso" in items[cerdef_biblioteca.ID_BASE + ident]["title"]
    assert "avviso di abrogazione" not in items[cerdef_biblioteca.ID_BASE + documents[1][0]]["title"]


def test_ricerca_storica_continua_dal_secondo_archivio(monkeypatch):
    from lex.normativa import cerdef_biblioteca, consultazione

    monkeypatch.setattr(cerdef_biblioteca, "alias_originali_storici", lambda: {75: 4000000000001})
    sources = {10**12: [101], 2*10**12: [201, 202], 4*10**12: [401]}

    def native(database, *, escludi_atti, offset, limit, **filters):
        assert escludi_atti == (75,)
        return {"total": 2, "items": [1, 2][offset:offset+limit]}

    def linked(identifier, *, archive_base, offset, limit, **filters):
        assert identifier == 0
        values = sources[archive_base]
        return {"total": len(values), "items": values[offset:offset+limit]}

    monkeypatch.setattr(consultazione, "articoli", native)
    monkeypatch.setattr(cerdef_biblioteca, "linked_articles", linked)
    result = cerdef_biblioteca.ricerca_storica(None, query="convenzione", offset=3)
    assert result == {"items": [201, 202, 401], "total": 6, "act_id": 0}


def test_catalogo_salvato_riusa_la_stessa_revisione(tmp_path, monkeypatch, linked_database):
    from lex.normativa import cerdef_catalogo_salvato as salvato

    _, index, documents = linked_database
    edizioni = (cerdef_biblioteca.ID_BASE,)
    prima = salvato.catalogo_cerdef_salvato(tmp_path, edizioni, prepara=True)
    assert len(prima) == len(documents)
    with monkeypatch.context() as patch:
        def no_scan(*args, **kwargs):
            raise AssertionError("Il catalogo della stessa revisione è già disponibile.")

        patch.setattr(salvato, "_catalogue", no_scan)
        assert salvato.catalogo_cerdef_salvato(tmp_path, edizioni, prepara=True) == prima

    with sqlite3.connect(index) as connection:
        connection.execute("DELETE FROM atti WHERE document_id=?", (documents[0][0],))
    nuova = salvato.catalogo_cerdef_salvato(tmp_path, edizioni, prepara=True)
    assert [atto["id"] for atto in nuova] == [cerdef_biblioteca.ID_BASE + documents[1][0]]
