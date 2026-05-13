from __future__ import annotations

from flask import Flask, g

from audit.routes import audit_blueprint
from audit.hashing import sha256_bytes

from tests.audit_test_utils import emit_sample_event, make_service


class _User:
    def ha_permesso(self, permission: str) -> bool:
        return permission in {"audit.leggi", "audit.esporta"}


def _app_with_service(service):
    app = Flask(__name__)
    app.testing = True
    app.extensions["legal_audit_service"] = service

    @app.before_request
    def _inject_context():
        g.tenant_context_slug = "tenant-a"
        g.utente_corrente = _User()

    app.register_blueprint(audit_blueprint)
    return app


def _app_without_tenant(service):
    app = Flask(__name__)
    app.testing = True
    app.extensions["legal_audit_service"] = service

    @app.before_request
    def _inject_context():
        g.utente_corrente = _User()

    app.register_blueprint(audit_blueprint)
    return app


def _app_without_audit_config(tmp_path):
    app = Flask(__name__)
    app.testing = True
    app.config["PCT_DATA_ROOT"] = str(tmp_path)

    @app.before_request
    def _inject_context():
        g.tenant_context_slug = "tenant-a"
        g.utente_corrente = _User()

    app.register_blueprint(audit_blueprint)
    return app


def test_audit_events_route_is_tenant_scoped(tmp_path) -> None:
    service, _public = make_service()
    event = emit_sample_event(service, tmp_path, idempotency_key="route-1")
    response = _app_with_service(service).test_client().get("/audit/events?fascicolo_id=FASC-1")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["tenant_id"] == "tenant-a"
    assert payload["items"][0]["event_id"] == event.event_id
    assert "payload" not in payload["items"][0]


def test_registro_alias_routes_expose_events_and_bundle(tmp_path) -> None:
    service, _public = make_service()
    event = emit_sample_event(service, tmp_path, idempotency_key="registro-alias")
    client = _app_with_service(service).test_client()

    events_response = client.get("/registro/events?fascicolo_id=FASC-1")
    assert events_response.status_code == 200
    assert events_response.get_json()["items"][0]["event_id"] == event.event_id

    proof_response = client.get(f"/registro/proof/{event.event_id}")
    assert proof_response.status_code == 200
    assert proof_response.get_json()["event"]["event_id"] == event.event_id

    bundle_response = client.get("/registro/bundle/fascicolo/FASC-1")
    assert bundle_response.status_code == 200
    assert bundle_response.mimetype == "application/zip"


def test_registro_bundle_alias_returns_controlled_error_when_worm_not_configured(tmp_path) -> None:
    response = _app_without_audit_config(tmp_path).test_client().get("/registro/bundle/fascicolo/FASC-1")
    assert response.status_code == 503
    assert response.get_json()["code"] == "audit_config_error"


def test_audit_events_route_fails_closed_without_tenant_context(tmp_path) -> None:
    service, _public = make_service()
    emit_sample_event(service, tmp_path, idempotency_key="route-missing-tenant")
    response = _app_without_tenant(service).test_client().get("/audit/events?fascicolo_id=FASC-1")
    assert response.status_code == 403
    assert response.get_json()["code"] == "tenant_required"


def test_internal_emit_requires_internal_auth(tmp_path) -> None:
    service, _public = make_service()
    response = _app_with_service(service).test_client().post("/internal/audit/emit", json={})
    assert response.status_code == 403


def test_internal_emit_accepts_testing_bypass_and_idempotency(tmp_path) -> None:
    service, _public = make_service()
    digest = sha256_bytes(b"eml")
    payload = {
        "kind": "PEC_SENT",
        "tenant_id": "tenant-a",
        "fascicolo_id": "FASC-1",
        "actor": {"actor_id": "svc", "actor_type": "service"},
        "payload": {
            "message_id": "msg-1",
            "sender_ref": "casella-studio",
            "recipients_hashes": [sha256_bytes(b"destinatario")],
            "subject_hash": sha256_bytes(b"oggetto"),
            "sent_at": "2026-05-13T10:00:00Z",
        },
        "files": [{"label": "eml", "storage_ref": "pec://msg-1", "sha256": digest, "size_bytes": 3, "mime": "message/rfc822"}],
        "source": {"service": "iusentra", "module": "pec", "request_id": "route-emit"},
        "idempotency_key": "route-emit-1",
    }
    response = _app_with_service(service).test_client().post(
        "/internal/audit/emit",
        json=payload,
        headers={"X-Audit-Test-Bypass": "1"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert service.repository.get_event(body["event_id"], tenant_id="tenant-a")
