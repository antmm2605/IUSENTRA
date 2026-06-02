from __future__ import annotations

import requests

from pct import uffici_giudiziari as ug


class _OfflineResponse:
    ok = False


def test_aggiorna_ignora_url_non_autorizzato_e_usa_solo_pst_ufficiale(tmp_path, monkeypatch):
    chiamati: list[str] = []

    def fake_get(endpoint: str, **_kwargs):
        chiamati.append(endpoint)
        return _OfflineResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(ug, "_REMOTO_URL", "")

    gestore = ug.GestoreUfficiGiudiziari(str(tmp_path / "uffici.json"))
    ok, messaggio = gestore.aggiorna(url="http://169.254.169.254/latest/meta-data")

    assert ok is True
    assert "registro interno" in messaggio
    assert chiamati == [ug._PST_UFFICI]


def test_verifica_variazioni_ignora_env_non_autorizzato_e_usa_solo_pst_ufficiale(tmp_path, monkeypatch):
    chiamati: list[str] = []

    def fake_get(endpoint: str, **_kwargs):
        chiamati.append(endpoint)
        return _OfflineResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(ug, "_REMOTO_URL", "http://169.254.169.254/latest/meta-data")

    gestore = ug.GestoreUfficiGiudiziari(str(tmp_path / "uffici.json"))
    report = gestore.verifica_variazioni()

    assert report["sorgente"] == "registro_interno_versionato"
    assert chiamati == [ug._PST_UFFICI]
