"""Pagine d'errore: 403/404 React (ErroreApp), 500 e «Nessuna connessione» HTML statico autonomo."""

from __future__ import annotations

from pathlib import Path

from flask import abort

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app

RADICE = Path(__file__).resolve().parents[1]


def test_404_e_403_sono_pagine_react_con_stato_corretto(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    @app.route("/_collaudo/vietato")
    def _vietato():
        abort(403)

    with app.test_client() as anonimo:
        mancante_anonimo = anonimo.get("/percorso-che-non-esiste-davvero")
    with app.test_client() as client:
        _login(client)
        mancante = client.get("/percorso-che-non-esiste-davvero")
        vietato = client.get("/_collaudo/vietato")

    assert mancante.status_code == 404
    html = mancante.get_data(as_text=True)
    assert 'id="errore-react-root"' in html and 'data-errore="404"' in html
    assert 'data-autenticato="1"' in html
    assert "Pagina non trovata" in html  # testo leggibile anche senza bundle
    assert "base.html" not in html and "navbar" not in html
    assert mancante.headers["Cache-Control"].startswith("no-store")
    assert mancante_anonimo.status_code in {302, 404}
    assert vietato.status_code == 403
    assert 'data-errore="403"' in vietato.get_data(as_text=True)


def test_500_e_offline_sono_html_statico_senza_jinja_ne_bundle(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/_collaudo/guasto")
    def _guasto():
        raise RuntimeError("guasto di collaudo")

    with app.test_client() as client:
        _login(client)
        guasto = client.get("/_collaudo/guasto")
        offline = client.get("/offline")

    for risposta, nome in ((guasto, "500.html"), (offline, "offline.html")):
        corpo = risposta.get_data(as_text=True)
        sorgente = (RADICE / "web" / "static" / "errori" / nome).read_text(encoding="utf-8")
        assert corpo == sorgente
        assert "{{" not in corpo and "{%" not in corpo
        assert "/static/react/" not in corpo
        assert "nonce" not in corpo
    assert guasto.status_code == 500
    assert "Errore interno del server" in guasto.get_data(as_text=True)
    assert "guasto di collaudo" not in guasto.get_data(as_text=True)
    assert offline.status_code == 200
    assert '<script src="/static/errori/offline.js"></script>' in offline.get_data(as_text=True)


def test_service_worker_conserva_pagina_offline_e_suo_script():
    sw = (RADICE / "web" / "static" / "sw.js").read_text(encoding="utf-8")
    assert "'/static/errori/offline.js'" in sw
    for nome in ("errori/403.html", "errori/404.html", "errori/500.html", "offline.html", "404.html", "500.html"):
        assert not (RADICE / "web" / "templates" / nome).exists(), nome
