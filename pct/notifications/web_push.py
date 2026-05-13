"""Invio Web Push privacy-safe per IUSENTRA."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - dipendenza opzionale in ambienti senza integrazioni
    import pywebpush
except Exception:  # pragma: no cover
    pywebpush = None  # type: ignore[assignment]

from .models import NotificationRecord, PushSubscriptionRecord


WEB_PUSH_ENV_VARS = {
    "enabled": "IUSENTRA_WEB_PUSH_ENABLED",
    "public_key": "IUSENTRA_VAPID_PUBLIC_KEY",
    "private_key": "IUSENTRA_VAPID_PRIVATE_KEY",
    "subject": "IUSENTRA_VAPID_SUBJECT",
}

SAFE_BODIES = {
    "urgent": "IUSENTRA: evento urgente da verificare.",
    "important": "Hai una nuova notifica importante nel gestionale.",
    "normal": "E' disponibile una nuova notifica su IUSENTRA.",
}


@dataclass(frozen=True)
class WebPushConfig:
    enabled: bool
    public_key: str = ""
    private_key: str = ""
    subject: str = "mailto:admin@example.com"

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.public_key and self.private_key and self.subject)


@dataclass(frozen=True)
class PushSendResult:
    ok: bool
    configured: bool
    expired: bool = False
    status: str = ""
    error: str = ""


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_web_push_config(config: dict[str, Any] | None = None) -> WebPushConfig:
    cfg = dict(config or {})
    enabled = _as_bool(
        cfg.get("IUSENTRA_WEB_PUSH_ENABLED", os.getenv("IUSENTRA_WEB_PUSH_ENABLED")),
        default=False,
    )
    return WebPushConfig(
        enabled=enabled,
        public_key=str(cfg.get("IUSENTRA_VAPID_PUBLIC_KEY") or os.getenv("IUSENTRA_VAPID_PUBLIC_KEY") or "").strip(),
        private_key=str(cfg.get("IUSENTRA_VAPID_PRIVATE_KEY") or os.getenv("IUSENTRA_VAPID_PRIVATE_KEY") or "").strip(),
        subject=str(
            cfg.get("IUSENTRA_VAPID_SUBJECT")
            or os.getenv("IUSENTRA_VAPID_SUBJECT")
            or "mailto:admin@example.com"
        ).strip(),
    )


def web_push_config_diagnostics(
    config: WebPushConfig | dict[str, Any] | None = None,
    *,
    include_subject: bool = False,
) -> dict[str, Any]:
    cfg = config if isinstance(config, WebPushConfig) else load_web_push_config(config)
    missing: list[str] = []
    if not cfg.enabled:
        missing.append(WEB_PUSH_ENV_VARS["enabled"])
    if not cfg.public_key:
        missing.append(WEB_PUSH_ENV_VARS["public_key"])
    if not cfg.private_key:
        missing.append(WEB_PUSH_ENV_VARS["private_key"])
    if not cfg.subject:
        missing.append(WEB_PUSH_ENV_VARS["subject"])
    diagnostics: dict[str, Any] = {
        "enabled": bool(cfg.enabled),
        "configured": bool(cfg.configured),
        "hasPublicKey": bool(cfg.public_key),
        "hasPrivateKey": bool(cfg.private_key),
        "hasSubject": bool(cfg.subject),
        "missing": missing,
        "pywebpushInstalled": pywebpush is not None,
    }
    if include_subject:
        diagnostics["subject"] = cfg.subject
    return diagnostics


def web_push_recommendation(config: WebPushConfig | dict[str, Any] | None = None) -> str:
    diagnostics = web_push_config_diagnostics(config)
    if diagnostics["configured"] and diagnostics["pywebpushInstalled"]:
        return "Web Push configurato: verificare il consenso dal pannello Notifiche."
    if diagnostics["configured"] and not diagnostics["pywebpushInstalled"]:
        return "Configurazione presente, ma pywebpush non e' installato nel runtime."
    return "Eseguire deploy/hetzner/configure_web_push.sh sul server e poi riavviare IUSENTRA."


def safe_href(value: str | None) -> str:
    href = str(value or "").strip()
    if not href or not href.startswith("/") or href.startswith("//"):
        return "/app-v2"
    if any(token in href.lower() for token in ("javascript:", "data:", "\n", "\r")):
        return "/app-v2"
    return href[:500]


def safe_web_push_payload(notification: NotificationRecord) -> dict[str, Any]:
    priority = notification.priority if notification.priority in SAFE_BODIES else "normal"
    return {
        "title": "IUSENTRA",
        "body": SAFE_BODIES[priority],
        "href": safe_href(notification.href),
        "notificationId": notification.id,
        "priority": priority,
        "type": str(notification.type or "operational")[:80],
    }


def _subscription_info(subscription: PushSubscriptionRecord) -> dict[str, Any]:
    return {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    }


def _status_code(exc: BaseException) -> int:
    response = getattr(exc, "response", None)
    raw = getattr(response, "status_code", None) or getattr(response, "status", None)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def is_expired_push_error(exc: BaseException) -> bool:
    status = _status_code(exc)
    if status in {400, 404, 410}:
        return True
    text = str(exc).lower()
    return "410" in text or "expired" in text or "gone" in text or "invalid" in text


def send_web_push(
    subscription: PushSubscriptionRecord,
    payload: dict[str, Any],
    *,
    config: WebPushConfig | None = None,
    timeout: int = 5,
) -> PushSendResult:
    cfg = config or load_web_push_config()
    if not cfg.configured:
        return PushSendResult(ok=False, configured=False, status="not_configured")
    if pywebpush is None:
        return PushSendResult(ok=False, configured=True, status="missing_dependency", error="pywebpush non installato")
    try:
        pywebpush.webpush(
            subscription_info=_subscription_info(subscription),
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=cfg.private_key,
            vapid_claims={"sub": cfg.subject},
            timeout=timeout,
        )
        return PushSendResult(ok=True, configured=True, status="sent")
    except Exception as exc:  # pragma: no cover - coperto con mock nei test
        expired = is_expired_push_error(exc)
        return PushSendResult(
            ok=False,
            configured=True,
            expired=expired,
            status="expired" if expired else "failed",
            error=exc.__class__.__name__,
        )
