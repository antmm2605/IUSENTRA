import sqlite3

import pytest

from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from web.services.sentenzeweb_runtime import read_text, search


def prepare(tmp_path, source="cassazione_sentenzeweb"):
    path = tmp_path / "giurisprudenza_corpus.db"
    corpus = GestioneCorpusGiurisprudenza(str(path))
    record = corpus.salva_sentenza(
        {
            "uuid_interno": "public-case-1",
            "fonte_codice": source,
            "fonte_nome": "Fonte di prova",
            "tipo_fonte": "ufficiale",
            "organo_giudicante": "Corte di Cassazione — civile",
            "numero_sentenza": "26870",
            "anno_sentenza": 2026,
            "sezione": "2",
            "tipo_provvedimento": "ordinanza",
            "titolo": "Cassazione 26870/2026",
            "testo_integrale": "Testo completo verificabile. " * 80,
        }
    )
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sentenzeweb_progress(seen INTEGER,expected INTEGER,status TEXT,id INTEGER)")
        connection.execute("INSERT INTO sentenzeweb_progress VALUES(1,2,'running',1)")
    return {"IUSENTRA_SENTENZEWEB_DIRECTORY": str(tmp_path)}, record["id"]


def test_shared_corpus_search_and_entire_text_are_readonly(tmp_path):
    config, record_id = prepare(tmp_path)
    response = search(config, "26870/2026")
    assert response["available"] and response["received"] == 1 and response["expected"] == 2
    assert response["status"] == "running"
    assert response["caseCount"] == 1 and response["records"][0]["id"] == record_id
    assert read_text(config, record_id) == " ".join(("Testo completo verificabile. " * 80).split())
    assert read_text(config, 999999) == ""


def test_nonpublic_owner_cannot_be_exposed_as_shared_archive(tmp_path):
    config, _ = prepare(tmp_path, "manuale_interno")
    with pytest.raises(ValueError, match="public owner"):
        search(config)


def test_unconfigured_does_not_create_archive(tmp_path, monkeypatch):
    monkeypatch.delenv("IUSENTRA_SENTENZEWEB_DIRECTORY", raising=False)
    assert search({})["available"] is False
    assert not list(tmp_path.iterdir())


def test_unbounded_query_is_rejected(tmp_path):
    config, _ = prepare(tmp_path)
    with pytest.raises(ValueError, match="long"):
        search(config, "x" * 501)


def test_native_giurisprudenza_owner_includes_shared_hits_with_scoped_ids(tmp_path, monkeypatch):
    from pct.giurisprudenza import GestioneGiurisprudenza

    public = tmp_path / "public"
    public.mkdir()
    config, shared_id = prepare(public)
    monkeypatch.setenv("IUSENTRA_SENTENZEWEB_DIRECTORY", config["IUSENTRA_SENTENZEWEB_DIRECTORY"])
    manager = GestioneGiurisprudenza(str(tmp_path / "private" / "giurisprudenza.json"))
    rows = manager.cerca_corpus_professionale(q="26870/2026")
    hit = next(row for row in rows if row["id"] == f"sentenzeweb:{shared_id}")
    assert hit["shared_public_corpus"] and hit["text"].startswith("Testo completo")
    assert hit["stored_text_href"] == f"/giurisprudenza/sentenzeweb/{shared_id}/testo"
    assert manager.scheda_corpus_professionale(hit["id"])["numero_sentenza"] == "26870"
    assert manager._corpus.storage_stats()["sentenze"] == 0
    assert not manager.riferimento_professionale_verificato(hit["id"])


def test_source_document_cannot_be_read_through_another_case(tmp_path):
    from web.services.sentenzeweb_runtime import read_variant, variants

    config, case_id = prepare(tmp_path)
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    record = corpus.get_sentenza(case_id)
    record["documenti"] = [
        {
            "tipo_documento": "testo_plain",
            "titolo": "Originale",
            "testo_estratto": "Testo variante",
            "sha256": "a" * 64,
            "scaricato": True,
        }
    ]
    corpus.salva_sentenza(record)
    documents = variants(config, case_id)["documents"]
    assert len(documents) == 1
    assert read_variant(config, case_id, documents[0]["id"]) == "Testo variante"
    assert read_variant(config, case_id + 9999, documents[0]["id"]) == ""


def test_legacy_cassazione_sync_does_not_import_a_portal_as_a_decision(tmp_path, monkeypatch):
    from pct.giurisprudenza import GestioneGiurisprudenza

    public = tmp_path / "public"
    public.mkdir()
    config, _ = prepare(public)
    monkeypatch.setenv("IUSENTRA_SENTENZEWEB_DIRECTORY", config["IUSENTRA_SENTENZEWEB_DIRECTORY"])
    manager = GestioneGiurisprudenza(str(tmp_path / "study" / "giurisprudenza.json"))

    def forbidden(*args, **kwargs):
        raise AssertionError("The legacy source scraper must not fetch a portal or duplicate history")

    result = manager.sync_sources(source_ids=["cassazione"], request_get=forbidden)
    assert result["imported_total"] == 0
    assert result["runs"][0]["status"] == "archivio_condiviso"
    assert manager.cerca() == []


def test_global_legal_search_uses_the_same_downloaded_shared_owner(tmp_path, monkeypatch):
    from web.services import react_legal_intelligence_bridge as bridge
    config, shared_id = prepare(tmp_path)
    monkeypatch.setenv("IUSENTRA_SENTENZEWEB_DIRECTORY", config["IUSENTRA_SENTENZEWEB_DIRECTORY"])
    from flask import Flask
    with Flask(__name__).app_context():
        rows = bridge._official_archive_records([], "26870/2026")
    hit = next(row for row in rows if row["id"] == f"sentenzeweb:{shared_id}")
    assert hit["kind"] == "giurisprudenza"
    assert "Testo completo verificabile" in str(hit)


def test_initial_list_is_bounded_and_does_not_run_relevance_search(tmp_path, monkeypatch):
    config, record_id = prepare(tmp_path)
    def no_full_search(*args, **kwargs):
        raise AssertionError("Initial listing must not sort the entire corpus by relevance")
    monkeypatch.setattr(GestioneCorpusGiurisprudenza, "cerca_sentenze", no_full_search)
    result = search(config)
    assert result["available"] and len(result["records"]) == 1
    assert result["records"][0]["id"] == record_id
