"""Il riepilogo delle discordanze non risponde mai 500 (giro visivo del 01/11/2026, V48)."""

from __future__ import annotations

from tests.test_strumenti_legali import _cfg_web


def _client(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    return client


def test_senza_studio_identificato_il_riepilogo_e_vuoto_e_non_un_errore(tmp_path):
    risposta = _client(tmp_path).get("/api/v1/ui/controllo-studio/discordanze", headers={"Accept": "application/json"})
    assert risposta.status_code == 200
    corpo = risposta.get_json()
    assert corpo["ok"] is True and corpo["disponibile"] is False
    assert corpo["voci"] == [] and corpo["nonLette"] == 0 and corpo["lettureInCorso"] == 0


def test_un_guasto_dell_archivio_risponde_503_in_json(tmp_path, monkeypatch):
    import web.services.discordanze_letture_runtime as runtime

    def guasto(page=1):
        raise OSError("archivio non leggibile")

    monkeypatch.setattr(runtime, "riepilogo_discordanze", guasto)
    risposta = _client(tmp_path).get("/api/v1/ui/controllo-studio/discordanze", headers={"Accept": "application/json"})
    assert risposta.status_code == 503
    assert risposta.get_json()["ok"] is False
