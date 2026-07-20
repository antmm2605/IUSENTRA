from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from flask import Blueprint, Response, jsonify, request

from web.blueprints.api_v1_react import _richiedi_auth
from web.services.notification_presidia_payloads import (
    build_evidence_payload,
    build_presidia_list_payload,
    build_presidio_detail_payload,
    build_transitions_payload,
    evidence_text,
)
from web.services.notification_presidia_runtime import (
    NotificationPresidiaUnavailable,
    assert_notification_presidia_enabled,
    build_notification_presidio_repository,
    current_actor_id,
    legal_notification_presidia_rollout,
    mutate_presidio,
    presidio_permissions,
    public_error,
)
from web.services.tenant_isolation_runtime import TenantIsolationError
from web.services.tenant_paths import TenantDataPathError

api_v1_notification_presidia = Blueprint("api_v1_notification_presidia", __name__)
FORBIDDEN_PUBLIC_BODY_KEYS = {"tenant_id", "studio_id", "filesystem_path", "source_locator", "zip_member_path", "outer_sha256", "eml_sha256"}


def _json_body() -> tuple[dict[str, Any], Any | None]:
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        body, status = public_error("invalid_json", "Payload JSON non valido.", status=400)
        return {}, (jsonify(body), status)
    if any(key in payload for key in FORBIDDEN_PUBLIC_BODY_KEYS):
        body, status = public_error("forbidden_field", "Campo tecnico non ammesso nel payload pubblico.", status=400)
        return {}, (jsonify(body), status)
    return payload, None


def _idempotency_key(mutation: str, presidio_id: str, body: Mapping[str, Any]) -> str:
    header = str(request.headers.get("Idempotency-Key") or "").strip()
    if header:
        return header[:160]
    raw = json.dumps([mutation, presidio_id, current_actor_id(), dict(body)], sort_keys=True, ensure_ascii=False)
    return "ui:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _repo_or_error():
    try:
        assert_notification_presidia_enabled()
        return build_notification_presidio_repository(), None
    except PermissionError as exc:
        body, status = public_error("feature_disabled", str(exc), status=403)
        return None, (jsonify(body), status)
    except (TenantDataPathError, TenantIsolationError):
        body, status = public_error("tenant_context_required", "Contesto studio non disponibile.", status=409)
        return None, (jsonify(body), status)
    except NotificationPresidiaUnavailable:
        body, status = public_error("repository_unavailable", "Registro notifiche legali momentaneamente non disponibile.", status=503)
        return None, (jsonify(body), status)


def _handle_error(exc: Exception):
    if isinstance(exc, PermissionError):
        body, status = public_error("forbidden", str(exc), status=403)
    elif isinstance(exc, KeyError):
        body, status = public_error("not_found", "Presidio non trovato.", status=404)
    elif isinstance(exc, ValueError):
        body, status = public_error("invalid_request", str(exc), status=400)
    elif isinstance(exc, (TenantDataPathError, TenantIsolationError)):
        body, status = public_error("tenant_context_required", "Contesto studio non disponibile.", status=409)
    else:
        body, status = public_error("repository_unavailable", "Operazione notifiche legali non completata.", status=503)
    return jsonify(body), status


@api_v1_notification_presidia.get("/presidi")
@_richiedi_auth
def list_presidi():
    repo, error = _repo_or_error()
    if error:
        return error
    try:
        return jsonify(build_presidia_list_payload(repo, request.args))
    except Exception as exc:
        return _handle_error(exc)


@api_v1_notification_presidia.get("/presidi/<path:presidio_id>")
@_richiedi_auth
def get_presidio(presidio_id: str):
    repo, error = _repo_or_error()
    if error:
        return error
    try:
        return jsonify(build_presidio_detail_payload(repo, presidio_id))
    except Exception as exc:
        return _handle_error(exc)


@api_v1_notification_presidia.get("/presidi/<path:presidio_id>/evidence")
@_richiedi_auth
def get_evidence(presidio_id: str):
    repo, error = _repo_or_error()
    if error:
        return error
    try:
        return jsonify(build_evidence_payload(repo, presidio_id))
    except Exception as exc:
        return _handle_error(exc)


@api_v1_notification_presidia.get("/presidi/<path:presidio_id>/transitions")
@_richiedi_auth
def get_transitions(presidio_id: str):
    repo, error = _repo_or_error()
    if error:
        return error
    try:
        return jsonify(build_transitions_payload(repo, presidio_id))
    except Exception as exc:
        return _handle_error(exc)


@api_v1_notification_presidia.get("/presidi/<path:presidio_id>/evidence/<path:evidence_id>/content")
@_richiedi_auth
def get_evidence_content(presidio_id: str, evidence_id: str):
    repo, error = _repo_or_error()
    if error:
        return error
    try:
        text = evidence_text(repo, presidio_id, evidence_id)
    except Exception as exc:
        return _handle_error(exc)
    headers = {}
    if str(request.args.get("download") or "") == "1":
        headers["Content-Disposition"] = f'attachment; filename="evidenza-{evidence_id}.txt"'
    return Response(text, headers=headers, mimetype="text/plain; charset=utf-8")


@api_v1_notification_presidia.post("/presidi/<path:presidio_id>/<mutation>")
@_richiedi_auth
def mutate(presidio_id: str, mutation: str):
    repo, error = _repo_or_error()
    if error:
        return error
    body, body_error = _json_body()
    if body_error:
        return body_error
    try:
        detail = mutate_presidio(repo, presidio_id, mutation, body, idempotency_key=_idempotency_key(mutation, presidio_id, body))
        return jsonify({"ok": True, "message": "Operazione registrata.", "presidio": detail["presidio"], "warnings": detail.get("warnings", [])})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_notification_presidia.get("/rollout")
@_richiedi_auth
def get_rollout():
    if not presidio_permissions().get("can_configure"):
        body, status = public_error("forbidden", "Permesso admin.configura richiesto.", status=403)
        return jsonify(body), status
    try:
        return jsonify({"ok": True, "rollout": legal_notification_presidia_rollout(fail_closed_on_error=True)})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_notification_presidia.put("/rollout")
@_richiedi_auth
def update_rollout():
    if not presidio_permissions().get("can_configure"):
        body, status = public_error("forbidden", "Permesso admin.configura richiesto.", status=403)
        return jsonify(body), status
    body, body_error = _json_body()
    if body_error:
        return body_error
    try:
        repo = build_notification_presidio_repository()
        saved = repo.save_config(body, actor=current_actor_id())
        return jsonify({"ok": True, "config": {"rollout_enabled": bool(saved.get("rollout_enabled")), "rollout_mode": saved.get("rollout_mode")}})
    except Exception as exc:
        return _handle_error(exc)
