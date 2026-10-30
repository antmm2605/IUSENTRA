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


def test_legacy_redaction_notice_never_becomes_readable_decision(tmp_path):
    from pct.sentenzeweb_corpus import PublicSentenzeWebCorpus
    from web.services.sentenzeweb_runtime import read_variant, variants

    config, case_id = prepare(tmp_path)
    notice = "!CORTE SUPREMA DI CASSAZIONE ITALGIUREWEB La sentenza richiesta è in fase di oscuramentoI"
    owner = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    record = owner.get_sentenza(case_id)
    record.update(testo_integrale=notice, testo_integrale_presente=True,
                  stato_verifica="parzialmente_verificata", fonte_ufficiale_confermata=True,
                  url_pagina_ufficiale="https://www.italgiure.giustizia.it/sncass/")
    record["documenti"] = [{"tipo_documento": "testo_plain", "titolo": "Avviso originale",
        "testo_estratto": notice, "ufficiale": True, "scaricato": True,
        "sha256": "a" * 64, "url_origine": "https://www.italgiure.giustizia.it/sncass/"}]
    owner.salva_sentenza(record)
    response = search(config, "26870/2026")
    assert response["records"][0]["textAvailable"] is False
    assert response["records"][0]["textStatus"] == "source_notice"
    assert read_text(config, case_id) == ""
    public = PublicSentenzeWebCorpus(tmp_path / "giurisprudenza_corpus.db")
    guarded = public.get_sentenza(case_id)
    assert not public.can_cite_sentenza(guarded)
    document = variants(config, case_id)["documents"][0]
    assert document["textStatus"] == "source_notice" and document["official"] is True
    assert read_variant(config, case_id, document["id"]) == notice
    assert owner.get_sentenza(case_id)["testo_integrale"] == notice  # original preserved


def test_alternative_transcription_keeps_explicit_nonofficial_provenance(tmp_path):
    from web.services.sentenzeweb_runtime import variants

    config, case_id = prepare(tmp_path)
    owner = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    record = owner.get_sentenza(case_id)
    record["documenti"] = [{"tipo_documento": "testo_plain", "titolo": "Trascrizione pubblicata",
        "testo_estratto": "P.Q.M. Rigetta il ricorso.", "ufficiale": False,
        "sha256": "b" * 64, "url_origine": "https://www.misterlex.it/cassazione-civile/2026/26870/"}]
    owner.salva_sentenza(record)
    document = variants(config, case_id)["documents"][0]
    assert document["official"] is False
    assert document["textStatus"] == "content_unreviewed"
    assert document["sourceUrl"] == "https://www.misterlex.it/cassazione-civile/2026/26870/"


@pytest.mark.parametrize('query', ['30750/2021', 'n. 30750/2021', '99999/2021'])
def test_exact_reference_excludes_other_years_and_does_not_query_fts(tmp_path, query):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / 'corpus.db'))
    for year in [2021, 2022]:
        corpus.salva_sentenza({'uuid_interno':f'case-{year}', 'fonte_codice':'cassazione_sentenzeweb', 'fonte_nome':'Fonte sintetica', 'tipo_fonte':'ufficiale', 'organo_giudicante':'Corte di Cassazione', 'numero_sentenza':'30750', 'anno_sentenza':year, 'titolo':f'Cassazione 30750/{year}', 'testo_integrale':'Testo sintetico 30750 2021 2022.'})
    original = corpus._connect
    statements = []
    def traced():
        connection = original()
        connection.set_trace_callback(statements.append)
        return connection
    corpus._connect = traced
    rows = corpus.cerca_sentenze(q=query, semantica=False)
    assert [r['anno_sentenza'] for r in rows] == ([] if query.startswith('99999') else [2021])
    assert not any(' MATCH ' in sql for sql in statements)

def test_exact_reference_keeps_filters_and_disables_semantic_fallback(tmp_path, monkeypatch):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / 'corpus.db'))
    corpus.salva_sentenza({'uuid_interno':'exact', 'fonte_codice':'cassazione_sentenzeweb', 'fonte_nome':'Sintetica', 'tipo_fonte':'ufficiale', 'organo_giudicante':'Corte di Cassazione', 'numero_sentenza':'30750', 'anno_sentenza':2021, 'titolo':'Decisione', 'testo_integrale':'Testo sintetico.'})
    def forbidden(**kwargs):
        raise AssertionError('La ricerca esatta non deve attivare embedding')
    monkeypatch.setattr(corpus,'cerca_sentenze_ibrida',forbidden)
    assert corpus.cerca_sentenze(q='30750/2021',organo_giudicante='Altro organo',semantica=True)==[]
    assert corpus.cerca_sentenze(q='30750/2021',solo_con_pdf=True,semantica=True)==[]
    assert len(corpus.cerca_sentenze(q='30750/2021',semantica=True))==1

def test_thematic_query_still_uses_full_text(tmp_path):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / 'corpus.db'))
    corpus.salva_sentenza({'uuid_interno':'topic', 'fonte_codice':'cassazione_sentenzeweb', 'fonte_nome':'Sintetica', 'tipo_fonte':'ufficiale', 'organo_giudicante':'Corte di Cassazione', 'numero_sentenza':'10', 'anno_sentenza':2021, 'titolo':'Restituzione delle spese', 'testo_integrale':'Restituzione spese difensore distrattario.'})
    assert len(corpus.cerca_sentenze(q='restituzione spese',semantica=False))==1

def test_exact_ecli_never_returns_a_different_identity(tmp_path):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / 'corpus.db'))
    for number in ['10','11']:
        corpus.salva_sentenza({'uuid_interno':'ecli-'+number, 'fonte_codice':'cassazione_sentenzeweb', 'fonte_nome':'Sintetica', 'tipo_fonte':'ufficiale', 'organo_giudicante':'Corte di Cassazione', 'numero_sentenza':number, 'anno_sentenza':2021, 'ecli':f'ECLI:IT:CASS:2021:{number}', 'titolo':'Restituzione spese', 'testo_integrale':'Testo sintetico ECLI IT CASS 2021.'})
    rows=corpus.cerca_sentenze(q='ecli:it:cass:2021:10',semantica=True)
    assert len(rows)==1 and rows[0]['numero_sentenza']=='10'
    assert corpus.cerca_sentenze(q='ECLI:IT:CASS:2021:999',semantica=True)==[]
