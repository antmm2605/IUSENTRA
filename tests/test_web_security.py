from __future__ import annotations

import re
from pathlib import Path

from web.app import create_app

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
    if not match:
        match = re.search(r'name="_csrf_token"\s+value="([^"]+)"', html)
    assert match, "Token CSRF non trovato nella pagina."
    return match.group(1)


def test_login_headers_e_bootstrap_password_forzata(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["TESTING"] = False
    cfg["PCT_HTTPS"] = True
    app = create_app(cfg)

    with app.test_client() as client:
        page = client.get("/login?_legacy=1")
        html = page.get_data(as_text=True)
        token = _extract_csrf_token(html)

        assert page.status_code == 200
        assert page.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert page.headers["X-Content-Type-Options"] == "nosniff"
        assert page.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert page.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert "max-age=31536000" in page.headers["Strict-Transport-Security"]
        assert 'id="accesso-react-root"' in html
        assert 'data-vista="login"' in html
        assert "iusentra-login-mark.svg" in html

        next_page = client.get("/login?next=/notifiche-legali&_legacy=1")
        assert 'data-next="/notifiche-legali"' in next_page.get_data(as_text=True)

        blocked = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            headers={"Origin": "https://evil.example"},
            follow_redirects=False,
        )
        assert blocked.status_code == 400

        allowed = client.post(
            "/login",
            data={
                "username": "admin",
                "password": "admin",
                "_csrf_token": token,
            },
            follow_redirects=False,
        )
        assert allowed.status_code == 302
        assert allowed.headers["Location"].endswith("/profilo?password_obbligatoria=1")


def test_password_temporanea_blocca_navigazione_finche_non_viene_cambiata(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["TESTING"] = False
    app = create_app(cfg)

    with app.test_client() as client:
        login_page = client.get("/login?_legacy=1")
        login_token = _extract_csrf_token(login_page.get_data(as_text=True))

        login = client.post(
            "/login",
            data={
                "username": "admin",
                "password": "admin",
                "_csrf_token": login_token,
            },
            follow_redirects=False,
        )
        assert login.status_code == 302
        assert login.headers["Location"].endswith("/profilo?password_obbligatoria=1")

        blocked_dashboard = client.get("/dashboard", follow_redirects=False)
        assert blocked_dashboard.status_code == 302
        assert blocked_dashboard.headers["Location"].endswith("/profilo?password_obbligatoria=1")

        profile_page = client.get("/profilo?_legacy=1")
        profile_token = _extract_csrf_token(profile_page.get_data(as_text=True))

        changed = client.post(
            "/profilo",
            data={
                "azione": "password",
                "password_old": "admin",
                "password_new": "NuovaPassword123!",
                "_csrf_token": profile_token,
            },
            follow_redirects=False,
        )
        assert changed.status_code == 302
        assert changed.headers["Location"].endswith("/profilo")

        home = client.get("/", follow_redirects=False)
        assert home.status_code in {200, 302}
        if home.status_code == 302:
            assert home.headers["Location"].endswith("/admin/")


def test_profilo_cambia_nome_utente_solo_con_la_password_del_proprio_account(tmp_path: Path):
    from pct.auth import GestioneUtenti, RuoloUtente

    cfg = _cfg_web(tmp_path)
    cfg["TESTING"] = False
    cfg["MULTI_TENANT"] = False
    _write_studio_config(tmp_path / "config" / "studio.json")
    gu = GestioneUtenti(cfg["AUTH_DB"], cfg["AUDIT_DB"], crea_admin_se_vuoto=False)
    attuale = gu.crea("titolare", "PasswordPrima!1", RuoloUtente.AVVOCATO, must_change_password=False)
    altro = gu.crea("collega", "PasswordAltra!2", RuoloUtente.AVVOCATO, email="riservato@example.test")
    app = create_app(cfg)

    def accedi(client, username):
        token = _extract_csrf_token(client.get("/login").get_data(as_text=True))
        return client.post("/login", data={"username": username, "password": "PasswordPrima!1", "_csrf_token": token})

    with app.test_client() as client:
        assert accedi(client, "titolare").status_code == 302
        profilo = client.get("/profilo")
        token = _extract_csrf_token(profilo.get_data(as_text=True))

        def cambia(username, password, csrf=token):
            return client.post("/profilo", headers={"Accept": "application/json"}, data={
                "azione": "username", "username": username, "password_conferma_username": password,
                "_csrf_token": csrf, "id": altro.id,
            })

        assert cambia("nuovo.nome", "PasswordPrima!1", "").status_code == 400
        assert cambia("nuovo.nome", "PasswordAltra!2").get_json()["message"] == "Password attuale non corretta."
        assert cambia(" COLLEGA ", "PasswordPrima!1").get_json()["message"] == "Nome utente già in uso."
        assert cambia("nome con spazi", "PasswordPrima!1").status_code == 400
        risposta = cambia(" Nuovo.Nome ", "PasswordPrima!1")
        assert risposta.status_code == 200 and risposta.get_json()["ok"]
        utente = client.get("/api/v1/ui/profilo").get_json()["user"]
        assert (utente["id"], utente["username"]) == (attuale.id, "nuovo.nome")

    with app.test_client() as client:
        accedi(client, "titolare")
        assert client.get("/api/v1/ui/profilo").status_code in {401, 403}
        assert accedi(client, "nuovo.nome").status_code == 302
        assert client.get("/api/v1/ui/profilo").get_json()["user"]["id"] == attuale.id

    riletto = GestioneUtenti(cfg["AUTH_DB"], cfg["AUDIT_DB"], crea_admin_se_vuoto=False)
    assert riletto.get(altro.id).username == "collega"
    assert any(evento.azione == "auth.cambia_username" and evento.risorsa_id == attuale.id for evento in riletto._audit)


def test_api_v1_cors_resta_chiuso_di_default(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)

    with app.test_client() as client:
        response = client.get("/api/v1/", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


def test_api_v1_cors_consente_solo_origin_configurati(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["API_V1_ALLOWED_ORIGINS"] = "https://mobile.example.it,https://app.example.it"
    app = create_app(cfg)

    with app.test_client() as client:
        allowed = client.get("/api/v1/", headers={"Origin": "https://mobile.example.it"})
        blocked = client.get("/api/v1/", headers={"Origin": "https://evil.example"})

    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://mobile.example.it"
    assert "Origin" in allowed.headers.get("Vary", "")
    assert blocked.status_code == 200
    assert "Access-Control-Allow-Origin" not in blocked.headers
