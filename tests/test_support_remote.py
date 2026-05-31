from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import base64
import hashlib
import hmac
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from pct.auth import GestioneUtenti
from pct.support_remote import (
    AgentState,
    RemoteControlError,
    SupportPcAgentRequestHandler,
    build_ice_servers,
    default_support_stun_urls,
    execute_command,
)
from web.app import create_app
from web.services.support_runtime import support_repository
from web.services.support_surface import build_support_console_payload
from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config


def _seed_platform_superadmin(app):
    utenti = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=True,
    )
    return utenti.ensure_platform_superadmin() or utenti.get_by_username("admin")


def _seed_runtime(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    superadmin = _seed_platform_superadmin(app)
    studio, tenant_admin = _seed_tenant_admin(app)
    return app, superadmin, studio, tenant_admin


def test_support_pc_agent_state_requires_token():
    state = AgentState()

    with pytest.raises(RemoteControlError):
        state.require("sessione-test", "token")

    armed = state.arm("sessione-test", "token", ttl_seconds=60)
    assert armed.session_id == "sessione-test"
    assert state.active_count() == 1
    assert state.require("sessione-test", "token").token == "token"

    with pytest.raises(RemoteControlError):
        state.require("sessione-test", "sbagliato")

    state.disarm("sessione-test", "token")
    assert state.active_count() == 0


def test_support_pc_agent_execute_dry_run_validates_actions():
    assert execute_command({"action": "click"}, dry_run=True)["action"] == "click"
    assert execute_command({"action": "text", "text": "IUSENTRA"}, dry_run=True)["dry_run"] is True

    with pytest.raises(RemoteControlError):
        execute_command({}, dry_run=True)


def test_support_pc_agent_http_arm_execute_and_reject_wrong_token():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SupportPcAgentRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def request(path: str, payload: dict | None = None) -> tuple[int, dict]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{base}{path}",
            data=data,
            method="POST" if payload is not None else "GET",
            headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:8080"},
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as response:  # noqa: S310 - localhost test
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    try:
        status_code, status = request("/status")
        assert status_code == 200
        assert status["agent"] == "IUSENTRA Support Remote Agent"

        arm_code, arm = request("/arm", {"session_id": "sessione-http-test", "token": "segreto"})
        assert arm_code == 200
        assert arm["ok"] is True

        wrong_code, wrong = request(
            "/execute",
            {
                "session_id": "sessione-http-test",
                "token": "token-sbagliato",
                "command": {"action": "click"},
                "dry_run": True,
            },
        )
        assert wrong_code == 400
        assert "Token PC non valido" in wrong["error"]

        execute_code, executed = request(
            "/execute",
            {
                "session_id": "sessione-http-test",
                "token": "segreto",
                "command": {"action": "text", "text": "IUSENTRA"},
                "dry_run": True,
            },
        )
        assert execute_code == 200
        assert executed["ok"] is True
        assert executed["action"] == "text"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_support_remote_console_and_routes_register_on_runtime(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    assert "support_remote" in app.blueprints
    assert app.extensions.get("support_remote_ws_registered") is True

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        response = client.get("/admin/supporto-remoto")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Assistenza remota cliente" in html
    assert "Pronta per assistenza immediata" in html
    assert "TURN non configurato" not in html

    with app.test_request_context("/admin/supporto-remoto"):
        payload = build_support_console_payload()

    assert payload["ready_now"] is True
    assert payload["warnings"] == []
    assert payload["readiness"]["stun_ready"] is True
    assert payload["runtime_config"]["stun_urls_text"] == "\n".join(default_support_stun_urls())


def test_support_remote_create_session_allows_impersonating_superadmin(tmp_path: Path):
    app, superadmin, studio, tenant_admin = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = tenant_admin.id
            session_tx["tenant_slug"] = studio.slug
            session_tx["auth_scope"] = "tenant"
            session_tx["auth_tenant_slug"] = studio.slug
            session_tx["superadmin_user_id"] = superadmin.id
            session_tx["last_activity"] = datetime.now().isoformat()

        response = client.post(
            "/support/api/session",
            json={
                "customer_name": "Mario Rossi",
                "customer_email": "mario.rossi@example.it",
                "practice_id": "fasc-001",
                "practice_label": "RG 1025/2024 - Vendita immobili",
                "client_id": "cli-001",
            },
        )
        operator_room = client.get(f"/support/operatore/{response.get_json()['session']['public_id']}")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["session"]["studio_slug"] == studio.slug
    assert payload["session"]["customer_name"] == "Mario Rossi"
    assert payload["join_url"].endswith(payload["session"]["client_token"])
    assert operator_room.status_code == 200
    assert "Stanza operatore" in operator_room.get_data(as_text=True)


def test_support_remote_customer_link_and_state_work_without_login(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        create_response = client.post(
            "/support/api/session",
            json={
                "customer_name": "Lucia Bianchi",
                "customer_email": "lucia@example.it",
            },
        )
        payload = create_response.get_json()
        public_id = payload["session"]["public_id"]
        client_token = payload["session"]["client_token"]

        join_page = client.get(f"/support/join/{client_token}")
        state = client.get(f"/support/api/{public_id}/state?role=client&token={client_token}")
        webrtc = client.get(f"/support/api/{public_id}/webrtc-config?role=client&token={client_token}")

    assert join_page.status_code == 200
    assert "Assistenza remota con consenso esplicito" in join_page.get_data(as_text=True)
    assert state.status_code == 200
    assert state.get_json()["session"]["public_id"] == public_id
    assert webrtc.status_code == 200
    assert webrtc.get_json()["rtcConfiguration"]["iceServers"][0]["urls"] == default_support_stun_urls()


def test_support_remote_turn_credential_usa_hmac_sha256(tmp_path: Path, monkeypatch):
    app, _, _, _ = _seed_runtime(tmp_path)
    app.config.update(
        SUPPORT_STUN_URLS=[],
        SUPPORT_TURN_URLS=["turn:turn.example.test:3478"],
        SUPPORT_TURN_SHARED_SECRET="turn-secret",
        SUPPORT_TURN_TTL_SECONDS=60,
    )
    monkeypatch.setattr("pct.support_remote.time.time", lambda: 1_800_000_000)

    with app.app_context():
        turn = build_ice_servers("studio@example.it")[-1]

    expected_username = "1800000060:studio@example.it"
    expected_credential = base64.b64encode(
        hmac.new(b"turn-secret", expected_username.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    assert turn["username"] == expected_username
    assert turn["credential"] == expected_credential
    assert len(base64.b64decode(turn["credential"])) == hashlib.sha256().digest_size


def test_support_remote_studio_user_can_request_assistance_from_studio(tmp_path: Path):
    app, superadmin, studio, tenant_admin = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = tenant_admin.id
            session_tx["tenant_slug"] = studio.slug
            session_tx["auth_scope"] = "tenant"
            session_tx["auth_tenant_slug"] = studio.slug
            session_tx["last_activity"] = datetime.now().isoformat()

        dashboard = client.get("/")
        request_response = client.post(
            "/support/studio/sessione",
            json={
                "practice_label": "Panoramica dello studio",
                "notes": "Richiesta aperta dalla barra dello studio.",
            },
        )
        payload = request_response.get_json()
        public_id = payload["session"]["public_id"]
        client_token = payload["session"]["client_token"]
        join_page = client.get(f"/support/join/{client_token}")

        with client.session_transaction() as session_tx:
            session_tx.clear()
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        console = client.get(f"/admin/supporto-remoto?sessione={public_id}")
        operator_room = client.get(f"/support/operatore/{public_id}")

    assert dashboard.status_code == 200
    dashboard_html = dashboard.get_data(as_text=True)
    assert 'id="iusentra-react-bootstrap"' in dashboard_html
    assert "/static/js/support_launch.js" in dashboard_html
    assert 'data-support-endpoint="{{ url_for(\'support_remote.create_studio_session_api\') }}"' in Path(
        "web/templates/base.html"
    ).read_text(encoding="utf-8")
    assert 'data-support-endpoint="/support/studio/sessione"' in Path(
        "frontend/src/components/layout/TopBar.tsx"
    ).read_text(encoding="utf-8")
    assert "Richiedi assistenza remota" in Path("frontend/src/components/layout/TopBar.tsx").read_text(
        encoding="utf-8"
    )
    assert request_response.status_code == 200
    assert payload["ok"] is True
    assert payload["customer_entry"] is True
    assert payload["session"]["studio_slug"] == studio.slug
    assert payload["session"]["practice_label"] == "Panoramica dello studio"
    assert payload["join_url"].endswith(client_token)
    assert join_page.status_code == 200
    assert "Assistenza remota con consenso esplicito" in join_page.get_data(as_text=True)
    assert console.status_code == 200
    assert "Panoramica dello studio" in console.get_data(as_text=True)
    assert operator_room.status_code == 200
    assert "Stanza operatore" in operator_room.get_data(as_text=True)

    with app.app_context():
        events = support_repository().list_events(public_id)
    assert any(event["event_type"] == "studio_support_requested" for event in events)


def test_support_remote_studio_request_requires_login(tmp_path: Path):
    app, _, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        response = client.post("/support/studio/sessione", json={})

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_support_remote_note_update_and_repository_story(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.app_context():
        repo = support_repository()
        row = repo.create_session(
            {
                "customer_name": "Giulia Ferri",
                "customer_email": "giulia@example.it",
                "created_by": "SUPERADMIN",
                "assigned_to": "SUPERADMIN",
            }
        )
        repo.append_event(
            row["public_id"],
            event_type="session_created",
            actor_role="operator",
            actor_name="SUPERADMIN",
            story_line="SUPERADMIN ha aperto una nuova sessione di assistenza remota per Giulia Ferri.",
            payload={"customer_name": "Giulia Ferri"},
        )
        stats = repo.stats()
        events = repo.list_events(row["public_id"])

    assert stats["totale_sessioni"] == 1
    assert events[-1]["story_line"].startswith("SUPERADMIN ha aperto una nuova sessione")

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        response = client.post(
            f"/support/api/{row['public_id']}/note?role=operator",
            json={"notes": "Cliente guidato su sincronizzazione PEC e refresh browser."},
        )

    assert response.status_code == 200
    assert response.get_json()["session"]["notes"] == "Cliente guidato su sincronizzazione PEC e refresh browser."


def test_support_remote_close_sets_end_timestamp(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        create_response = client.post(
            "/support/api/session",
            json={"customer_name": "Cliente Chiusura"},
        )
        payload = create_response.get_json()
        public_id = payload["session"]["public_id"]
        operator_room = client.get(f"/support/operatore/{public_id}")
        assert operator_room.status_code == 200

        close_response = client.post(
            f"/support/api/{public_id}/close?role=operator",
            json={},
        )

    assert close_response.status_code == 200
    closed = close_response.get_json()["session"]
    assert closed["status"] == "closed"
    assert closed["ended_at"]


def test_support_remote_closed_customer_link_is_read_only(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        create_response = client.post(
            "/support/api/session",
            json={"customer_name": "Cliente Link Chiuso"},
        )
        payload = create_response.get_json()
        public_id = payload["session"]["public_id"]
        client_token = payload["session"]["client_token"]

        close_response = client.post(
            f"/support/api/{public_id}/close?role=operator",
            json={},
        )
        join_page = client.get(f"/support/join/{client_token}")

    html = join_page.get_data(as_text=True)
    assert close_response.status_code == 200
    assert join_page.status_code == 200
    assert "Sessione conclusa" in html
    assert "Questo link appartiene a una sessione già chiusa" in html
    assert 'id="startBtn" type="button" disabled' in html
    assert '"closed": true' in html


def test_support_remote_pc_control_request_does_not_require_external_template(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)
    app.config["SUPPORT_ADVANCED_URL_TEMPLATE"] = ""

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        create_response = client.post(
            "/support/api/session",
            json={"customer_name": "Cliente Escalation"},
        )
        payload = create_response.get_json()
        public_id = payload["session"]["public_id"]
        operator_room = client.get(f"/support/operatore/{public_id}")
        assert operator_room.status_code == 200

        request_response = client.post(
            f"/support/api/{public_id}/escalation?role=operator",
            json={"action": "request"},
        )
        approve_response = client.post(
            f"/support/api/{public_id}/escalation?role=client&token={payload['session']['client_token']}",
            json={"action": "approve"},
        )

    assert request_response.status_code == 200
    assert request_response.get_json()["session"]["advanced_control_requested"] is True
    assert approve_response.status_code == 200
    approved = approve_response.get_json()
    assert approved["session"]["advanced_control_approved"] is True
    assert approved["advanced_url"] == ""


def test_support_remote_operator_room_has_full_screen_control_panel(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        create_response = client.post(
            "/support/api/session",
            json={"customer_name": "Cliente Schermo Intero"},
        )
        public_id = create_response.get_json()["session"]["public_id"]
        response = client.get(f"/support/operatore/{public_id}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "support-room--operator" in html
    assert 'id="remoteControlBadge"' in html
    assert 'id="remoteScreen"' in html
    assert 'id="fullscreenBtn"' in html
    assert "Richiedi controllo PC" in html
    assert "Controllo PC" in html


def test_support_remote_pc_control_scripts_and_agent_are_separate_from_local_signer():
    operator_script = Path("web/static/js/support_operator_room.js").read_text(encoding="utf-8")
    customer_script = Path("web/static/js/support_customer_room.js").read_text(encoding="utf-8")
    agent_source = Path("pct/support_remote.py").read_text(encoding="utf-8")
    local_signer = Path("tools/local_signer.py").read_text(encoding="utf-8")

    assert 'type: "remote_control"' in operator_script
    assert 'message.type === "remote_control"' in customer_script
    assert 'fetchAgent("/arm"' in customer_script
    assert "IUSENTRA Support Remote Agent" in agent_source
    assert "SetCursorPos" in agent_source
    assert "SendInput" in agent_source
    assert "/remote-control/execute" not in local_signer
    assert "SupportPcAgentRequestHandler" not in local_signer


def test_support_remote_platform_config_can_be_saved_from_console(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        response = client.post(
            "/admin/supporto-remoto/configurazione",
            data={
                "stun_urls": "stun:turn.example.it:3478",
                "turn_urls": "turn:turn.example.it:3478?transport=udp",
                "turn_shared_secret": "support-secret-demo",
                "turn_ttl_seconds": "7200",
                "ws_token_max_age": "1800",
                "advanced_url_template": "https://support.example.it/advanced/{public_id}",
            },
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert "Configurazione assistenza remota aggiornata." in response.get_data(as_text=True)
    assert app.config["SUPPORT_STUN_URLS"] == ["stun:turn.example.it:3478"]
    assert app.config["SUPPORT_TURN_URLS"] == ["turn:turn.example.it:3478?transport=udp"]
    assert app.config["SUPPORT_TURN_SHARED_SECRET"] == "support-secret-demo"
    assert app.config["SUPPORT_TURN_TTL_SECONDS"] == 7200
    assert app.config["SUPPORT_WS_TOKEN_MAX_AGE"] == 1800
    assert app.config["SUPPORT_ADVANCED_URL_TEMPLATE"] == "https://support.example.it/advanced/{public_id}"

    with app.test_request_context("/admin/supporto-remoto"):
        payload = build_support_console_payload()

    assert "TURN non configurato" not in " ".join(payload["warnings"])
    assert payload["advanced_ready"] is True


def test_support_remote_empty_stun_preserves_ready_default(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        response = client.post(
            "/admin/supporto-remoto/configurazione",
            data={
                "stun_urls": "",
                "turn_urls": "",
                "turn_shared_secret": "",
                "turn_ttl_seconds": "3600",
                "ws_token_max_age": "43200",
                "advanced_url_template": "",
            },
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert app.config["SUPPORT_STUN_URLS"] == default_support_stun_urls()

    with app.test_request_context("/admin/supporto-remoto"):
        payload = build_support_console_payload()

    assert payload["ready_now"] is True
    assert payload["warnings"] == []


def test_support_remote_console_clipboard_failure_non_bloccante():
    script = Path("web/static/js/support_console.js").read_text(encoding="utf-8")

    assert "let clipboardCopied = false" in script
    assert "clipboardCopied = false;" in script
    assert "Link cliente pronto nel campo dedicato" in script
    assert "Impossibile creare la sessione" in script


def test_support_remote_studio_launcher_opens_customer_room():
    script = Path("web/static/js/support_launch.js").read_text(encoding="utf-8")

    assert "payload.customer_entry" in script
    assert "Apri stanza cliente" in script
    assert "Stanza cliente aperta" in script
    assert "function showSupportModal()" in script
    assert "modal.style.display = \"block\"" in script
    assert 'button.dataset.supportEndpoint || "/support/api/session"' in script
