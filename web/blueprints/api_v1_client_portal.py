"""API JSON App V2 per Portale Cliente."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, jsonify, request, send_file

from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from web.services.react_client_portal_bridge import (
    accept_invite_token,
    build_studio_dashboard_payload,
    client_complete_signature,
    client_dashboard_payload,
    client_document_download,
    client_mark_notification,
    client_send_message,
    client_set_consent,
    client_submit_questionnaire,
    client_submit_survey,
    client_update_appointment,
    client_update_preferences,
    client_update_profile,
    client_upload_document,
    create_invite_from_payload,
    export_conversation,
    invite_preview_payload,
    revoke_invite,
    studio_add_appointment,
    studio_add_document_request,
    studio_add_message,
    studio_add_signature_request,
    studio_create_evidence_pack,
    studio_document_download,
    studio_upload_signature_document,
    update_settings_from_payload,
)
from web.services.tenant_api_auth import api_key_valid_for_request


api_v1_client_portal = Blueprint("api_v1_client_portal", __name__)


def _json_body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return dict(payload) if isinstance(payload, dict) else {}


def _status_for(payload: dict[str, Any]) -> int:
    if payload.get("ok", False):
        return 200
    code = str(payload.get("code") or "")
    return {
        "unauthorized": 401,
        "forbidden": 403,
        "feature_disabled": 403,
        "invalid_invite": 404,
        "validation_error": 422,
    }.get(code, 400)


def _json(payload: dict[str, Any]):
    return jsonify(payload), _status_for(payload)


def _studio_auth_required(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        from flask import g

        if g.get("utente_corrente") or api_key_valid_for_request():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "code": "unauthorized", "message": "Autenticazione richiesta."}), 401

    return wrapper


@api_v1_client_portal.before_request
def _backend_security_guard():
    violations = backend_control_violations_for_request(request)
    if not violations:
        return None
    # Eccezione mirata: il download pubblico del portale clienti riceve il token
    # di sessione in query string perche' viene aperto via <a download> da link
    # condivisi (email/SMS) — non e' possibile impostare header X-... su un click.
    # Il token e' validato lato server contro la tabella client_portal_sessions
    # (vedi client_document_download); resta un parametro di autenticazione,
    # non un controllo server arbitrario.
    if (
        request.method == "GET"
        and "/public/documents/" in request.path
        and request.path.endswith("/download")
    ):
        violations = [v for v in violations if not (v.source == "query" and v.key == "token")]
        if not violations:
            return None
    return backend_security_error_response(violations)


@api_v1_client_portal.get("/dashboard")
@api_v1_client_portal.get("/studio/dashboard")
@_studio_auth_required
def studio_dashboard():
    return _json(build_studio_dashboard_payload())


@api_v1_client_portal.get("/studio/settings")
@_studio_auth_required
def studio_settings():
    payload = build_studio_dashboard_payload()
    return _json({"ok": True, "settings": payload.get("settings", {}), "featureFlags": payload.get("featureFlags", {})})


@api_v1_client_portal.post("/studio/settings")
@_studio_auth_required
def studio_settings_update():
    return _json(update_settings_from_payload(_json_body()))


@api_v1_client_portal.post("/studio/invites")
@_studio_auth_required
def studio_invite_create():
    return _json(create_invite_from_payload(_json_body()))


@api_v1_client_portal.post("/studio/invites/<invite_id>/revoke")
@_studio_auth_required
def studio_invite_revoke(invite_id: str):
    return _json(revoke_invite(invite_id))


@api_v1_client_portal.post("/studio/messages")
@_studio_auth_required
def studio_message_create():
    return _json(studio_add_message(_json_body()))


@api_v1_client_portal.post("/studio/document-requests")
@_studio_auth_required
def studio_document_request_create():
    return _json(studio_add_document_request(_json_body()))


@api_v1_client_portal.post("/studio/signature-requests")
@_studio_auth_required
def studio_signature_request_create():
    return _json(studio_add_signature_request(_json_body()))


@api_v1_client_portal.post("/studio/signature-requests/upload")
@_studio_auth_required
def studio_signature_request_upload():
    file = request.files.get("file")
    payload = {
        "matterId": str(request.form.get("matterId") or ""),
        "title": str(request.form.get("title") or ""),
        "description": str(request.form.get("description") or ""),
        "dueAt": str(request.form.get("dueAt") or ""),
    }
    return _json(studio_upload_signature_document(file, payload))


@api_v1_client_portal.get("/studio/documents/<document_id>/download")
@_studio_auth_required
def studio_document_file(document_id: str):
    result = studio_document_download(document_id)
    if isinstance(result, dict):
        return _json(result)
    path, filename, content_type = result
    return send_file(path, mimetype=content_type, as_attachment=True, download_name=filename)


@api_v1_client_portal.post("/studio/appointments")
@_studio_auth_required
def studio_appointment_create():
    return _json(studio_add_appointment(_json_body()))


@api_v1_client_portal.post("/studio/evidence-packs")
@_studio_auth_required
def studio_evidence_pack_create():
    return _json(studio_create_evidence_pack(_json_body()))


@api_v1_client_portal.get("/studio/conversation-export")
@_studio_auth_required
def studio_conversation_export():
    return _json(export_conversation(str(request.args.get("matterId") or "")))


@api_v1_client_portal.get("/public/invites/<path:token>")
def public_invite_preview(token: str):
    return _json(invite_preview_payload(token))


@api_v1_client_portal.post("/public/invites/<path:token>/accept")
def public_invite_accept(token: str):
    return _json(accept_invite_token(token))


@api_v1_client_portal.get("/public/dashboard")
def public_dashboard():
    return _json(client_dashboard_payload())


@api_v1_client_portal.post("/public/profile")
def public_profile_update():
    return _json(client_update_profile(_json_body()))


@api_v1_client_portal.post("/public/preferences")
def public_preferences_update():
    return _json(client_update_preferences(_json_body()))


@api_v1_client_portal.post("/public/consents")
def public_consent_update():
    return _json(client_set_consent(_json_body()))


@api_v1_client_portal.post("/public/messages")
def public_message_create():
    return _json(client_send_message(_json_body()))


@api_v1_client_portal.post("/public/documents")
def public_document_upload():
    file = request.files.get("file")
    if file is None:
        return _json({"ok": False, "code": "validation_error", "message": "File richiesto."})
    return _json(client_upload_document(file, request_id=str(request.form.get("requestId") or "")))


@api_v1_client_portal.get("/public/documents/<document_id>/download")
def public_document_file(document_id: str):
    result = client_document_download(document_id, token=str(request.args.get("token") or ""))
    if isinstance(result, dict):
        return _json(result)
    path, filename, content_type = result
    return send_file(path, mimetype=content_type, as_attachment=True, download_name=filename)


@api_v1_client_portal.post("/public/signatures/<signature_id>/complete")
def public_signature_complete(signature_id: str):
    return _json(client_complete_signature(signature_id, _json_body()))


@api_v1_client_portal.post("/public/appointments/<appointment_id>")
def public_appointment_update(appointment_id: str):
    return _json(client_update_appointment(appointment_id, _json_body()))


@api_v1_client_portal.post("/public/notifications/<notification_id>/read")
def public_notification_read(notification_id: str):
    return _json(client_mark_notification(notification_id))


@api_v1_client_portal.post("/public/questionnaires/<questionnaire_id>")
def public_questionnaire_submit(questionnaire_id: str):
    return _json(client_submit_questionnaire(questionnaire_id, _json_body()))


@api_v1_client_portal.post("/public/surveys")
def public_survey_submit():
    return _json(client_submit_survey(_json_body()))


@api_v1_client_portal.get("/public/conversation-export")
def public_conversation_export():
    token = str(request.headers.get("X-Client-Portal-Token") or "")
    return _json(export_conversation(str(request.args.get("matterId") or ""), token=token))
