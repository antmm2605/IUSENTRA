from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.auth import GestioneUtenti, RuoloUtente
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


def _assert_no_secrets(payload: object) -> None:
    raw = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = ("password", "password_hash", "reset_token", "totp_secret", "session token", "api key")
    leaked = [item for item in forbidden if item in raw]
    assert not leaked, f"Payload profili espone campi sensibili: {leaked}"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="iusentra-profili-api-", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        _write_studio_config(tmp_path / "config" / "studio.json")
        app = create_app(_cfg_web(tmp_path))
        _crea_operatore(app)

        with app.app_context():
            manager = app.extensions["core_runtime"]["get_utenti"]()
            target = manager.crea(
                username="target-profili",
                password="Target123!",
                ruolo=RuoloUtente.SEGRETERIA,
                nome_completo="Target Profili",
                must_change_password=False,
            )
            reader = manager.crea(
                username="lettore-profili",
                password="Lettore123!",
                ruolo=RuoloUtente.CONTABILE,
                nome_completo="Lettore Profili",
                permessi_extra=["utenti.leggi"],
                must_change_password=False,
            )

        with app.test_client() as client:
            _login(client)
            app.config["ENABLE_BROWSER_CSRF"] = True

            shell = client.get("/profili")
            assert shell.status_code == 200
            shell_html = shell.get_data(as_text=True)
            assert "IUSENTRA - React Shell" in shell_html
            assert 'id="root"' in shell_html
            csrf = _csrf_from_html(shell_html)
            assert csrf, "CSRF assente dalla shell React"

            legacy = client.get("/profili?_legacy=1")
            legacy_html = legacy.get_data(as_text=True)
            assert legacy.status_code == 200
            assert "Matrice permessi per ruolo" in legacy_html
            assert 'id="root"' not in legacy_html

            api_get = client.get("/api/v1/ui/profili")
            assert api_get.status_code == 200
            api_payload = api_get.get_json()
            assert api_payload["ok"] is True
            assert api_payload["contracts"]["writes"] == "json_api"
            assert api_payload["actions"]["canWrite"] is True
            assert api_payload["roles"]
            assert api_payload["permissions"]
            assert api_payload["matrix"]
            _assert_no_secrets(api_payload)

            invalid = client.post(
                "/api/v1/ui/profili",
                json={"campo_ignoto": True},
                headers={"X-CSRF-Token": csrf},
            )
            assert invalid.status_code == 400
            invalid_payload = invalid.get_json()
            assert invalid_payload["ok"] is False
            assert invalid_payload["errors"]

            valid = client.post(
                "/api/v1/ui/profili",
                json={
                    "action": "update_user_override",
                    "userId": target.id,
                    "extraPermissions": ["backup.leggi"],
                    "deniedPermissions": [],
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert valid.status_code == 200
            valid_payload = valid.get_json()
            assert valid_payload["ok"] is True
            assert valid_payload["updated"]["id"] == target.id
            assert "backup.leggi" in valid_payload["updated"]["extraPermissions"]
            _assert_no_secrets(valid_payload)

            post_legacy = client.post("/profili")
            assert post_legacy.status_code == 405
            assert 'id="root"' not in post_legacy.get_data(as_text=True)

        with app.app_context():
            manager = app.extensions["core_runtime"]["get_utenti"]()
            updated = manager.get(target.id)
            assert updated is not None
            assert "backup.leggi" in updated.permessi_extra
            audit = manager.audit_log(id_utente="", azione="utenti.aggiorna_permessi", limit=20)
            assert any(event.risorsa_id == target.id for event in audit)

        with app.test_client() as reader_client:
            app.config["ENABLE_BROWSER_CSRF"] = False
            _login_as(reader_client, reader.username, "Lettore123!")
            app.config["ENABLE_BROWSER_CSRF"] = True
            reader_shell = reader_client.get("/profili")
            reader_csrf = _csrf_from_html(reader_shell.get_data(as_text=True))
            denied = reader_client.post(
                "/api/v1/ui/profili",
                json={
                    "action": "update_user_override",
                    "userId": target.id,
                    "extraPermissions": [],
                    "deniedPermissions": [],
                },
                headers={"X-CSRF-Token": reader_csrf},
            )
            assert denied.status_code == 403
            denied_payload = denied.get_json()
            assert denied_payload["ok"] is False
            assert denied_payload["errors"]["permission"]

    print("Check tranche 13A profili API OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
