"""API REST per pipeline PEC audit-grade."""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, Response, g, jsonify, request

from pct.pec_pipeline import PecAuditRepository, ingest_synthetic_dataset
from web.services.security_redaction import redact_exception_details
from web.services.tenant_api_auth import api_key_valid_for_request
from web.services.tenant_paths import TenantDataPathError, tenant_data_path

pec_pipeline_api = Blueprint("pec_pipeline_api", __name__, url_prefix="/api/pec")


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or api_key_valid_for_request():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "errore": "Autenticazione richiesta."}), 401

    return wrapper


def _tenant_id() -> str:
    return str(g.get("tenant_slug", "") or g.get("auth_tenant_slug", "") or "default")


def _actor() -> str:
    user = g.get("utente_corrente")
    return str(getattr(user, "username", "") or getattr(user, "id", "") or "api")


def _runtime_path(key: str, default: str, *aliases: str, required: bool = True) -> str:
    return tenant_data_path(key, default, *aliases, require_tenant=required)


def _repo() -> PecAuditRepository:
    email_db = Path(_runtime_path("EMAIL_CASELLA_DB", "./email/casella.json"))
    paths = getattr(g, "data_paths", {}) or {}
    configured_db = paths.get("PEC_AUDIT_DB")
    db_path = Path(str(configured_db)) if configured_db else email_db.parent / "pec_audit.sqlite"
    return PecAuditRepository(
        db_path,
        tenant_id=_tenant_id(),
        fascicoli_db_path=_runtime_path("FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_runtime_path("FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_runtime_path("SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
    )


def _json_error(exc: Exception, status: int = 400):
    if status == 403:
        message = "Dati dello studio non disponibili per questa richiesta."
    elif status == 404:
        message = "Elemento PEC non trovato."
    else:
        message = "Operazione PEC non completata."
    return jsonify({"ok": False, "errore": message}), status


def _json_success(payload: dict, status: int = 200):
    return jsonify(redact_exception_details(payload)), status


@pec_pipeline_api.get("/messages")
@_richiedi_auth
def pec_messages():
    try:
        repo = _repo()
        rows = repo.list_messages(
            limit=int(request.args.get("limit", "100") or 100),
            folder=request.args.get("folder", "").strip(),
            q=request.args.get("q", "").strip(),
        )
        return jsonify({"ok": True, "data": rows, "count": len(rows)})
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.get("/messages/<message_id>")
@_richiedi_auth
def pec_message_detail(message_id: str):
    try:
        return jsonify({"ok": True, "data": _repo().get_message_detail(message_id)})
    except KeyError as exc:
        return _json_error(exc, 404)
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.get("/messages/<message_id>/mime")
@_richiedi_auth
def pec_message_mime(message_id: str):
    try:
        raw, row = _repo().original_mime(message_id)
    except KeyError as exc:
        return _json_error(exc, 404)
    response = Response(raw, mimetype="message/rfc822")
    safe_name = f"{message_id}.eml"
    response.headers["Content-Disposition"] = f'inline; filename="{safe_name}"'
    response.headers["X-IUSENTRA-MIME-SHA256"] = str(row.get("mime_sha256") or "")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@pec_pipeline_api.post("/fetch")
@_richiedi_auth
def pec_fetch():
    try:
        from web.services.mailbox_sync_runtime import _get_config_pec, _get_config_smtp, mailbox_context_for_current_request

        ctx = mailbox_context_for_current_request()
        pec_cfg = _get_config_pec(ctx)
        smtp_cfg = _get_config_smtp(ctx)
        cfg = pec_cfg if pec_cfg and getattr(pec_cfg, "imap_host", "") else smtp_cfg
        if not cfg or not getattr(cfg, "imap_host", ""):
            return jsonify({"ok": False, "errore": "IMAP PEC non configurato."}), 400
        username = str(getattr(cfg, "indirizzo", "") or getattr(cfg, "username", "") or "")
        report = _repo().fetch_imap(
            imap_host=str(getattr(cfg, "imap_host", "")),
            imap_port=int(getattr(cfg, "imap_port", 993) or 993),
            username=username,
            password=str(getattr(cfg, "password", "") or ""),
            use_ssl=bool(getattr(cfg, "use_ssl", getattr(cfg, "imap_use_ssl", True))),
            limit=int(request.args.get("limit", "50") or 50),
            actor=_actor(),
        )
        worker = _repo().run_pending_jobs(limit=200, actor=_actor())
        return _json_success({"ok": True, "fetch": report, "workers": worker})
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.post("/workers/run")
@_richiedi_auth
def pec_workers_run():
    try:
        report = _repo().run_pending_jobs(limit=int(request.args.get("limit", "200") or 200), actor=_actor())
        return _json_success({"ok": True, "report": report})
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.get("/digest")
@_richiedi_auth
def pec_digest_get():
    try:
        return jsonify({"ok": True, "data": _repo().latest_digest()})
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.post("/digest/run")
@_richiedi_auth
def pec_digest_run():
    try:
        digest = _repo().build_daily_digest(digest_date=request.args.get("date") or None, actor=_actor())
        return jsonify({"ok": True, "data": digest})
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.post("/messages/<message_id>/salva-fascicolo")
@_richiedi_auth
def pec_save_to_fascicolo(message_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        result = _repo().save_to_fascicolo(message_id, fascicolo_id=str(payload.get("fascicolo_id") or ""), actor=_actor())
        return _json_success(result, 200 if result.get("ok") else 409)
    except KeyError as exc:
        return _json_error(exc, 404)
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.post("/messages/<message_id>/richiedi-allegato-mancante")
@_richiedi_auth
def pec_request_missing_attachment(message_id: str):
    try:
        return jsonify(_repo().request_missing_attachment(message_id, actor=_actor()))
    except KeyError as exc:
        return _json_error(exc, 404)
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.post("/messages/<message_id>/schedula-scadenza")
@_richiedi_auth
def pec_schedule_deadline(message_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        result = _repo().schedule_deadline(message_id, actor=_actor(), due_date=str(payload.get("data_scadenza") or ""))
        return _json_success(result, 200 if result.get("ok") else 409)
    except KeyError as exc:
        return _json_error(exc, 404)
    except TenantDataPathError as exc:
        return _json_error(exc, 403)


@pec_pipeline_api.post("/demo/ingest")
@_richiedi_auth
def pec_demo_ingest():
    try:
        return _json_success({"ok": True, "data": ingest_synthetic_dataset(_repo(), run_workers=True)})
    except TenantDataPathError as exc:
        return _json_error(exc, 403)
