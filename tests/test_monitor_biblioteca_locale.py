import sqlite3

from web.services import react_legal_intelligence_bridge as bridge


def test_catalogo_esistente_non_simula_aggiornamenti(monkeypatch, tmp_path):
    from lex.normativa import consultazione
    from lex.retrieval import normativa_catalog
    db = tmp_path / "codici_leggi.sqlite"
    db.touch()
    monkeypatch.setattr(normativa_catalog, "library_path", lambda general: db)
    observed = []
    def catalogo(path):
        observed.append(path)
        return [{"key": "codice_civile", "articles": 3249}]
    monkeypatch.setattr(consultazione, "catalogo", catalogo)
    monitor = {"sources_ready": 0, "sources_not_ready": 1,
               "sources": [{"source_code": "codice_civile", "status": "non_pronta",
                            "reason": "Nessuna acquisizione aggiornamenti.", "review_published": 0}]}
    result = bridge._monitor_biblioteca_locale(monitor, {"NORMATTIVA_DB": str(tmp_path / "normattiva.sqlite")})
    assert observed == [db]
    assert result["local_library"] == {"status": "catalogo_disponibile", "acts": 1, "articles": 3249}
    assert result["sources"][0]["local_articles"] == 3249
    assert "Biblioteca locale" in result["sources"][0]["reason"]
    assert result["sources_ready"] == 0
    assert result["sources"][0]["status"] == "non_pronta"
    assert result["sources"][0]["review_published"] == 0
    assert "local_articles" not in monitor["sources"][0]


def test_archivio_non_leggibile_non_diventa_disponibile(monkeypatch, tmp_path):
    from lex.normativa import consultazione
    def unavailable(path):
        raise sqlite3.DatabaseError("invalid")
    monkeypatch.setattr(consultazione, "catalogo", unavailable)
    result = bridge._monitor_biblioteca_locale({"sources_ready": 0, "sources": []},
                                              {"NORMATTIVA_DB": str(tmp_path / "absent.sqlite")})
    assert result["local_library"]["status"] == "non_disponibile"
    assert result["local_library"]["acts"] == 0
    assert result["sources_ready"] == 0


def test_scheda_configurata_non_prova_acquisizione():
    monitor = {"sources": [{"source_code": "codice_civile", "enabled": True,
                             "status": "non_pronta", "local_articles": 3249,
                             "reason": "Biblioteca locale disponibile; aggiornamenti assenti."}]}
    audit = {"sources": [{"source_id": "codice_civile", "official": True,
                          "delivery_status": "operativa_controllabile", "registry": "legal_update_sources"}]}
    result = bridge._enrich_autofetch_monitor_for_lawyer(monitor, audit)
    row = result["sources"][0]
    assert row["delivery_status_label"] == "Biblioteca locale disponibile; aggiornamenti da verificare"
    assert "pubblicata" not in row["delivery_status_label"]
    assert row["system_action"] == monitor["sources"][0]["reason"]


def test_stesso_catalogo_per_api_monitor_e_giurisprudenza(tmp_path, monkeypatch):
    import hashlib
    from flask import Flask
    from lex.normativa.consultazione import importa_fonti
    from lex.retrieval.normativa_catalog import library_catalog_snapshot
    from tests.test_normative_consultation import source
    from web.blueprints.api_v1_ricerca_legale import _normativa_db
    from web.services.lex_studio_knowledge_status import build_official_archive_section

    package, _ = source(tmp_path)
    db = tmp_path / "codici_leggi.sqlite"
    importa_fonti(package, db, "2026-10-07")  # Synthetic fixture, matching requested edition.
    monkeypatch.setenv("PCT_CODICI_LEGGI_DB", str(db))
    app = Flask(__name__)
    app.config["NORMATTIVA_DB"] = str(tmp_path / "general-absent.sqlite")
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    with app.app_context():
        assert _normativa_db() == db
        snapshot = library_catalog_snapshot()
        monitor = bridge._monitor_biblioteca_locale({"sources": []}, app.config)
        section = build_official_archive_section()
    library = next(item for item in section["items"] if item["id"] == "biblioteca_codici_leggi")
    assert snapshot["acts"] == monitor["local_library"]["acts"] == library["value"] == 1
    assert snapshot["articles"] == monitor["local_library"]["articles"] == 1
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert not (tmp_path / "general-absent.sqlite").exists()
