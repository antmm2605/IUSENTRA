"""API operative per la top bar React."""

from __future__ import annotations

from functools import wraps
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from web.services import topbar_operational as core_service
from web.services import topbar_recent as recent_service
from web.services import topbar_timer as timer_service

topbar = Blueprint("api_topbar", __name__)


def _json_error(message: str, status: int):
    return jsonify({"ok": False, "error": message}), status


def _require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = g.get("utente_corrente")
        if not user:
            return _json_error("Autenticazione richiesta.", 401)
        return fn(*args, **kwargs)

    return wrapper


def _json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _query_limit(default: int = 20) -> int:
    raw = request.args.get("limit", default)
    try:
        return int(raw or default)
    except (TypeError, ValueError) as exc:
        raise core_service.TopbarApiError("Limit non valido.", 400) from exc


def _handle(fn):
    try:
        return jsonify(fn())
    except core_service.TopbarApiError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Errore API top bar")
        return _json_error("Errore operativo della top bar.", 500)


@topbar.get("/api/search/global")
@_require_auth
def api_global_search():
    user = g.get("utente_corrente")
    return _handle(
        lambda: core_service.global_search_payload(
            user,
            request.args.get("q", ""),
            _query_limit(),
        )
    )


@topbar.get("/api/dashboard/today")
@_require_auth
def api_today():
    return _handle(lambda: core_service.today_payload(g.get("utente_corrente"), request.args.get("date")))


@topbar.get("/api/notifications")
@_require_auth
def api_notifications():
    return _handle(lambda: core_service.notifications_payload(g.get("utente_corrente")))


@topbar.patch("/api/notifications/read-all")
@_require_auth
def api_notifications_read_all():
    return _handle(lambda: core_service.mark_all_notifications_read(g.get("utente_corrente")))


@topbar.patch("/api/notifications/<path:notification_id>/read")
@_require_auth
def api_notification_read(notification_id: str):
    return _handle(lambda: core_service.mark_notification_read(notification_id, g.get("utente_corrente")))


@topbar.get("/api/deadlines/quick-summary")
@_require_auth
def api_quick_deadlines():
    return _handle(lambda: core_service.quick_deadlines_payload(g.get("utente_corrente")))


@topbar.get("/api/recent")
@_require_auth
def api_recent():
    return _handle(lambda: recent_service.recent_payload(g.get("utente_corrente")))


@topbar.post("/api/recent")
@_require_auth
def api_recent_track():
    payload = _json_payload()
    return _handle(
        lambda: recent_service.track_recent_payload(
            g.get("utente_corrente"),
            str(payload.get("entityType") or payload.get("entity_type") or ""),
            str(payload.get("entityId") or payload.get("entity_id") or ""),
        )
    )


@topbar.get("/api/time-tracking/active")
@_require_auth
def api_time_tracking_active():
    return _handle(lambda: timer_service.active_timer_payload(g.get("utente_corrente")))


@topbar.post("/api/time-tracking/start")
@_require_auth
def api_time_tracking_start():
    return _handle(lambda: timer_service.start_timer_payload(g.get("utente_corrente"), _json_payload()))


@topbar.patch("/api/time-tracking/<timer_id>/pause")
@_require_auth
def api_time_tracking_pause(timer_id: str):
    return _handle(lambda: timer_service.pause_timer_payload(g.get("utente_corrente"), timer_id))


@topbar.patch("/api/time-tracking/<timer_id>/resume")
@_require_auth
def api_time_tracking_resume(timer_id: str):
    return _handle(lambda: timer_service.resume_timer_payload(g.get("utente_corrente"), timer_id))


@topbar.patch("/api/time-tracking/<timer_id>/stop")
@_require_auth
def api_time_tracking_stop(timer_id: str):
    return _handle(lambda: timer_service.stop_timer_payload(g.get("utente_corrente"), timer_id))
