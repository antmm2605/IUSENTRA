"""Runtime Flask condiviso per il centro notifiche persistente."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flask import current_app, g, has_app_context

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


def _runtime_config(config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if config is not None:
        return config
    return current_app.config if has_app_context() else {}


def notification_repository_settings(
    paths: Mapping[str, Any] | None = None,
    *,
    database: Any = None,
    config: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Risolve backend e path con lo stesso contratto per API e scheduler."""

    data_paths = paths or {}
    cfg = _runtime_config(config)
    configured = str(data_paths.get("NOTIFICATIONS_DB") or cfg.get("NOTIFICATIONS_DB") or "").strip()
    if configured:
        db_path = configured
    else:
        fallback = Path(str(data_paths.get("NOTIFICHE_LOG") or cfg.get("NOTIFICHE_LOG") or "./notifiche/log.json"))
        db_path = str(fallback.with_name("notifications.db"))
    postgres_dsn = resolve_runtime_postgres_dsn(
        database=database or data_paths.get("_TENANT_DATABASE_CONFIG"),
        config=cfg,
        env_url_keys=("IUSENTRA_NOTIFICATIONS_DATABASE_URL", "PCT_NOTIFICATIONS_DATABASE_URL"),
    )
    return db_path, postgres_dsn


def notifications_db_path() -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return notification_repository_settings(paths, config=current_app.config)[0]


def build_notification_repository_for_paths(
    paths: Mapping[str, Any] | None = None,
    *,
    database: Any = None,
    config: Mapping[str, Any] | None = None,
) -> NotificationRepository:
    db_path, postgres_dsn = notification_repository_settings(
        paths,
        database=database,
        config=config,
    )
    cache_key = f"{db_path}|{postgres_dsn}"
    if has_app_context():
        cache = current_app.extensions.setdefault("notification_repositories", {})
        repo = cache.get(cache_key)
        if isinstance(repo, NotificationRepository):
            return repo
    repo = NotificationRepository(db_path, postgres_dsn=postgres_dsn)
    if has_app_context():
        current_app.extensions["notification_repositories"][cache_key] = repo
    return repo


def build_notification_repository() -> NotificationRepository:
    paths = getattr(g, "data_paths", {}) or {}
    if getattr(g, "tenant_context_missing", False):
        notifications_db_path()
    tenant = tenant_corrente()
    return build_notification_repository_for_paths(
        paths,
        database=getattr(tenant, "database", None),
        config=current_app.config,
    )


def build_notification_service() -> NotificationService:
    return NotificationService(
        build_notification_repository(),
        web_push_config=load_web_push_config(current_app.config),
    )


def _core_backend_for_paths(paths: Mapping[str, Any], database: Any = None):
    studio_db_path = str(paths.get("STUDIO_DB") or "").strip()
    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    if database_config is not None and studio_db_path:
        try:
            from pct.core_storage_backend import build_core_storage_backend

            backend = build_core_storage_backend(database_config, studio_db_path=studio_db_path)
            if backend is not None:
                return backend
        except Exception:
            pass
    if studio_db_path and Path(studio_db_path).exists():
        try:
            from pct.storage import StudioDB

            return StudioDB.get(studio_db_path)
        except Exception:
            pass
    return None


def notification_recipients_for_paths(
    paths: Mapping[str, Any],
    *,
    database: Any = None,
) -> list[Any]:
    from pct.auth import GestioneUtenti

    auth_db = str(paths.get("AUTH_DB") or "./auth/utenti.json")
    backend = _core_backend_for_paths(paths, database)
    if not Path(auth_db).exists() and backend is None:
        return []
    audit_db = str(paths.get("AUDIT_DB") or "./auth/audit.json")
    secret = str(current_app.config.get("SECRET_KEY") or "scheduler") if has_app_context() else "scheduler"
    gestore = GestioneUtenti(
        db_path=auth_db,
        audit_path=audit_db,
        secret_key=secret,
        crea_admin_se_vuoto=False,
        studio_db=backend,
    )
    return list(gestore.tutti(solo_attivi=True))


def materialize_agenda_scadenziario_notifications_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    tenant_id: str = "",
    database: Any = None,
) -> dict[str, Any]:
    """Materializza centro notifiche e push senza dipendere dall'apertura UI."""

    from pct.agenda import Agenda
    from pct.scadenziario import GestioneScadenziario
    from web.services.topbar_operational import agenda_scadenziario_notification_items

    database_config = database or paths.get("_TENANT_DATABASE_CONFIG")
    backend = _core_backend_for_paths(paths, database_config)
    agenda = Agenda(
        db_path=str(paths.get("AGENDA_DB") or "./agenda/appuntamenti.json"),
        studio_db=backend,
    )
    scadenziario = GestioneScadenziario(
        db_path=str(paths.get("SCADENZIARIO_DB") or "./scadenziario/scadenze.json"),
        studio_db=backend,
    )
    recipients = notification_recipients_for_paths(paths, database=database_config)
    config = _runtime_config()
    service = NotificationService(
        build_notification_repository_for_paths(paths, database=database_config, config=config),
        web_push_config=load_web_push_config(config),
    )
    resolved_tenant_id = str(
        tenant_id
        or paths.get("_TENANT_NOTIFICATION_ID")
        or tenant_label
        or "default"
    ).strip()
    report = {
        "ok": True,
        "tenant": str(tenant_label or "default"),
        "source_of_truth": "notification repository SQLite/PostgreSQL tenant-aware",
        "recipients": 0,
        "items": 0,
        "errors": 0,
    }
    for user in recipients:
        try:
            can_agenda = not hasattr(user, "ha_permesso") or bool(user.ha_permesso("agenda.leggi"))
            can_scadenziario = not hasattr(user, "ha_permesso") or bool(user.ha_permesso("scadenziario.leggi"))
            if not can_agenda and not can_scadenziario:
                continue
            user_id = str(getattr(user, "id", "") or getattr(user, "username", "") or "").strip()
            if not user_id:
                continue
            items = agenda_scadenziario_notification_items(
                agenda,
                scadenziario,
                include_agenda=can_agenda,
                include_scadenziario=can_scadenziario,
            )
            service.sync_operational_items(
                tenant_id=resolved_tenant_id,
                user_id=user_id,
                items=items,
                expire_source_types={"deadline", "hearing", "task"},
            )
            report["recipients"] += 1
            report["items"] += len(items)
        except Exception:
            report["errors"] += 1
    report["ok"] = report["errors"] == 0
    return report
