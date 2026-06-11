"""Test reali di tentativi di accesso contro il guard anti brute-force del login.

Verifica la base di sicurezza "nessuno entra senza credenziali valide":
- dopo N fallimenti la coppia (IP, username) viene bloccata,
- durante il blocco anche la password CORRETTA viene respinta (429),
- l'evento viene tracciato nell'audit,
- un login corretto sotto soglia funziona e azzera i tentativi,
- il blocco è per (IP, username): la vittima può comunque entrare da un altro IP,
- in ambiente di test il guard è disattivato di default (non rompe la suite).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


ADMIN = {"username": "admin", "password": "admin"}
WRONG = {"username": "admin", "password": "password-sbagliata"}


def _app(tmp_path: Path, **guard_overrides):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    # create_app non propaga chiavi di config sconosciute: il guard si configura
    # sull'app risultante (in produzione gli stessi valori arrivano da env).
    guard_cfg = {
        "LOGIN_GUARD_ENABLED": True,
        "LOGIN_GUARD_MAX_PER_USER": 3,
        "LOGIN_GUARD_MAX_PER_IP": 50,
        "LOGIN_GUARD_WINDOW_SECONDS": 900,
        "LOGIN_GUARD_LOCK_SECONDS": 900,
    }
    guard_cfg.update(guard_overrides)
    app.config.update(guard_cfg)
    return app


def _audit_text(app) -> str:
    path = Path(app.config["AUDIT_DB"])
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_login_si_blocca_dopo_troppe_credenziali_errate(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        first = client.post("/login", data=WRONG)
        second = client.post("/login", data=WRONG)
        assert first.status_code == 200
        assert second.status_code == 200
        assert "Credenziali non valide" in first.get_data(as_text=True)

        # Terzo fallimento: raggiunge la soglia -> blocco attivato (429 + Retry-After).
        third = client.post("/login", data=WRONG)
        assert third.status_code == 429
        assert int(third.headers["Retry-After"]) > 0
        assert "sospeso" in third.get_data(as_text=True).lower()

        # Durante il blocco anche la password CORRETTA viene respinta.
        during_lock = client.post("/login", data=ADMIN)
        assert during_lock.status_code == 429
        assert int(during_lock.headers["Retry-After"]) > 0
        # Non è stata creata alcuna sessione: nessun cookie di sessione valido.
        assert "user_id" not in (during_lock.headers.get("Set-Cookie", "") or "")

    audit_raw = _audit_text(app)
    assert "auth.login_bloccato" in audit_raw


def test_login_corretto_sotto_soglia_funziona_e_azzera_i_tentativi(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        # Due fallimenti (sotto la soglia di 3).
        assert client.post("/login", data=WRONG).status_code == 200
        assert client.post("/login", data=WRONG).status_code == 200

        # Login corretto: redirect di successo (non 429, non pagina di errore).
        ok = client.post("/login", data=ADMIN)
        assert ok.status_code == 302
        set_cookie = ok.headers.get("Set-Cookie", "") or ""
        assert "HttpOnly" in set_cookie
        assert "SameSite=Lax" in set_cookie

        # I tentativi sono stati azzerati: un nuovo fallimento riparte da 1 (200, non 429).
        client.post("/logout")
        again = client.post("/login", data=WRONG)
        assert again.status_code == 200


def test_blocco_per_coppia_ip_username_non_blocca_la_vittima_da_altro_ip(tmp_path: Path):
    app = _app(tmp_path)
    attacker = {"X-Forwarded-For": "203.0.113.10"}
    victim = {"X-Forwarded-For": "198.51.100.20"}
    with app.test_client() as client:
        # L'attaccante blocca la coppia (suo IP, admin) con 3 fallimenti.
        for _ in range(3):
            client.post("/login", data=WRONG, headers=attacker)
        blocked = client.post("/login", data=ADMIN, headers=attacker)
        assert blocked.status_code == 429

        # La vittima legittima, da un altro IP, entra comunque: nessun DoS sull'account.
        legit = client.post("/login", data=ADMIN, headers=victim)
        assert legit.status_code == 302


def test_guard_disattivato_di_default_in_ambiente_di_test(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    # Nessun override: LOGIN_GUARD_ENABLED assente -> default disattivo sotto TESTING.
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as client:
        for _ in range(6):
            resp = client.post("/login", data=WRONG)
            assert resp.status_code == 200


def test_security_headers_presenti_sulla_pagina_di_login(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        resp = client.get("/login")
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    # In test la CSP è in report-only; in produzione (CSP_REPORT_ONLY off) è applicata.
    csp = resp.headers.get("Content-Security-Policy") or resp.headers.get(
        "Content-Security-Policy-Report-Only", ""
    )
    assert "default-src 'self'" in csp
