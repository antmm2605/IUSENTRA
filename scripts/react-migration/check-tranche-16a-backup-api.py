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


def _assert_no_sensitive_payload(payload: object) -> None:
    raw = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = (
        "api_key",
        "client_secret",
        "smtp_password",
        "pec_password",
        "session token",
        "stack_trace",
        "traceback",
        "percorso_file",
        "hash_file",
        "hash_atteso",
        "hash_attuale",
        "c:\\",
        "/tmp/",
        "/data/",
    )
    leaked = [item for item in forbidden if item in raw]
    assert not leaked, f"Payload backup espone dati non ammessi: {leaked}"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="iusentra-backup-api-", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        _write_studio_config(tmp_path / "config" / "studio.json")
        app = create_app(_cfg_web(tmp_path))
        _crea_operatore(app)

        with app.app_context():
            manager = app.extensions["core_runtime"]["get_utenti"]()
            reader = manager.crea(
                username="lettore-backup",
                password="Lettore123!",
                ruolo=RuoloUtente.CONTABILE,
                nome_completo="Lettore Backup",
                permessi_extra=["backup.leggi"],
                must_change_password=False,
            )

        with app.test_client() as client:
            _login(client)
            app.config["ENABLE_BROWSER_CSRF"] = True

            shell = client.get("/backup")
            assert shell.status_code == 200
            shell_html = shell.get_data(as_text=True)
            assert "IUSENTRA - React Shell" in shell_html
            assert 'id="root"' in shell_html
            csrf = _csrf_from_html(shell_html)
            assert csrf, "CSRF assente dalla shell React"

            legacy = client.get("/backup?_legacy=1")
            legacy_html = legacy.get_data(as_text=True)
            assert legacy.status_code == 200
            assert "Backup" in legacy_html
            assert 'id="root"' not in legacy_html

            subpath = client.get("/backup/qualunque")
            assert subpath.status_code in {302, 404, 405}
            assert 'id="root"' not in subpath.get_data(as_text=True)

            post_legacy = client.post("/backup")
            assert post_legacy.status_code == 405
            assert 'id="root"' not in post_legacy.get_data(as_text=True)

            api_get = client.get("/api/v1/ui/backup")
            assert api_get.status_code == 200
            api_payload = api_get.get_json()
            assert api_payload["ok"] is True
            assert api_payload["contracts"]["writes"] == "json_api"
            assert api_payload["contracts"]["operational"] is True
            assert api_payload["contracts"]["restore_migrated"] is False
            assert "status" in api_payload
            assert "backups" in api_payload
            assert "integrity" in api_payload
            assert api_payload["actions"]["canCreate"] is True
            assert api_payload["actions"]["canVerify"] is True
            _assert_no_sensitive_payload(api_payload)

            invalid = client.post(
                "/api/v1/ui/backup/crea",
                json={"destination": "C:/non-ammesso"},
                headers={"X-CSRF-Token": csrf},
            )
            assert invalid.status_code == 400
            invalid_payload = invalid.get_json()
            assert invalid_payload["ok"] is False
            assert invalid_payload["errors"]
            _assert_no_sensitive_payload(invalid_payload)

            create = client.post(
                "/api/v1/ui/backup/crea",
                json={"type": "COMPLETO", "components": ["agenda", "clienti"], "note": "check 16A", "confirm": True},
                headers={"X-CSRF-Token": csrf},
            )
            assert create.status_code == 200
            create_payload = create.get_json()
            assert create_payload["ok"] is True
            backup_id = create_payload["backup"]["id"]
            assert create_payload["backup"]["downloadHref"].startswith(f"/backup/{backup_id}/scarica")
            _assert_no_sensitive_payload(create_payload)

            verify = client.post(
                "/api/v1/ui/backup/verifica",
                json={"backupId": backup_id, "confirm": True},
                headers={"X-CSRF-Token": csrf},
            )
            assert verify.status_code == 200
            verify_payload = verify.get_json()
            assert verify_payload["ok"] is True
            assert verify_payload["integrity"]["checkedBackupId"] == backup_id
            _assert_no_sensitive_payload(verify_payload)

        with app.app_context():
            audit_manager = app.extensions["core_runtime"]["get_utenti"]()
            actions = {event.azione for event in audit_manager.audit_log(limit=50) if event.risorsa_id == backup_id}
            assert "backup.crea" in actions
            assert "backup.verifica" in actions

        with app.test_client() as reader_client:
            app.config["ENABLE_BROWSER_CSRF"] = False
            _login_as(reader_client, reader.username, "Lettore123!")
            app.config["ENABLE_BROWSER_CSRF"] = True
            reader_shell = reader_client.get("/backup")
            assert reader_shell.status_code == 200
            reader_csrf = _csrf_from_html(reader_shell.get_data(as_text=True))
            assert reader_csrf

            for endpoint, payload in [
                ("/api/v1/ui/backup/crea", {"type": "COMPLETO", "confirm": True}),
                ("/api/v1/ui/backup/verifica", {"backupId": backup_id, "confirm": True}),
            ]:
                denied = reader_client.post(endpoint, json=payload, headers={"X-CSRF-Token": reader_csrf})
                assert denied.status_code == 403
                denied_payload = denied.get_json()
                assert denied_payload["ok"] is False
                assert denied_payload["errors"]["permission"]
                _assert_no_sensitive_payload(denied_payload)

    print("Check tranche 16A backup API OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
