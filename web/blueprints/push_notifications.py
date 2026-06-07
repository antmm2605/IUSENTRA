"""API PWA/Web Push per notifiche dispositivo."""

from __future__ import annotations

from functools import wraps
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from pct.notifications import NotificationServiceError
from pct.notifications.web_push import load_web_push_config, web_push_config_diagnostics
from web.services.feature_flags import is_feature_enabled, require_feature_flag
from web.services.notifications_runtime import (
    build_notification_service,
    current_tenant_id,
    current_user_id,
)

push_notifications = Blueprint("api_push_notifications", __name__)


def _json_error(message: str, status: int):
    return jsonify({"ok": False, "error": message, "message": message}), status


def _require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return _json_error("Autenticazione richiesta.", 401)
        return fn(*args, **kwargs)

    return wrapper


def _json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _subscription_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("subscription")
    return nested if isinstance(nested, dict) else payload


def _keys(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("keys")
    return value if isinstance(value, dict) else {}


def _context() -> tuple[str, str]:
    tenant_id = current_tenant_id()
    user_id = current_user_id()
    if not tenant_id or not user_id:
        raise NotificationServiceError("Contesto utente non disponibile.", 403)
    return tenant_id, user_id


@push_notifications.get("/api/push/public-key")
@_require_auth
def public_key():
    try:
        tenant_id, user_id = _context()
        if not is_feature_enabled("notifications.mobilePush", current_app.config):
            return jsonify(
                {
                    "ok": False,
                    "configured": False,
                    "enabled": False,
                    "diagnostics": {"enabled": False, "configured": False, "missing": []},
                    "message": "Notifiche su dispositivo non attive per questo studio.",
                    "preferences": {
                        "pushEnabled": False,
                        "notifyUrgent": True,
                        "notifyImportant": True,
                        "notifyNormal": False,
                    },
                }
            )
        config = load_web_push_config(current_app.config)
        diagnostics = web_push_config_diagnostics(config)
        service = build_notification_service()
        preferences = service.preferences(tenant_id, user_id)
        if not config.configured:
            return jsonify(
                {
                    "ok": False,
                    "configured": False,
                    "enabled": bool(config.enabled),
                    "diagnostics": diagnostics,
                    "message": "Notifiche su dispositivo non configurate nel sistema.",
                    "preferences": {
                        "pushEnabled": preferences.push_enabled,
                        "notifyUrgent": preferences.notify_urgent,
                        "notifyImportant": preferences.notify_important,
                        "notifyNormal": preferences.notify_normal,
                    },
                }
            )
        return jsonify(
            {
                "ok": True,
                "configured": True,
                "enabled": True,
                "diagnostics": diagnostics,
                "publicKey": config.public_key,
                "preferences": {
                    "pushEnabled": preferences.push_enabled,
                    "notifyUrgent": preferences.notify_urgent,
                    "notifyImportant": preferences.notify_important,
                    "notifyNormal": preferences.notify_normal,
                },
            }
        )
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Errore lettura chiave pubblica notifiche dispositivo")
        return _json_error("Notifiche su dispositivo non disponibili.", 500)


@push_notifications.post("/api/push/subscribe")
@_require_auth
@require_feature_flag("notifications.mobilePush")
def subscribe():
    try:
        tenant_id, user_id = _context()
        payload = _subscription_payload(_json_payload())
        keys = _keys(payload)
        service = build_notification_service()
        record = service.register_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            endpoint=str(payload.get("endpoint") or ""),
            p256dh=str(keys.get("p256dh") or ""),
            auth=str(keys.get("auth") or ""),
            user_agent=request.headers.get("User-Agent", ""),
            device_label=str(_json_payload().get("device_label") or _json_payload().get("deviceLabel") or ""),
        )
        return jsonify(
            {
                "ok": True,
                "active": True,
                "subscriptionId": record.id,
                "message": "Notifiche attive su questo dispositivo.",
            }
        )
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Errore salvataggio subscription push")
        return _json_error("Attivazione notifiche non completata.", 500)


@push_notifications.delete("/api/push/subscribe")
@_require_auth
@require_feature_flag("notifications.mobilePush")
def unsubscribe():
    try:
        tenant_id, user_id = _context()
        payload = _subscription_payload(_json_payload())
        endpoint = str(payload.get("endpoint") or "")
        subscription_id = str(payload.get("id") or payload.get("subscriptionId") or "")
        removed = build_notification_service().revoke_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            endpoint=endpoint,
            subscription_id=subscription_id,
        )
        return jsonify(
            {
                "ok": True,
                "active": False,
                "revoked": removed,
                "message": "Notifiche disattivate per questo dispositivo.",
            }
        )
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Errore revoca subscription push")
        return _json_error("Disattivazione notifiche non completata.", 500)


@push_notifications.post("/api/push/test")
@_require_auth
@require_feature_flag("notifications.mobilePush")
def test_push():
    try:
        tenant_id, user_id = _context()
        record, summary = build_notification_service().create_test_notification(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if summary.sent:
            message = "Notifica di test inviata al dispositivo."
        elif not summary.configured:
            message = "Notifica interna creata; notifiche su dispositivo non configurate."
        else:
            message = "Notifica interna creata; nessun dispositivo attivo ha ricevuto il test."
        return jsonify(
            {
                "ok": True,
                "message": message,
                "pushConfigured": summary.configured,
                "attempted": summary.attempted,
                "sent": summary.sent,
                "disabled": summary.disabled,
                "notificationId": record.id,
            }
        )
    except NotificationServiceError as exc:
        return _json_error(str(exc), exc.status_code)
    except Exception:
        current_app.logger.exception("Errore invio notifica di test")
        return _json_error("Notifica di test non completata.", 500)
