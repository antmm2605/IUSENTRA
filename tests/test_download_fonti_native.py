import hashlib
import importlib

import pytest
from flask import Flask, g, request

module = importlib.import_module("web.blueprints.legal_intelligence")


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(module.legal_intelligence)
    app.add_url_rule("/login", "login", lambda: "login")
    @app.before_request
    def identity():
        g.utente_corrente = {"id": "reader"} if request.headers.get("X-Test-User") else None
    def no_daily():
        raise AssertionError("Native identity must never fall back to monitor snapshots")
    monkeypatch.setattr(module, "_daily_engine", no_daily)
    return app.test_client()


def test_native_article_exports_actual_body_and_digest(client, monkeypatch):
    from lex.retrieval import normativa_catalog
    text = "Art. 2043. Testo archiviato verificato. " * 80
    monkeypatch.setattr(normativa_catalog, "leggi_chunk_archiviato", lambda key: {
        "titolo": "Codice civile", "normative_full_text": text, "url_origine": "urn:nir:prova"})
    response = client.get("/legal-intelligence/fonte/normattiva:stable:art2043:chunk1/scarica", headers={"X-Test-User": "yes"})
    assert response.status_code == 200 and response.mimetype == "text/plain"
    assert response.get_data(as_text=True).endswith(text)
    assert hashlib.sha256(text.encode()).hexdigest() in response.get_data(as_text=True)
    assert "attachment" in response.headers["Content-Disposition"]
    assert "no-store" in response.headers["Cache-Control"]


def test_missing_and_ambiguous_native_article_never_export_monitor_html(client, monkeypatch):
    from lex.retrieval import normativa_catalog
    monkeypatch.setattr(normativa_catalog, "leggi_chunk_archiviato", lambda key: None)
    url = "/legal-intelligence/fonte/normattiva:missing/scarica"
    assert client.get(url, headers={"X-Test-User": "yes"}).status_code == 404
    def ambiguous(key):
        raise normativa_catalog.NormativaIndexUnavailable("different owner identity")
    monkeypatch.setattr(normativa_catalog, "leggi_chunk_archiviato", ambiguous)
    assert client.get(url, headers={"X-Test-User": "yes"}).status_code == 409
    assert client.get(url).status_code == 302


def test_shared_download_resolves_public_native_case(client, tmp_path, monkeypatch):
    from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
    manager = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    body = "Decisione civile di prova archiviata. " * 80
    case = manager.salva_sentenza({"uuid_interno": "shared-download", "fonte_codice": "cassazione_sentenzeweb",
        "fonte_nome": "SentenzeWeb", "organo_giudicante": "Corte di Cassazione", "titolo": "26870/2026",
        "numero_sentenza": "26870", "anno_sentenza": 2026, "testo_integrale": body})
    monkeypatch.setenv("IUSENTRA_SENTENZEWEB_DIRECTORY", str(tmp_path))
    response = client.get(f"/legal-intelligence/fonte/sentenzeweb:{case['id']}/scarica", headers={"X-Test-User": "yes"})
    assert response.status_code == 200 and response.mimetype == "text/plain"
    assert response.get_data(as_text=True).endswith(body.strip())
