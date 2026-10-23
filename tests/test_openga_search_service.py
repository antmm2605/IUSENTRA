import hashlib

import pytest

from pct.openga_catalogo import CatalogoOpenGA
from pct.openga_search import _SEARCH_LOCK, search_openga
from tests.test_openga_catalogo import risorsa


def test_query_reale_e_fallback_conservano_risultati(tmp_path):
    path, meta = risorsa(tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}])
    db = tmp_path / "catalogo.db"
    CatalogoOpenGA(db).importa(path, meta)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    config = {"OPENGA_CATALOGO_DB": str(db)}
    normal = search_openga({"q": "permesso soggiorno"}, config)
    fallback = search_openga({"q": "permesso soggiorno", "semantica": True}, config)
    assert normal["ok"] and normal["risultati"]
    assert fallback["risultati"] == normal["risultati"]
    assert not fallback["semantic_available"] and fallback["message"]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert normal["evidence_scope"] == "metadata_only"
    assert not {"massima_ufficiale", "principio", "testo_integrale"} & normal["risultati"][0].keys()


@pytest.mark.parametrize("payload", [
    {"q": []}, {"q": " "}, {"q": "x" * 1001}, {"q": "x", "dal": True},
    {"q": "x", "dal": 2026.5}, {"q": "x", "dal": 2026, "al": 2020},
    {"q": "x", "sede": []}, {"q": "x", "semantica": "true"},
])
def test_input_non_validi_senza_avviare_motori(payload):
    with pytest.raises(ValueError):
        search_openga(payload, {})


def test_nessuna_creazione_se_catalogo_assente(tmp_path):
    db = tmp_path / "assente/catalogo.db"
    result = search_openga({"q": "soggiorno"}, {"OPENGA_CATALOGO_DB": str(db)})
    assert not result["ok"] and not db.parent.exists()
    assert str(db) not in str(result)


def test_richiesta_concorrente_non_accoda_inferenze(tmp_path):
    db = tmp_path / "catalogo.db"
    db.touch()
    _SEARCH_LOCK.acquire()
    try:
        result = search_openga({"q": "soggiorno", "semantica": True}, {"OPENGA_CATALOGO_DB": str(db)})
        assert not result["ok"] and "già in corso" in result["message"]
    finally:
        _SEARCH_LOCK.release()


def test_route_reale_richiede_sessione_e_cerca_catalogo(tmp_path, monkeypatch):
    from tests.test_giurisprudenza import _cfg_web, _login_admin
    from web.app import create_app
    monkeypatch.delenv("IUSENTRA_OPENGA_SEARCH_URL", raising=False)
    path, meta = risorsa(tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}])
    db = tmp_path / "catalogo.db"
    CatalogoOpenGA(db).importa(path, meta)
    monkeypatch.setenv("IUSENTRA_OPENGA_CATALOGO_DB", str(db))
    config = {**_cfg_web(tmp_path), "DATA_DIR": str(tmp_path)}
    _login_admin(config)
    app = create_app(config)
    with app.test_client() as client:
        url = "/api/v1/ui/giurisprudenza/ricerca-amministrativa"
        assert client.post(url, json={"q": "soggiorno"}).status_code in {401, 403}
        client.post("/login", data={"username": "admin-giurisprudenza", "password": "Admin1234!"})
        result = client.post(url, json={"q": "soggiorno"})
        assert result.status_code == 200
        assert result.json["ok"] and result.json["risultati"]
        assert client.get(url).status_code == 405
        assert client.post(url, json={"q": "soggiorno", "dal": 2026, "al": 2020}).status_code == 400


def test_trasporto_locale_non_invia_contesto_privato(monkeypatch):
    from web.services.openga_search import search_openga as proxy
    seen = []
    class Response:
        status_code = 200
        content = b"{}"
        def raise_for_status(self):
            return None
        def json(self):
            return {"ok": True, "risultati": [], "evidence_scope": "metadata_only"}
    def post(url, **kwargs):
        seen.append((url, kwargs))
        return Response()
    monkeypatch.setattr("requests.post", post)
    proxy({"q": "oggetto", "fascicolo": "privato", "cookie": "non inoltrare", "db": "/altro"}, {"OPENGA_SEARCH_URL": "http://openga-search:8092"})
    assert seen[0][1]["json"] == {"q": "oggetto"}
    assert seen[0][1]["allow_redirects"] is False
    with pytest.raises(ValueError):
        proxy({"q": "oggetto"}, {"OPENGA_SEARCH_URL": "https://external.example:8092"})
    assert len(seen) == 1


def test_sede_esplicita_guida_anche_la_modalita_rapida(tmp_path, monkeypatch):
    import sqlite3
    path, meta = risorsa(tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}])
    db = tmp_path / "catalogo.db"
    CatalogoOpenGA(db).importa(path, meta)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE righe SET sede='004',nome_sede='TAR ABRUZZO - L’AQUILA'")
    observed = []
    original = CatalogoOpenGA.cerca
    def check(self, q, **kwargs):
        observed.append(kwargs["sede"])
        return original(self, q, **kwargs)
    monkeypatch.setattr(CatalogoOpenGA, "cerca", check)
    result = search_openga({"q": "TAR L’Aquila permesso soggiorno"}, {"OPENGA_CATALOGO_DB": str(db)})
    assert result["ok"] and result["risultati"]
    assert observed == [("004",)]
