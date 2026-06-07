from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
import base64
import hashlib
import hmac
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import pct.support_remote as support_remote
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
from web.services.support_runtime import _platform_notification_repository, support_repository
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


def test_support_remote_repository_uses_explicit_utc_timestamps(tmp_path: Path):
    app, _, _, _ = _seed_runtime(tmp_path)

    with app.app_context():
        repo = support_repository()
        row = repo.create_session(
            {
                "customer_name": "Cliente orario UTC",
                "practice_label": "Verifica ora italiana",
                "studio_nome": "Studio orario",
            }
        )
        assert row["created_at"].endswith("+00:00")
        assert row["updated_at"].endswith("+00:00")

        public_id = row["public_id"]
        with repo._connect() as conn:
            conn.execute(
                "UPDATE support_session SET updated_at = ? WHERE public_id = ?",
                ("2026-05-31 21:05:00", public_id),
            )
            conn.commit()

        normalized = repo.get_session_by_public_id(public_id)
        assert normalized
        assert normalized["updated_at"] == "2026-05-31T21:05:00+00:00"

        repo.append_event(public_id, event_type="timezone_check", actor_role="test")
        events = repo.list_events(public_id)
        assert events[-1]["created_at"].endswith("+00:00")


def test_support_remote_repository_prioritizes_new_studio_requests(tmp_path: Path):
    app, _, _, _ = _seed_runtime(tmp_path)

    with app.app_context():
        repo = support_repository()
        active = repo.create_session({"customer_name": "Cliente gia attivo", "status": "active"})
        waiting_peer = repo.create_session({"customer_name": "Cliente in attesa altra parte", "status": "waiting_peer"})
        incoming = repo.create_session({"customer_name": "Richiesta studio nuova", "status": "waiting_operator"})
        rows = repo.list_sessions(limit=10)

    assert [rows[0]["public_id"], rows[1]["public_id"], rows[2]["public_id"]] == [
        incoming["public_id"],
        waiting_peer["public_id"],
        active["public_id"],
    ]


def test_support_pc_agent_state_requires_token():
    state = AgentState()

    with pytest.raises(RemoteControlError):
        state.require("sessione-test", "token")

    armed = state.arm("sessione-test", "token", ttl_seconds=60)
    assert armed.session_id == "sessione-test"
    assert armed.allow_control is True
    assert state.active_count() == 1
    assert state.require("sessione-test", "token").token == "token"

    with pytest.raises(RemoteControlError):
        state.require("sessione-test", "sbagliato")

    view_only = state.arm("sessione-solo-schermo", "token-schermo", ttl_seconds=60, allow_control=False)
    assert view_only.allow_control is False
    assert state.require("sessione-solo-schermo", "token-schermo").allow_control is False
    with pytest.raises(RemoteControlError):
        state.require("sessione-solo-schermo", "token-schermo", require_control=True)

    state.disarm("sessione-test", "token")
    state.disarm("sessione-solo-schermo", "token-schermo")
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
        assert arm["control"] is True

        view_code, view = request("/arm", {"session_id": "sessione-http-solo-schermo", "token": "schermo", "control": False})
        assert view_code == 200
        assert view["ok"] is True
        assert view["control"] is False

        view_execute_code, view_execute = request(
            "/execute",
            {
                "session_id": "sessione-http-solo-schermo",
                "token": "schermo",
                "command": {"action": "text", "text": "vietato"},
                "dry_run": True,
            },
        )
        assert view_execute_code == 400
        assert "Controllo PC non autorizzato" in view_execute["error"]

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


