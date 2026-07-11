"""API v1 UI per il piano del giorno (Lex Oggi) — /api/v1/ui/daily-plan*.

Prestazioni: le GET leggono esclusivamente lo snapshot materializzato
(nessuna scansione, nessun OCR, nessun LLM). Le POST accodano lavoro o
creano proposte approvabili; il tenant è sempre risolto lato server.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date
from functools import wraps
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from pct.daily_plan.clock import system_clock
from web.services.feature_flags import feature_disabled_response, is_feature_enabled
from web.services.react_daily_plan_bridge import (
    DOMAIN_ACTIONS,
    STATUS_ACTIONS,
    apply_daily_plan_status_action,
    build_react_daily_plan_payload,
    create_daily_plan_domain_proposal,
    daily_plan_backlog_payload,
    daily_plan_coverage_payload,
    daily_plan_error_payload,
    daily_plan_item_detail_payload,
    enqueue_daily_plan_refresh,
)
from web.services.tenant_api_auth import api_key_valid_for_request

api_v1_daily_plan = Blueprint("api_v1_daily_plan", __name__, url_prefix="/api/v1/ui")

READ_PERMISSIONS = ("agenda.leggi", "scadenziario.leggi")
WRITE_PERMISSIONS = ("agenda.leggi", "scadenziario.leggi")
ADMIN_PERMISSION = "admin.leggi"

# chiavi che il client non può mai decidere (tenant/permessi lato server)
_FORBIDDEN_BODY_KEYS = {
    "tenant", "tenant_id", "studio_id", "tenant_slug", "user_permissions",
    "permessi", "path", "file_path", "token", "api_key", "secret",
}


def _api_key_valida() -> bool:
    return api_key_valid_for_request()


def _session_user_can(permission: str) -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _p: False)(permission))


def _can_all(*permissions: str) -> bool:
    if _api_key_valida():
        return True
    return all(_session_user_can(p) for p in permissions)


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "code": "unauthorized", "detail": "Autenticazione richiesta."}), 401

    return wrapper


def _flag_gate():
    if not is_feature_enabled("lex.dailyPlan.enabled", current_app.config):
        return feature_disabled_response("lex.dailyPlan.enabled")
    return None


def _forbidden():
    return jsonify({"ok": False, "code": "forbidden", "detail": "Permessi insufficienti."}), 403


def _actor_label() -> str:
    utente = g.get("utente_corrente")
    if utente is not None:
        return str(
            getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or "utente"
        )
    return "api-key"


def _session_user_id() -> str:
    utente = g.get("utente_corrente")
    return str(getattr(utente, "id", "") or "") if utente is not None else ""


def _target_user_id() -> tuple[str, Any]:
    """Utente del piano: sé stessi; altri utenti o coda studio solo admin."""
    requested = str(request.args.get("user") or "").strip()
    own = _session_user_id()
    if not requested or requested == own:
        return (requested or own), None
    if requested == "studio":
        requested = ""
    if _can_all(ADMIN_PERMISSION) or _api_key_valida():
        return requested, None
    return "", _forbidden()


def _audit(action: str, resource_id: str = "", details: str = "") -> None:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    audit = core_runtime.get("audit")
    if callable(audit):
        try:
            audit(action, "daily_plan", resource_id, details)
        except Exception:
            pass


def _json_body() -> tuple[dict[str, Any] | None, Any]:
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return None, (jsonify({"ok": False, "code": "invalid_body"}), 400)
    lowered = {str(k).lower() for k in body}
    if lowered & _FORBIDDEN_BODY_KEYS:
        return None, (
            jsonify({"ok": False, "code": "client_control_rejected",
                     "detail": "Parametri riservati non ammessi."}),
            400,
        )
    return body, None


def _etag_for(user_id: str, target_date: str, version: str, generated_at: str) -> str:
    tenant = "t"
    try:
        from web.services.daily_plan_runtime import current_tenant_label

        tenant = current_tenant_label()
    except Exception:
        pass
    stamp = hashlib.sha256(str(generated_at or "").encode("utf-8")).hexdigest()[:10]
    return f'W/"dp-{tenant}-{user_id or "studio"}-{target_date}-{version}-{stamp}"'


# ------------------------------------------------------------------ letture


@api_v1_daily_plan.get("/daily-plan")
@_richiedi_auth
def daily_plan_home():
    blocked = _flag_gate()
    if blocked is not None:
        return blocked
    if not _can_all(*READ_PERMISSIONS):
        return _forbidden()
    user_id, err = _target_user_id()
    if err is not None:
        return err
    target_date = str(request.args.get("date") or "").strip()
    try:
        payload = build_react_daily_plan_payload(target_date=target_date, user_id=user_id)
    except Exception as exc:
        body, status = daily_plan_error_payload(exc)
        return jsonify(body), status
    version = str(payload.get("versione_piano") or "")
    if version:
        etag = _etag_for(
            user_id,
            str(payload.get("data") or ""),
            version,
            str(payload.get("generato_il") or ""),
        )
        if request.headers.get("If-None-Match") == etag:
            response = current_app.response_class(status=304)
            response.headers["ETag"] = etag
            return response
        response = jsonify(payload)
        response.headers["ETag"] = etag
        response.headers["X-Plan-Version"] = version
        return response
    return jsonify(payload)


@api_v1_daily_plan.get("/daily-plan/coverage")
@_richiedi_auth
def daily_plan_coverage():
    blocked = _flag_gate()
    if blocked is not None:
        return blocked
    if not _can_all(*READ_PERMISSIONS):
        return _forbidden()
    try:
        return jsonify(daily_plan_coverage_payload())
    except Exception as exc:
        body, status = daily_plan_error_payload(exc)
        return jsonify(body), status


@api_v1_daily_plan.get("/daily-plan/items/<item_id>")
@_richiedi_auth
def daily_plan_item_detail(item_id: str):
    blocked = _flag_gate()
    if blocked is not None:
        return blocked
    if not _can_all(*READ_PERMISSIONS):
        return _forbidden()
    try:
        return jsonify(daily_plan_item_detail_payload(item_id))
    except Exception as exc:
        current_app.logger.exception("Errore dettaglio piano del giorno: %s", exc)
        body, status = daily_plan_error_payload(exc)
        return jsonify(body), status


@api_v1_daily_plan.get("/daily-plan/backlog")
@_richiedi_auth
def daily_plan_backlog():
    blocked = _flag_gate()
    if blocked is not None:
        return blocked
    if not _can_all(*READ_PERMISSIONS):
        return _forbidden()
    user_id, err = _target_user_id()
    if err is not None:
        return err
    try:
        limit = max(min(int(request.args.get("limit") or 50), 200), 1)
    except Exception:
        limit = 50
    try:
        return jsonify(
            daily_plan_backlog_payload(
                target_date=str(request.args.get("date") or "").strip(),
                user_id=user_id,
                cursor=str(request.args.get("cursor") or "").strip(),
                limit=limit,
            )
        )
    except Exception as exc:
        body, status = daily_plan_error_payload(exc)
        return jsonify(body), status


# ------------------------------------------------------------------ scritture


@api_v1_daily_plan.post("/daily-plan/refresh")
@_richiedi_auth
def daily_plan_refresh():
    blocked = _flag_gate()
    if blocked is not None:
        return blocked
    if not _can_all(*WRITE_PERMISSIONS):
        return _forbidden()
    body, err = _json_body()
    if err is not None:
        return err
    mode = str(body.get("mode") or "incremental").strip().lower()
    if mode not in ("incremental", "full"):
        return jsonify({"ok": False, "code": "invalid_mode"}), 400
    if mode == "full" and not (_can_all(ADMIN_PERMISSION) or _api_key_valida()):
        return _forbidden()
    idempotency_key = str(
        request.headers.get("Idempotency-Key") or body.get("idempotency_key") or ""
    ).strip()[:120]
    target_raw = str(body.get("date") or "").strip()
    try:
        today = system_clock().today()
        target = date.fromisoformat(target_raw) if target_raw else today
        if target < today:
            raise ValueError("La data del piano non può essere precedente a oggi.")
        target_date = target.isoformat()
        outcome = enqueue_daily_plan_refresh(
            mode=mode,
            actor=_actor_label(),
            target_date=target_date,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        payload, status = daily_plan_error_payload(exc)
        return jsonify(payload), status
    outcome["avvio_immediato_richiesto"] = False
    try:
        from web.services.scheduler_admin_surface import request_scheduler_run

        dispatch = request_scheduler_run(
            "daily_plan_incremental_refresh",
            username=_actor_label(),
            dedupe_open=bool(outcome.get("gia_in_coda")),
        )
        outcome["avvio_immediato_richiesto"] = dispatch.get("status") in {
            "requested",
            "running",
        }
    except Exception as exc:
        current_app.logger.exception(
            "Richiesta immediata piano del giorno non inoltrata: %s", exc
        )
    outcome["messaggio"] = (
        "Aggiornamento richiesto: il piano si riallinea automaticamente."
        if outcome["avvio_immediato_richiesto"]
        else "Aggiornamento accodato: il piano si riallinea al prossimo controllo."
    )
    _audit("daily_plan.refresh_richiesto", outcome.get("job_id", ""), f"modalita={mode}")
    return jsonify(outcome), 202


@api_v1_daily_plan.post("/daily-plan/items/<item_id>/action")
@_richiedi_auth
def daily_plan_item_action(item_id: str):
    blocked = _flag_gate()
    if blocked is not None:
        return blocked
    if not _can_all(*WRITE_PERMISSIONS):
        return _forbidden()
    body, err = _json_body()
    if err is not None:
        return err
    action = str(body.get("action") or "").strip()
    params = dict(body.get("params") or {})
    lowered = {str(k).lower() for k in params}
    if lowered & _FORBIDDEN_BODY_KEYS:
        return jsonify({"ok": False, "code": "client_control_rejected"}), 400
    idempotency_key = str(
        request.headers.get("Idempotency-Key") or body.get("idempotency_key") or ""
    ).strip()[:120]

    try:
        if action in STATUS_ACTIONS:
            result = apply_daily_plan_status_action(
                item_id=item_id,
                action=action,
                params=params,
                actor=_actor_label(),
                idempotency_key=idempotency_key,
            )
            _audit(f"daily_plan.{action}", item_id)
            return jsonify(result)
        if action in DOMAIN_ACTIONS:
            if not is_feature_enabled("lex.dailyPlan.writeProposals", current_app.config):
                return feature_disabled_response("lex.dailyPlan.writeProposals")
            if not is_feature_enabled("lex.workflowAgents.enabled", current_app.config):
                return feature_disabled_response("lex.workflowAgents.enabled")
            result = create_daily_plan_domain_proposal(
                item_id=item_id, action=action, params=params, actor=_actor_label()
            )
            _audit(f"daily_plan.proposta.{action}", item_id, result.get("proposal_id", ""))
            return jsonify(result)
        return jsonify({"ok": False, "code": "unknown_action",
                        "detail": "Azione non riconosciuta."}), 400
    except Exception as exc:
        payload, status = daily_plan_error_payload(exc)
        return jsonify(payload), status
