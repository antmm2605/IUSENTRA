from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "client-portal-test-key"
    return app


def _seed_cliente_fascicolo(app):
    with app.app_context():
        clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
        cliente = clienti.nuovo(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Mario",
            cognome="Rossi",
            codice_fiscale="RSSMRA80A01H501U",
        )
        clienti.aggiorna_recapiti(cliente.id, email="mario.rossi@example.it", cellulare="3331234567")
        fascicoli = GestioneFascicoli(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )
        fascicolo = fascicoli.nuovo(
            "Pratica responsabilità contrattuale",
            TipoFascicolo.CIVILE,
            id_cliente=cliente.id,
            nome_cliente=cliente.nome_completo,
        )
    return cliente, fascicolo


def _create_invite(client, cliente_id: str, fascicolo_id: str) -> tuple[str, dict]:
    response = client.post(
        "/api/v1/ui/client-portal/studio/invites",
        json={"clientId": cliente_id, "matterId": fascicolo_id, "expiresDays": 7},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["inviteUrl"].startswith("http://localhost/portale-cliente/invito/")
    token = payload["inviteUrl"].rsplit("/", 1)[-1]
    return token, payload


def test_client_portal_studio_api_richiede_login(tmp_path: Path):
    app = _app(tmp_path)

    with app.test_client() as client:
        response = client.get("/api/v1/ui/client-portal/dashboard")

    assert response.status_code == 401
    assert response.get_json()["code"] == "unauthorized"


def test_client_portal_blocca_tenant_id_anche_autenticato(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/client-portal/studio/invites",
            json={"clientId": "CLI", "matterId": "FASC", "tenant_id": "studio-b"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["code"] == "backend_security_control_param"
    assert "tenant_id" in {item["key"] for item in payload["violations"]}
    assert "studio-b" not in response.get_data(as_text=True)


def test_client_portal_non_propone_fascicoli_di_prova(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, _fascicolo = _seed_cliente_fascicolo(app)
    with app.app_context():
        fascicoli = GestioneFascicoli(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )
        fascicolo_prova = fascicoli.nuovo(
            "Procedimento penale demo",
            TipoFascicolo.PENALE,
            id_cliente=cliente.id,
            nome_cliente=cliente.nome_completo,
        )

    with app.test_client() as client:
        _login(client)
        dashboard = client.get("/api/v1/ui/client-portal/dashboard")
        create = client.post(
            "/api/v1/ui/client-portal/studio/invites",
            json={"clientId": cliente.id, "matterId": fascicolo_prova.id, "expiresDays": 7},
        )

    assert dashboard.status_code == 200
    labels = [item["label"].lower() for item in dashboard.get_json()["matterOptions"]]
    assert "pratica responsabilità contrattuale" in labels
    assert all("demo" not in label for label in labels)
    assert create.status_code == 422
    assert create.get_json()["code"] == "validation_error"


def test_client_portal_invito_associa_fascicolo_del_cliente_se_unico(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/client-portal/studio/invites",
            json={"clientId": cliente.id, "expiresDays": 7},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["invite"]["matter_id"]
    assert payload["dashboard"]["matters"][0]["fascicolo_id"] == fascicolo.id
    assert payload["inviteUrl"].startswith("http://localhost/portale-cliente/invito/")


def test_client_portal_videocall_visibile_e_validata(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        token, invite_payload = _create_invite(client, cliente.id, fascicolo.id)
        matter_id = invite_payload["invite"]["matter_id"]

        missing_date = client.post(
            "/api/v1/ui/client-portal/studio/appointments",
            json={"matterId": matter_id, "videoUrl": "https://meet.example.test/studio/rossi"},
        )
        assert missing_date.status_code == 422
        assert missing_date.get_json()["message"] == "Indica data e ora dell'appuntamento."

        invalid = client.post(
            "/api/v1/ui/client-portal/studio/appointments",
            json={"matterId": matter_id, "startsAt": "2026-06-08T10:00", "videoUrl": "javascript:alert(1)"},
        )
        assert invalid.status_code == 422
        assert invalid.get_json()["code"] == "validation_error"

        appointment = client.post(
            "/api/v1/ui/client-portal/studio/appointments",
            json={
                "matterId": matter_id,
                "startsAt": "2026-06-08T10:00",
                "videoUrl": "https://meet.example.test/studio/rossi",
            },
        )
        appointment_payload = appointment.get_json()
        assert appointment.status_code == 200
        assert appointment_payload["ok"] is True
        assert appointment_payload["item"]["starts_at"] == "2026-06-08T08:00:00+00:00"
        assert appointment_payload["item"]["starts_at_label"] == "08/06/2026 10:00"
        assert appointment_payload["item"]["video_url"] == "https://meet.example.test/studio/rossi"

        accepted = client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})
        assert accepted.status_code == 200
        dashboard = client.get(
            "/api/v1/ui/client-portal/public/dashboard",
            headers={"X-Client-Portal-Token": token},
        )

    payload = dashboard.get_json()
    assert dashboard.status_code == 200
    assert payload["appointments"][0]["starts_at_label"] == "08/06/2026 10:00"
    assert payload["appointments"][0]["video_url"] == "https://meet.example.test/studio/rossi"


def test_client_portal_invito_cliente_chat_upload_e_consenso(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)

    with app.test_client() as client:
        _login(client)
        token, invite_payload = _create_invite(client, cliente.id, fascicolo.id)

        portal_db = tmp_path / "client_portal" / "client_portal.db"
        with sqlite3.connect(portal_db) as conn:
            rows = conn.execute("SELECT token_hash FROM client_portal_invites").fetchall()
        assert rows
        assert token not in portal_db.read_text(encoding="latin-1", errors="ignore")
        assert "token_hash" not in str(invite_payload)

        preview = client.get(f"/api/v1/ui/client-portal/public/invites/{token}")
        assert preview.status_code == 200
        assert preview.get_json()["ok"] is True
        assert preview.get_json()["matter"]["title"] == "Pratica responsabilità contrattuale"

        accepted = client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})
        assert accepted.status_code == 200
        assert accepted.get_json()["ok"] is True

        dashboard = client.get(
            "/api/v1/ui/client-portal/public/dashboard",
            headers={"X-Client-Portal-Token": token},
        )
        payload = dashboard.get_json()
        assert dashboard.status_code == 200
        assert payload["ok"] is True
        assert payload["client"]["display_name"] == "Rossi Mario"
        assert payload["activityCenter"]["openItems"] >= 1

        consent = client.post(
            "/api/v1/ui/client-portal/public/consents",
            json={"key": "privacy_portale_cliente", "accepted": True},
            headers={"X-Client-Portal-Token": token},
        )
        assert consent.status_code == 200
        assert consent.get_json()["ok"] is True

        message = client.post(
            "/api/v1/ui/client-portal/public/messages",
            json={"body": "Buongiorno studio, ho caricato il documento."},
            headers={"X-Client-Portal-Token": token},
        )
        assert message.status_code == 200
        assert message.get_json()["ok"] is True

        request_id = payload["documentRequests"][0]["id"]
        upload = client.post(
            "/api/v1/ui/client-portal/public/documents",
            data={
                "requestId": request_id,
                "file": (io.BytesIO(b"%PDF-1.4\ncontenuto"), "../../carta-identita.pdf"),
            },
            content_type="multipart/form-data",
            headers={"X-Client-Portal-Token": token},
        )
        upload_payload = upload.get_json()
        assert upload.status_code == 200
        assert upload_payload["ok"] is True
        assert upload_payload["item"]["filename"] == "carta-identita.pdf"
        assert "stored_name" not in upload_payload["item"]
        assert ".." not in str(upload_payload)
        with sqlite3.connect(portal_db) as conn:
            stored_name = conn.execute("SELECT stored_name FROM client_portal_documents").fetchone()[0]
        assert stored_name.endswith("_carta-identita.pdf")
        assert ".." not in stored_name
        assert "/" in stored_name


def test_client_portal_shell_studio_e_cliente(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        public = client.get("/portale-cliente")
        studio_without_login = client.get("/app/portale-clienti")
        _login(client)
        studio = client.get("/app/portale-clienti")

    assert public.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in public.get_data(as_text=True)
    assert "react-shell-page--client-portal-public" in public.get_data(as_text=True)
    assert studio_without_login.status_code in {302, 303}
    assert "/login" in studio_without_login.headers["Location"]
    assert studio.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in studio.get_data(as_text=True)
    assert "react-shell-page--client-portal-studio" in studio.get_data(as_text=True)
