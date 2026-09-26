"""Revisione 2.410.0: accessi, permessi e difese del browser verificati con l'app reale."""

from __future__ import annotations

from pathlib import Path

from flask import render_template_string

from pct.auth import GestioneUtenti, RuoloUtente
from tests.test_topbar_operational_api import _cfg_web, _create_user, _login
from web.app import create_app


def _app(tmp_path: Path, **extra):
    cfg = _cfg_web(tmp_path)
    cfg.update(extra)
    app = create_app(cfg)
    _create_user(app, "operatore", "Operatore123!")
    return app


def test_api_senza_sessione_risponde_401_json(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        risposta = client.get("/api/agenda")
        assert risposta.status_code == 401
        # I controlli di salute del deploy restano raggiungibili.
        assert client.get("/api/pronto").status_code in (200, 503)
        assert risposta.get_json()["code"] == "authentication_required"
        # Nessuna rotta sotto /api/ restituisce dati senza accesso (solo l'indice pubblico).
        aperte = []
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith("/api/") or "<" in rule.rule or "GET" not in rule.methods:
                continue
            r = client.get(rule.rule)
            if r.status_code < 300 and rule.rule not in {"/api/v1/", "/api/pronto", "/api/health", "/api/metriche/runtime"}:
                aperte.append(rule.rule)
        assert aperte == []


def test_agenda_scrittura_richiede_permesso(tmp_path):
    app = _app(tmp_path)
    _create_user(app, "segreteria", "Segreteria123!", ruolo=RuoloUtente.SEGRETERIA, permessi_negati=["agenda.scrivi", "agenda.elimina"])
    with app.test_client() as client:
        _login(client, "segreteria", "Segreteria123!")
        headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        for percorso in ("/agenda/ABC/elimina", "/agenda/ABC/stato"):
            risposta = client.post(percorso, headers=headers)
            assert risposta.status_code == 403, percorso


def test_scrittura_da_sito_estraneo_respinta(tmp_path):
    app = _app(tmp_path, ENABLE_BROWSER_CSRF=True)
    with app.test_client() as client:
        accesso = client.post(
            "/login",
            data={"username": "operatore", "password": "Operatore123!"},
            headers={"Origin": "http://localhost"},
        )
        assert accesso.status_code in (200, 302)
        estranea = client.post("/api/recent/search", json={"query": "RG 1"}, headers={"Origin": "https://sito-malevolo.example"})
        assert estranea.status_code == 400
        propria = client.post("/api/recent/search", json={"query": "RG 1"}, headers={"Origin": "http://localhost"})
        assert propria.status_code == 200


def test_aggiornamento_indice_ricerca_non_ripetibile_a_raffica(tmp_path):
    from web.blueprints import global_search

    global_search._reindex_ultimo.clear()
    app = _app(tmp_path)
    with app.test_client() as client:
        _login(client)
        prima = client.post("/api/global-search/reindex")
        assert prima.status_code == 200
        seconda = client.post("/api/global-search/reindex")
        assert seconda.status_code == 429
        assert "riprova" in seconda.get_json()["message"]
    global_search._reindex_ultimo.clear()


def test_documento_non_scaricabile_senza_permesso_di_lettura(tmp_path):
    app = _app(tmp_path)
    _create_user(app, "contabile", "Contabile123!", ruolo=RuoloUtente.CONTABILE, permessi_negati=["fascicoli.leggi"])
    with app.test_client() as client:
        _login(client, "contabile", "Contabile123!")
        assert client.get("/fascicoli/F1/documenti/D1/scarica").status_code == 403
        assert client.get("/fascicoli/F1/documenti/D1/visualizza").status_code == 403


def test_utente_disattivato_perde_la_sessione(tmp_path):
    app = _app(tmp_path)
    _create_user(app, "praticante", "Praticante123!", ruolo=RuoloUtente.PRATICANTE)
    with app.test_client() as client:
        _login(client, "praticante", "Praticante123!")
        assert client.get("/api/recent").status_code == 200
        with app.app_context():
            gestore = GestioneUtenti(
                db_path=app.config["AUTH_DB"],
                audit_path=app.config["AUDIT_DB"],
                secret_key=app.secret_key,
                bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
                bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
            )
            utente = next(u for u in gestore.tutti() if u.username == "praticante")
            gestore.aggiorna(utente.id, attivo=False)
        assert client.get("/api/recent").status_code == 401


def test_html_dei_messaggi_ripulito(tmp_path):
    app = _app(tmp_path)
    with app.test_request_context("/"):
        html = render_template_string(
            "{{ corpo | html_sicuro }}",
            corpo='<p onclick="x()">Gentile <b>cliente</b></p><script>alert(1)</script><a href="javascript:alert(1)">link</a>',
        )
    assert "<script" not in html and "onclick" not in html and "javascript:" not in html
    assert "<b>cliente</b>" in html


def test_snippet_della_ricerca_con_escape():
    from pct.search_index import _snippet_sicuro

    assert _snippet_sicuro("<img src=x onerror=alert(1)> parola") == "&lt;img src=x onerror=alert(1)&gt; <mark>parola</mark>"


def test_caldav_solo_https_pubblico_e_stesso_server():
    import pytest

    from pct.calendar_providers.apple_caldav import url_caldav_sicuro
    from pct.calendar_providers.base import CalendarProviderError

    for url in ("http://caldav.icloud.com/", "https://127.0.0.1/dav", "https://redis:6379/", "https://10.0.0.5/dav"):
        with pytest.raises(CalendarProviderError):
            url_caldav_sicuro(url)
    with pytest.raises(CalendarProviderError):
        url_caldav_sicuro("https://evil.example.com/cal/1.ics", base="https://caldav.icloud.com/")


def test_totp_valido_e_non_valido():
    import time

    from pct.auth import _hotp, verifica_totp
    import base64

    segreto = base64.b32encode(b"12345678901234567890").decode()
    codice = str(_hotp(base64.b32decode(segreto), int(time.time()) // 30)).zfill(6)
    assert verifica_totp(segreto, codice)
    assert not verifica_totp(segreto, "000000" if codice != "000000" else "111111")


def test_chiave_sessioni_solo_nella_cartella_dati(tmp_path, monkeypatch):
    import os
    import stat

    from web.services.security_runtime import _chiave_persistente

    monkeypatch.delenv("PCT_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert _chiave_persistente() == ""
    assert not (tmp_path / ".chiave_sessioni").exists()
    dati = tmp_path / "dati"
    dati.mkdir()
    monkeypatch.setenv("PCT_DATA_DIR", str(dati))
    prima = _chiave_persistente()
    assert len(prima) == 64 and _chiave_persistente() == prima
    assert stat.S_IMODE(os.stat(dati / ".chiave_sessioni").st_mode) == 0o600
