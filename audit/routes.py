"""Flask routes for forensic audit evidence."""

from __future__ import annotations

from datetime import UTC, datetime
import base64
import hashlib
import hmac
import io
import json
import os
import time
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request, send_file

from .bundle import AuditBundleBuilder
from .exceptions import AuditConfigError, AuditError, AuditValidationError, AuditWormError
from .merkle import merkle_proof
from .schemas import ActorContext, AuditFileRef, SourceContext
from .service import AuditService


audit_blueprint = Blueprint("legal_audit", __name__)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _tenant_id() -> str:
    tenant = getattr(g, "tenant", None)
    value = (
        getattr(tenant, "id", "")
        or getattr(tenant, "slug", "")
        or getattr(g, "tenant_context_slug", "")
    )
    if getattr(g, "tenant_context_missing", False) or not _text(value):
        raise AuditValidationError("Contesto studio mancante.")
    return _text(value)


def _tenant_or_error() -> tuple[str, Any | None]:
    try:
        return _tenant_id(), None
    except AuditValidationError as exc:
        return "", _json_error(str(exc), 403, code="tenant_required")


def _can(permission: str) -> bool:
    user = g.get("utente_corrente")
    return bool(user and getattr(user, "ha_permesso", lambda _perm: False)(permission))


def _json_error(message: str, status: int, *, code: str = "audit_error"):
    return jsonify({"ok": False, "message": message, "code": code}), status


@audit_blueprint.errorhandler(AuditError)
def _audit_error_handler(exc: AuditError):
    current_app.logger.warning("legal_audit_route_failed code=%s", getattr(exc, "code", type(exc).__name__))
    if isinstance(exc, (AuditConfigError, AuditWormError)):
        return _json_error(
            "Presidio probatorio non disponibile: verificare configurazione WORM e firma.",
            503,
            code=getattr(exc, "code", "audit_unavailable"),
        )
    return _json_error("Richiesta audit non valida.", 400, code=getattr(exc, "code", "audit_error"))


def _service() -> AuditService:
    cached = current_app.extensions.get("legal_audit_service")
    if isinstance(cached, AuditService):
        return cached
    service = AuditService.from_config(current_app.config)
    current_app.extensions["legal_audit_service"] = service
    return service


def _rate_limit_internal() -> bool:
    now = time.time()
    key = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    hits = current_app.extensions.setdefault("legal_audit_internal_rate_limit", {})
    window = [item for item in hits.get(key, []) if item > now - 60]
    if len(window) >= int(current_app.config.get("AUDIT_INTERNAL_RATE_LIMIT_PER_MINUTE", 60)):
        hits[key] = window
        return False
    window.append(now)
    hits[key] = window
    return True


def _b64url_decode(value: str) -> bytes:
    raw = value.encode("ascii")
    raw += b"=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw)


def _internal_hmac_valid(token: str) -> bool:
    env = _text(current_app.config.get("AUDIT_ENV") or os.getenv("AUDIT_ENV") or "development").lower()
    if env == "production":
        return False
    secret = _text(current_app.config.get("AUDIT_INTERNAL_TOKEN_HMAC_KEY") or os.getenv("AUDIT_INTERNAL_TOKEN_HMAC_KEY"))
    if not secret or not token.startswith("hmac."):
        return False
    try:
        _, payload_b64, sig_b64 = token.split(".", 2)
        expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(base64.urlsafe_b64encode(expected).rstrip(b"=").decode("ascii"), sig_b64):
            return False
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        return payload.get("aud") == "iusentra-audit-emit" and int(payload.get("exp", 0)) >= int(time.time())
    except Exception:
        return False