def test_support_pc_agent_private_network_preflight_allows_app_origin():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SupportPcAgentRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        req = urllib.request.Request(
            f"{base}/status",
            method="OPTIONS",
            headers={
                "Origin": "https://app.iusentra.it",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        with urllib.request.urlopen(req, timeout=3) as response:  # noqa: S310 - localhost test
            headers = dict(response.headers.items())

        assert headers["Access-Control-Allow-Origin"] == "https://app.iusentra.it"
        assert headers["Access-Control-Allow-Private-Network"] == "true"
        assert "POST" in headers["Access-Control-Allow-Methods"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_support_pc_agent_declares_chrome_edge_loopback_policies():
    origins = [urllib.parse.urlsplit(origin) for origin in support_remote.SUPPORT_PC_AGENT_BROWSER_POLICY_ORIGINS]
    assert any(parsed.scheme == "https" and parsed.netloc == "app.iusentra.it" and parsed.path == "" for parsed in origins)
    assert any("Google\\Chrome\\LoopbackNetworkAllowedForUrls" in item for item in support_remote.SUPPORT_PC_AGENT_BROWSER_POLICY_PATHS)
    assert any("Google\\Chrome\\LocalNetworkAccessAllowedForUrls" in item for item in support_remote.SUPPORT_PC_AGENT_BROWSER_POLICY_PATHS)
    assert any("Microsoft\\Edge\\LoopbackNetworkAllowedForUrls" in item for item in support_remote.SUPPORT_PC_AGENT_BROWSER_POLICY_PATHS)
    assert any("Microsoft\\Edge\\LocalNetworkAccessAllowedForUrls" in item for item in support_remote.SUPPORT_PC_AGENT_BROWSER_POLICY_PATHS)


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
    assert "Percorso reale di assistenza" in html
    assert "Richieste dallo studio" in html
    assert "<summary" in html
    assert "Sessione manuale, solo se il cliente non usa Assistenza" in html
    assert "Impostazioni rete avanzate" in html
    assert "Notifiche cellulare SUPERADMIN" in html
    assert "Cancella prove/test" in html
    assert "Presidio realtime" not in html
    assert "TURN non configurato" not in html

    with app.test_request_context("/admin/supporto-remoto"):
        payload = build_support_console_payload()

    assert payload["ready_now"] is True
    assert payload["warnings"] == []
    assert payload["readiness"]["stun_ready"] is True
    assert payload["runtime_config"]["stun_urls_text"] == "\n".join(default_support_stun_urls())
    assert payload["push_status"]["configured"] is False


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
    assert "token=" in payload["operator_url"]
    assert operator_room.status_code == 200
    assert 'id="support-operator-react-root"' in operator_room.get_data(as_text=True)


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
        state_with_events = client.get(f"/support/api/{public_id}/state?role=client&token={client_token}&events=1")
        webrtc = client.get(f"/support/api/{public_id}/webrtc-config?role=client&token={client_token}")

    assert join_page.status_code == 200
    assert "Assistenza remota con consenso esplicito" in join_page.get_data(as_text=True)
    assert state.status_code == 200
    state_payload = state.get_json()
    assert state_payload["session"]["public_id"] == public_id
    assert "events" not in state_payload
    assert state_with_events.status_code == 200
    assert isinstance(state_with_events.get_json()["events"], list)
    assert webrtc.status_code == 200
    assert webrtc.get_json()["rtcConfiguration"]["iceServers"][0]["urls"] == default_support_stun_urls()


def test_support_remote_operator_link_firmato_apre_stanza_react_senza_login(tmp_path: Path):
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
                "customer_name": "Cliente token operatore",
                "customer_email": "cliente-token@example.it",
            },
        )
        payload = create_response.get_json()
        operator_url = payload["operator_url"]

        with client.session_transaction() as session_tx:
            session_tx.clear()

        operator_room = client.get(operator_url)
        no_token = client.get(f"/support/operatore/{payload['session']['public_id']}")

    assert create_response.status_code == 200
    assert "token=" in operator_url
    assert operator_room.status_code == 200
    html = operator_room.get_data(as_text=True)
    assert 'id="support-operator-react-root"' in html
    assert "window.SUPPORT_BOOTSTRAP" in html
    assert no_token.status_code == 302
    assert "/login" in no_token.headers["Location"]


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
        customer_state_after_operator = client.get(
            f"/support/api/{public_id}/state?role=client&token={client_token}"
        )

    assert dashboard.status_code == 200
    dashboard_html = dashboard.get_data(as_text=True)
    assert 'id="iusentra-react-bootstrap"' in dashboard_html
    assert "/static/js/support_launch.js" in dashboard_html
    assert 'data-support-endpoint="{{ url_for(\'support_remote.create_studio_session_api\') }}"' in Path(
        "web/templates/base.html"
    ).read_text(encoding="utf-8")
    topbar_source = Path("frontend/src/components/layout/TopBar.tsx").read_text(encoding="utf-8")
    assert "requestSupport" in topbar_source
    assert "fetch('/support/studio/sessione'" in topbar_source
    assert "window.location.assign(String(payload.join_url))" in topbar_source
    assert "Richiedi assistenza remota" in topbar_source
    assert "data-support-launch" not in topbar_source
    assert request_response.status_code == 200
    assert payload["ok"] is True
    assert payload["customer_entry"] is True
    assert payload["session"]["studio_slug"] == studio.slug
    assert payload["session"]["practice_label"] == "Panoramica dello studio"
    assert payload["join_url"].endswith(client_token)
    assert payload["notification"]["created"] == 1
    assert payload["notification"]["push_configured"] is False
    assert join_page.status_code == 200
    join_html = join_page.get_data(as_text=True)
    assert "Assistenza remota con consenso esplicito" in join_html
    assert "Richiesta visualizzata dal SUPERADMIN" in join_html
    assert 'id="customerFullscreenBtn"' in join_html
    assert 'id="compactChatBtn"' in join_html
    assert 'id="localAgentPreview"' not in join_html
    assert 'id="localPreview"' not in join_html
    assert 'id="customerScreenPanel"' in join_html
    assert 'id="customerChatPanel">\n        <div class="card-header fw-semibold">\n          <i class="bi bi-chat-dots' in join_html
    assert 'id="startBtn" type="button" disabled' in join_html
    assert "support-customer-shell--fullscreen" in join_html
    assert "support-customer-chat--compact" in join_html
    assert console.status_code == 200
    console_html = console.get_data(as_text=True)
    assert "Panoramica dello studio" in console_html
    assert "Richiesta assistenza remota" in console_html
    assert "Cambia stato assistenza" in console_html
    assert "Cancella sessione" in console_html
    assert "Prossimo passo: apri la stanza operatore" in console_html
    assert "Prendi in carico" in console_html
    assert 'class="btn btn-sm btn-primary" href="/support/operatore/' in console_html
    assert operator_room.status_code == 200
    assert 'id="support-operator-react-root"' in operator_room.get_data(as_text=True)
    assert customer_state_after_operator.status_code == 200
    assert customer_state_after_operator.get_json()["session"]["status"] == "waiting_client"

    with app.test_client() as start_client:
        with start_client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()
        operator_start = start_client.post(f"/support/api/{public_id}/start?role=operator", json={})
        client_start = start_client.post(
            f"/support/api/{public_id}/start?role=client&token={client_token}",
            json={},
        )
    assert operator_start.status_code == 403
    assert client_start.status_code == 200
    assert client_start.get_json()["session"]["status"] == "active"

    with app.app_context():
        events = support_repository().list_events(public_id)
        platform_notifications = _platform_notification_repository().list_notifications("default", str(superadmin.id))
    serialized_notifications = json.dumps([record.to_db() for record in platform_notifications], ensure_ascii=False)
    assert "Richiesta assistenza remota" in serialized_notifications
    assert studio.nome in serialized_notifications
    assert f"/admin/supporto-remoto?sessione={public_id}" in serialized_notifications
    assert any(event["event_type"] == "studio_support_requested" for event in events)


def test_support_remote_console_can_manage_status_delete_and_cleanup_tests(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        first = client.post("/support/api/session", json={"customer_name": "Cliente prova cleanup", "practice_label": "E2E prova"})
        keep = client.post("/support/api/session", json={"customer_name": "Cliente operativo", "practice_label": "Assistenza ordinaria"})
        first_id = first.get_json()["session"]["public_id"]
        keep_id = keep.get_json()["session"]["public_id"]

        changed = client.post(
            f"/admin/supporto-remoto/{first_id}/stato",
            json={"status": "closed"},
        )
        deleted_one = client.post(f"/admin/supporto-remoto/{keep_id}/cancella", json={})
        cleanup = client.post("/admin/supporto-remoto/prove/cancella", json={})

    assert changed.status_code == 200
    assert changed.get_json()["session"]["status"] == "closed"
    assert deleted_one.status_code == 200
    assert deleted_one.get_json()["deleted"] == 1
    assert cleanup.status_code == 200
    assert cleanup.get_json()["deleted"] == 1

    with app.app_context():
        repo = support_repository()
        assert repo.get_session_by_public_id(first_id) is None
        assert repo.get_session_by_public_id(keep_id) is None


def test_support_remote_superadmin_push_configuration_endpoints(tmp_path: Path, monkeypatch):
    app, superadmin, _, _ = _seed_runtime(tmp_path)
    app.config.update(
        IUSENTRA_WEB_PUSH_ENABLED="1",
        IUSENTRA_VAPID_PUBLIC_KEY="public-key",
        IUSENTRA_VAPID_PRIVATE_KEY="private-key",
        IUSENTRA_VAPID_SUBJECT="mailto:admin@example.com",
    )
    sent_payloads = []

    def fake_webpush(**kwargs):
        sent_payloads.append(json.loads(kwargs["data"]))

    from pct.notifications import web_push

    monkeypatch.setattr(web_push, "pywebpush", type("WebPush", (), {"webpush": staticmethod(fake_webpush)}))

    with app.test_client() as client:
        with client.session_transaction() as session_tx:
            session_tx["user_id"] = superadmin.id
            session_tx["auth_scope"] = "global"
            session_tx["auth_tenant_slug"] = ""
            session_tx["last_activity"] = datetime.now().isoformat()

        status = client.get("/admin/supporto-remoto/notifiche-dispositivo")
        subscribed = client.post(
            "/admin/supporto-remoto/notifiche-dispositivo/subscribe",
            json={
                "endpoint": "https://push.example/superadmin",
                "keys": {"p256dh": "p256dh", "auth": "auth"},
                "deviceLabel": "Telefono SUPERADMIN",
            },
        )
        test = client.post("/admin/supporto-remoto/notifiche-dispositivo/test", json={})

    assert status.status_code == 200
    assert status.get_json()["configured"] is True
    assert subscribed.status_code == 200
    assert subscribed.get_json()["active"] is True
    assert test.status_code == 200
    assert test.get_json()["sent"] == 1
    assert sent_payloads[0]["title"] == "IUSENTRA Assistenza"
    assert sent_payloads[0]["body"] == "Richiesta assistenza da Studio test IUSENTRA."


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
    assert 'id="support-operator-react-root"' in html
    assert 'data-support-operator-room="1"' in html
    assert "window.SUPPORT_BOOTSTRAP" in html
    assert "/static/react/" in html
    assert "support_operator_room.js" not in html
    operator_component = Path("frontend/src/components/SupportOperatorRoom.tsx").read_text(encoding="utf-8")
    assert "Stanza operatore" in operator_component
    assert "Richiedi controllo PC" in operator_component
    assert 'id="remoteAudio"' in operator_component
    assert 'id="operatorMuteMicBtn"' in operator_component
    assert "Muta microfono" in operator_component


def test_support_remote_pc_control_scripts_and_agent_are_separate_from_local_signer():
    operator_script = Path("web/static/js/support_operator_room.js").read_text(encoding="utf-8")
    customer_script = Path("web/static/js/support_customer_room.js").read_text(encoding="utf-8")
    agent_source = Path("pct/support_remote.py").read_text(encoding="utf-8")
    local_signer = Path("tools/local_signer.py").read_text(encoding="utf-8")

    assert 'type: "remote_control"' in operator_script
    assert 'message.type === "remote_control"' in customer_script
    assert 'fetchAgent("/arm"' in customer_script
    assert 'fetchAgent("/screenshot"' in customer_script
    assert "screen_frame" in operator_script
    assert "screen_frame" in customer_script
    assert "remoteDisplayedRect" in operator_script
    assert "remoteFrameMeta" in operator_script
    assert "remoteFrameMeta = {" in operator_script
    assert "getUserMedia({ audio: true, video: false })" in customer_script
    assert "Microfono non autorizzato o non disponibile sul PC: assistenza avviata senza audio." in customer_script
    assert "Microfono non disponibile: assistenza avviata senza audio." in customer_script
    assert "return [];" in customer_script
    assert "localStream = audioTracks.length ? new MediaStream(audioTracks) : null" in customer_script
    assert "Agente IUSENTRA Assistenza non raggiungibile" in customer_script
    assert "getDisplayMedia" not in customer_script
    assert 'targetAddressSpace: "loopback"' in customer_script
    assert "await startAgentScreenShare();" in customer_script
    assert "wsOpenPromise = new Promise" in customer_script
    assert "Canale realtime chiuso prima della connessione." in customer_script
    assert "function toggleCustomerMicrophone()" in customer_script
    assert "tracks.length > 0 || Boolean(consentAudio?.checked)" in customer_script
    assert "Microfono cliente disattivato all'avvio" in customer_script
    assert 'consentAudio?.addEventListener("change"' in customer_script
    assert "track.enabled = !customerMicMuted" in customer_script
    assert "Microfono cliente disattivato" in customer_script
    assert 'pc.addTransceiver("audio", { direction: "recvonly" })' in operator_script
    assert 'pc.addTransceiver("video", { direction: "recvonly" })' in operator_script
    assert 'const remoteAudio = $("remoteAudio")' in operator_script
    assert "function toggleOperatorMicrophone()" in operator_script
    assert "tracks.length > 0 || Boolean(operatorMic?.checked)" in operator_script
    assert "Microfono operatore non disponibile: assistenza avviata senza audio" in operator_script
    assert "wsOpenPromise = new Promise" in operator_script
    assert "Canale realtime chiuso prima della connessione." in operator_script
    assert 'fetchJson(apiUrl("/start")' not in operator_script
    assert "statePollDelayMs = 12000" in operator_script
    assert "stateUrl()" in operator_script
    assert "stateSyncInFlight" in operator_script
    assert "remoteCommandQueue" in operator_script
    assert "flushRemoteCommandQueue" in operator_script
    assert "handleRemoteControlAck" in operator_script
    assert "remoteCommandAckTimeoutMs = 10000" in operator_script
    assert "document.hidden) return" not in operator_script
    assert "document.hidden) return" not in customer_script
    assert "Microfono operatore disattivato all'avvio" in operator_script
    assert 'operatorMic?.addEventListener("change"' in operator_script
    assert "track.enabled = !operatorMicMuted" in operator_script
    assert "Microfono operatore disattivato" in operator_script
    assert "allow_control: bool" in agent_source
    assert "await connectWs();" in customer_script
    assert 'id="support-operator-react-root"' in Path("web/templates/support/operator_room.html").read_text(encoding="utf-8")
    assert "SupportOperatorRoom" in Path("frontend/src/main.tsx").read_text(encoding="utf-8")
    assert "IUSENTRA Support Remote Agent" in agent_source
    assert "SetCursorPos" in agent_source
    assert "SendInput" in agent_source
    assert "/remote-control/execute" not in local_signer
    assert "SupportPcAgentRequestHandler" not in local_signer


def test_support_remote_pc_click_uses_virtual_desktop_origin(monkeypatch):
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(support_remote, "_support_pc_is_windows", lambda: True)
    monkeypatch.setattr(
        support_remote,
        "_support_pc_virtual_screen_geometry",
        lambda: {"x": -1920, "y": 0, "width": 3840, "height": 1080},
    )
    monkeypatch.setattr(support_remote, "_support_pc_move_pointer", lambda x, y: calls.append(("move", x, y)))
    monkeypatch.setattr(
        support_remote,
        "_support_pc_click",
        lambda button="left", double=False: calls.append(("click", button, double)),
    )

    result = execute_command({"action": "click", "x_ratio": 0.75, "y_ratio": 0.5})

    assert result == {"ok": True, "action": "click"}
    assert calls == [("move", 959, 539), ("click", "left", False)]


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
    customer_script = Path("web/static/js/support_customer_room.js").read_text(encoding="utf-8")
    customer_page = Path("web/templates/support/customer_room.html").read_text(encoding="utf-8")

    assert "payload.customer_entry" in script
    assert "Apri stanza cliente" in script
    assert "Richiesta inviata al SUPERADMIN" in script
    assert "function showSupportModal()" in script
    assert "modal.style.display = \"block\"" in script
    assert 'button.dataset.supportEndpoint || "/support/api/session"' in script
    assert 'id="takeChargeNotice"' in customer_page
    assert 'id="customerFullscreenBtn"' in customer_page
    assert 'id="compactChatBtn"' in customer_page
    assert 'id="customerMuteMicBtn"' in customer_page
    assert 'id="customerScreenPanel"' in customer_page
    assert 'id="customerChatPanel"' in customer_page
    assert 'id="customerChatPanel">\n        <div class="card-header fw-semibold">\n          <i class="bi bi-chat-dots' in customer_page
    assert "Richiesta visualizzata dal SUPERADMIN" in customer_page
    assert "support-customer-shell--fullscreen" in customer_page
    assert "support-customer-chat--compact" in customer_page
    assert "setTakeChargeNotice(session)" in customer_script
    assert "startBtn.disabled = !canStart" in customer_script
    assert "toggleCustomerFullscreen" in customer_script
    assert "toggleCompactChat" in customer_script
    assert "toggleCustomerMicrophone" in customer_script
    assert "statePollDelayMs = 12000" in customer_script
    assert "stateUrl()" in customer_script
    assert "stateSyncInFlight" in customer_script
    assert "window.setInterval(syncState, statePollDelayMs)" in customer_script
