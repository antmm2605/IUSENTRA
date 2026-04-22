from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pct.auth import GestioneUtenti
from web.app import create_app
from web.services.support_runtime import support_repository
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

    assert response.status_code == 200
    assert "Assistenza remota cliente" in response.get_data(as_text=True)


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

    assert join_page.status_code == 200
    assert "Assistenza remota con consenso esplicito" in join_page.get_data(as_text=True)
    assert state.status_code == 200
    assert state.get_json()["session"]["public_id"] == public_id


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


def test_support_remote_escalation_requires_advanced_template(tmp_path: Path):
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

        escalation_response = client.post(
            f"/support/api/{public_id}/escalation?role=operator",
            json={"action": "request"},
        )

    assert escalation_response.status_code == 409
    assert "Controllo remoto avanzato non configurato" in escalation_response.get_data(as_text=True)