def _internal_auth_ok() -> bool:
    if current_app.testing and request.headers.get("X-Audit-Test-Bypass") == "1":
        return True
    mtls_verify = _text(request.headers.get("X-SSL-Client-Verify") or request.headers.get("X-Client-Cert-Verify")).upper()
    if mtls_verify == "SUCCESS":
        allowed = _text(current_app.config.get("AUDIT_INTERNAL_MTLS_FINGERPRINTS") or os.getenv("AUDIT_INTERNAL_MTLS_FINGERPRINTS"))
        fingerprint = _text(request.headers.get("X-SSL-Client-Fingerprint") or request.headers.get("X-Client-Cert-Fingerprint")).lower()
        if not allowed:
            return True
        return fingerprint in {item.strip().lower() for item in allowed.split(",") if item.strip()}
    auth = _text(request.headers.get("Authorization"))
    token = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else _text(request.headers.get("X-Audit-Service-Token"))
    if _internal_hmac_valid(token):
        return True
    return False


def _event_public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": row.get("event_id", ""),
        "tenant_id": row.get("tenant_id", ""),
        "fascicolo_id": row.get("fascicolo_id", ""),
        "actor_id": row.get("actor_id", ""),
        "kind": row.get("kind", ""),
        "event_ts_utc": row.get("event_ts_utc", ""),
        "event_hash": row.get("event_hash", ""),
        "prev_event_hash": row.get("prev_event_hash", ""),
        "signature_alg": row.get("signature_alg", ""),
        "signer_kid": row.get("signer_kid", ""),
        "worm_bucket": row.get("worm_bucket", ""),
        "worm_key": row.get("worm_key", ""),
        "worm_version_id": row.get("worm_version_id", ""),
        "worm_retention_until": row.get("worm_retention_until", ""),
        "snapshot_id": row.get("snapshot_id", ""),
    }


@audit_blueprint.get("/audit/events")
@audit_blueprint.get("/registro/events")
@audit_blueprint.get("/registro/eventi")
def audit_events():
    if not _can("audit.leggi"):
        return _json_error("Permesso audit.leggi richiesto.", 403, code="permission_denied")
    tenant_id, error = _tenant_or_error()
    if error is not None:
        return error
    rows = _service().repository.list_events(
        tenant_id=tenant_id,
        fascicolo_id=_text(request.args.get("fascicolo_id")),
        kind=_text(request.args.get("kind")),
        date_from=_text(request.args.get("date_from")),
        date_to=_text(request.args.get("date_to")),
        limit=min(int(request.args.get("limit", 100) or 100), 500),
    )
    return jsonify({"ok": True, "items": [_event_public_row(row) for row in rows], "tenant_id": tenant_id})


@audit_blueprint.get("/audit/events/<event_id>")
@audit_blueprint.get("/registro/events/<event_id>")
@audit_blueprint.get("/registro/eventi/<event_id>")
def audit_event_detail(event_id: str):
    if not _can("audit.leggi"):
        return _json_error("Permesso audit.leggi richiesto.", 403, code="permission_denied")
    tenant_id, error = _tenant_or_error()
    if error is not None:
        return error
    row = _service().repository.get_event(event_id, tenant_id=tenant_id)
    if not row:
        return _json_error("Evento audit non trovato.", 404, code="not_found")
    envelope = _service().load_envelope(row)
    verified = _service().verify_envelope(envelope)
    return jsonify(
        {
            "ok": verified.ok,
            "item": _event_public_row(row),
            "envelope": envelope,
            "verification": {"ok": verified.ok, "errors": list(verified.errors), "warnings": list(verified.warnings)},
        }
    )


