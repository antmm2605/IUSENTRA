from __future__ import annotations

import re
from pathlib import Path

from web.app import create_app

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def _extract_csrf_token(html: str) -> str:
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
        page = client.get("/login")
        token = _extract_csrf_token(page.get_data(as_text=True))

        assert page.status_code == 200
        assert page.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert page.headers["X-Content-Type-Options"] == "nosniff"
        assert page.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert page.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert "max-age=31536000" in page.headers["Strict-Transport-Security"]

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
        login_page = client.get("/login")
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

        profile_page = client.get("/profilo")
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
