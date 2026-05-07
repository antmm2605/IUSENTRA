from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.auth import RuoloUtente
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _csrf_from_html(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]*)"', html)
    return match.group(1) if match else ""


def _login_as(client, username: str, password: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    assert response.status_code == 200, f"login fallito per {username}: {response.status_code}"


def _assert_no_sensitive_payload(payload: object, *, forbidden_value: str = "") -> None:
    raw = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = ("password_hash", "reset_token", "totp_secret", "session token", "api key")
    leaked = [item for item in forbidden if item in raw]
    assert not leaked, f"Payload utenti espone campi sensibili: {leaked}"
    if forbidden_value:
        assert forbidden_value.lower() not in raw, "La credenziale temporanea e' stata restituita in chiaro."


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="iusentra-utenti-api-", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        _write_studio_config(tmp_path / "config" / "studio.json")
        app = create_app(_cfg_web(tmp_path))
        _crea_operatore(app)

        with app.app_context():
            manager = app.extensions["core_runtime"]["get_utenti"]()
            target = manager.crea(
                username="target-utenti",
                password="Target123!",
                ruolo=RuoloUtente.SEGRETERIA,
                nome_completo="Target Utenti",
                email="target@example.it",
                must_change_password=False,
            )
            reader = manager.crea(
                username="lettore-utenti",
                password="Lettore123!",
                ruolo=RuoloUtente.CONTABILE,
                nome_completo="Lettore Utenti",
                permessi_extra=["utenti.leggi"],
                must_change_password=False,
            )

        with app.test_client() as client:
            _login(client)
            app.config["ENABLE_BROWSER_CSRF"] = True

            shell = client.get("/utenti")
            assert shell.status_code == 200
            shell_html = shell.get_data(as_text=True)
            assert "IUSENTRA - React Shell" in shell_html
            assert 'id="root"' in shell_html
            csrf = _csrf_from_html(shell_html)
            assert csrf, "CSRF assente dalla shell React"

            legacy = client.get("/utenti?_legacy=1")
            legacy_html = legacy.get_data(as_text=True)
            assert legacy.status_code == 200
            assert "Gestione Utenti" in legacy_html
            assert 'id="root"' not in legacy_html

            post_legacy = client.post("/utenti")
            assert post_legacy.status_code == 405
            assert 'id="root"' not in post_legacy.get_data(as_text=True)

            api_get = client.get("/api/v1/ui/utenti")
            assert api_get.status_code == 200
            api_payload = api_get.get_json()
            assert api_payload["ok"] is True
            assert api_payload["contracts"]["writes"] == "json_api"
            assert api_payload["contracts"]["operational"] is True
            assert api_payload["actions"]["canUpdate"] is True
            assert api_payload["users"]
            assert api_payload["roles"]
            _assert_no_sensitive_payload(api_payload)

            invalid = client.post(
                f"/api/v1/ui/utenti/{target.id}/stato",
                json={"active": "no"},
                headers={"X-CSRF-Token": csrf},
            )
            assert invalid.status_code == 400
            invalid_payload = invalid.get_json()
            assert invalid_payload["ok"] is False
            assert invalid_payload["errors"]

            status = client.post(
                f"/api/v1/ui/utenti/{target.id}/stato",
                json={"active": False},
                headers={"X-CSRF-Token": csrf},
            )
            assert status.status_code == 200
            status_payload = status.get_json()
            assert status_payload["ok"] is True
            assert status_payload["user"]["active"] is False
            _assert_no_sensitive_payload(status_payload)

            role = client.post(
                f"/api/v1/ui/utenti/{target.id}/ruolo",
                json={"role": "AVVOCATO"},
                headers={"X-CSRF-Token": csrf},
            )
            assert role.status_code == 200
            role_payload = role.get_json()
            assert role_payload["ok"] is True
            assert role_payload["user"]["role"] == "AVVOCATO"
            _assert_no_sensitive_payload(role_payload)

            profile = client.post(
                f"/api/v1/ui/utenti/{target.id}/profilo",
                json={"name": "Target Aggiornato", "email": "aggiornato@example.it"},
                headers={"X-CSRF-Token": csrf},
            )
            assert profile.status_code == 200
            profile_payload = profile.get_json()
            assert profile_payload["ok"] is True
            assert profile_payload["user"]["name"] == "Target Aggiornato"
            _assert_no_sensitive_payload(profile_payload)

            temporary_value = "NuovaTemp123!"
            reset = client.post(
                f"/api/v1/ui/utenti/{target.id}/reset-password",
                json={"temporaryPassword": temporary_value, "confirm": True},
                headers={"X-CSRF-Token": csrf},
            )
            assert reset.status_code == 200
            reset_payload = reset.get_json()
            assert reset_payload["ok"] is True
            assert reset_payload["user"]["mustChangeCredential"] is True
            _assert_no_sensitive_payload(reset_payload, forbidden_value=temporary_value)

        with app.app_context():
            manager = app.extensions["core_runtime"]["get_utenti"]()
            updated = manager.get(target.id)
            assert updated is not None
            assert updated.attivo is False
            assert updated.ruolo == RuoloUtente.AVVOCATO
            assert updated.nome_completo == "Target Aggiornato"
            assert updated.must_change_password is True
            actions = {event.azione for event in manager.audit_log(limit=50) if event.risorsa_id == target.id}
            assert "utenti.modifica_stato" in actions
            assert "utenti.modifica_ruolo" in actions
            assert "utenti.modifica_profilo" in actions
            assert "utenti.reset_password" in actions

        with app.test_client() as reader_client:
            app.config["ENABLE_BROWSER_CSRF"] = False
            _login_as(reader_client, reader.username, "Lettore123!")
            app.config["ENABLE_BROWSER_CSRF"] = True
            reader_shell = reader_client.get("/utenti")
            reader_csrf = _csrf_from_html(reader_shell.get_data(as_text=True))
            assert reader_csrf
            for endpoint, payload in [
                (f"/api/v1/ui/utenti/{target.id}/stato", {"active": True}),
                (f"/api/v1/ui/utenti/{target.id}/ruolo", {"role": "SEGRETERIA"}),
                (f"/api/v1/ui/utenti/{target.id}/reset-password", {"temporaryPassword": "NoPermesso123!", "confirm": True}),
            ]:
                denied = reader_client.post(endpoint, json=payload, headers={"X-CSRF-Token": reader_csrf})
                assert denied.status_code == 403
                denied_payload = denied.get_json()
                assert denied_payload["ok"] is False
                assert denied_payload["errors"]["permission"]
                _assert_no_sensitive_payload(denied_payload)

            denied_profile = reader_client.post(
                f"/api/v1/ui/utenti/{target.id}/profilo",
                json={"name": "No Permesso", "email": "no@example.it"},
                headers={"X-CSRF-Token": reader_csrf},
            )
            assert denied_profile.status_code == 403
            denied_profile_payload = denied_profile.get_json()
            assert denied_profile_payload["ok"] is False
            assert denied_profile_payload["errors"]["permission"]

    print("Check tranche 14A utenti API OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