@audit_blueprint.get("/audit/proof/<event_id>")
@audit_blueprint.get("/registro/proof/<event_id>")
@audit_blueprint.get("/registro/prova/<event_id>")
def audit_event_proof(event_id: str):
    if not _can("audit.leggi"):
        return _json_error("Permesso audit.leggi richiesto.", 403, code="permission_denied")
    tenant_id, error = _tenant_or_error()
    if error is not None:
        return error
    service = _service()
    row = service.repository.get_event(event_id, tenant_id=tenant_id)
    if not row:
        return _json_error("Evento audit non trovato.", 404, code="not_found")
    envelope = service.load_envelope(row)
    snapshot_payload: dict[str, Any] | None = None
    proof: list[dict[str, str]] = []
    snapshot_id = _text(row.get("snapshot_id"))
    tsa = {"status": "non ancora incluso", "worm_key": ""}
    if snapshot_id:
        snap_row = service.repository.get_snapshot(snapshot_id, tenant_id=tenant_id)
        if snap_row:
            raw = service.worm_store.get_object(_text(snap_row["worm_key"]), version_id=_text(snap_row.get("worm_version_id")) or None)
            snapshot_payload = json.loads(raw.decode("utf-8"))
            signed_snapshot = snapshot_payload.get("signed_snapshot") or {}
            event_hashes = [str(item) for item in signed_snapshot.get("event_hashes") or []]
            proof = [step.to_dict() for step in merkle_proof(_text(row["event_hash"]), event_hashes)] if event_hashes else []
            tsa = {"status": "presente" if snap_row.get("tsa_token_worm_key") else "non configurata", "worm_key": snap_row.get("tsa_token_worm_key") or ""}
    return jsonify(
        {
            "ok": True,
            "event": _event_public_row(row),
            "envelope": envelope,
            "chain": {"prev_event_hash": row.get("prev_event_hash", ""), "event_hash": row.get("event_hash", "")},
            "snapshot": snapshot_payload,
            "merkle_proof": proof,
            "tsa": tsa,
            "instructions": "Verifica offline: python scripts/verify_audit.py verify-proof proofs/<event_id>.json",
        }
    )


@audit_blueprint.get("/audit/bundle/fascicolo/<fascicolo_id>")
@audit_blueprint.get("/registro/bundle/fascicolo/<fascicolo_id>")
def audit_bundle_fascicolo(fascicolo_id: str):
    if not _can("audit.esporta") and not _can("audit.leggi"):
        return _json_error("Permesso audit.esporta richiesto.", 403, code="permission_denied")
    tenant_id, error = _tenant_or_error()
    if error is not None:
        return error
    bundle = AuditBundleBuilder(_service()).build_fascicolo_bundle(tenant_id=tenant_id, fascicolo_id=fascicolo_id)
    return send_file(
        io.BytesIO(bundle.content),
        mimetype="application/zip",
        as_attachment=True,
        download_name=bundle.filename,
    )


@audit_blueprint.post("/internal/audit/emit")
def internal_audit_emit():
    if not _rate_limit_internal():
        current_app.logger.warning("audit_internal_rate_limited ip=%s", request.remote_addr)
        return _json_error("Troppe richieste interne audit.", 429, code="rate_limited")
    if not _internal_auth_ok():
        current_app.logger.warning("audit_internal_auth_denied ip=%s", request.remote_addr)
        return _json_error("Autenticazione interna audit richiesta.", 403, code="internal_auth_required")
    payload = request.get_json(silent=True) or {}
    idempotency_key = _text(payload.get("idempotency_key") or request.headers.get("Idempotency-Key"))
    if not idempotency_key:
        return _json_error("Idempotency key obbligatoria.", 400, code="idempotency_required")
    try:
        result = _service().emit_event(
            kind=_text(payload.get("kind")),
            tenant_id=_text(payload.get("tenant_id")),
            fascicolo_id=_text(payload.get("fascicolo_id")),
            actor=ActorContext(**(payload.get("actor") or {})),
            payload=payload.get("payload") or {},
            files=[AuditFileRef(**item) for item in (payload.get("files") or [])],
            source=SourceContext(**{**(payload.get("source") or {}), "idempotency_key": idempotency_key}),
            idempotency_key=idempotency_key,
        )
        return jsonify({"ok": True, "event_id": result.event_id, "event_hash": result.event_hash, "worm_uri": result.worm_uri})
    except AuditError as exc:
        _service().record_failure_safe(
            tenant_id=_text(payload.get("tenant_id")),
            fascicolo_id=_text(payload.get("fascicolo_id")),
            attempted_kind=_text(payload.get("kind")),
            idempotency_key=idempotency_key,
            failure_stage="internal_emit",
            exc=exc,
        )
        current_app.logger.warning("audit_internal_emit_failed code=%s", getattr(exc, "code", type(exc).__name__))
        return _json_error("Emissione audit non riuscita.", 400, code=getattr(exc, "code", "audit_error"))
