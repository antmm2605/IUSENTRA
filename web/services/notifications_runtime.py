"""Runtime Flask condiviso per il centro notifiche persistente."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app, g

from pct.notifications import NotificationRepository, NotificationService
from pct.notifications.web_push import load_web_push_config
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from web.helpers import tenant_corrente


def current_tenant_id() -> str:
    tenant = tenant_corrente()
    value = (
        getattr(tenant, "id", "")
        or getattr(tenant, "slug", "")
        or getattr(g, "tenant_context_slug", "")
        or "default"
    )
    return str(value or "default").strip()


def current_user_id(user: Any | None = None) -> str:
    current = user if user is not None else g.get("utente_corrente")
    return str(getattr(current, "id", "") or getattr(current, "username", "") or "").strip()


def notifications_db_path() -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if paths.get("NOTIFICATIONS_DB"):
        return str(paths["NOTIFICATIONS_DB"])
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    configured = str(current_app.config.get("NOTIFICATIONS_DB") or "").strip()
    if configured:
        return configured
    fallback = Path(str(current_app.config.get("NOTIFICHE_LOG") or "./notifiche/log.json"))
    return str(fallback.with_name("notifications.db"))


def build_notification_repository() -> NotificationRepository:
    postgres_dsn = resolve_runtime_postgres_dsn(
        config=current_app.config,
        env_url_keys=("IUSENTRA_NOTIFICATIONS_DATABASE_URL", "PCT_NOTIFICATIONS_DATABASE_URL"),
    )
    db_path = notifications_db_path()
    cache_key = f"{db_path}|{postgres_dsn}"
    cache = current_app.extensions.setdefault("notification_repositories", {})
    repo = cache.get(cache_key)
    if isinstance(repo, NotificationRepository):
        return repo
    repo = NotificationRepository(db_path, postgres_dsn=postgres_dsn)
    cache[cache_key] = repo
    return repo


def build_notification_service() -> NotificationService:
    return NotificationService(
        build_notification_repository(),
        web_push_config=load_web_push_config(current_app.config),
    )
