from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flask import current_app, g, has_app_context

from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from web.services.feature_flags import (
    LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG,
    LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG,
    resolve_feature_flags,
)
from web.services.tenant_isolation_runtime import TenantIsolationError, assert_tenant_data_path
from web.services.tenant_paths import TenantDataPathError, tenant_data_path


class NotificationPresidiaUnavailable(RuntimeError):
    pass


def _global_rollout_flags(config: Mapping[str, Any] | None = None) -> tuple[bool, bool]:
    flags = resolve_feature_flags(config)
    return (
        bool(flags.get(LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG)),
        bool(flags.get(LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG)),
    )


def _tenant_id() -> str:
    if has_app_context() and getattr(g, "tenant_context_missing", False):
        raise TenantDataPathError("Contesto studio non disponibile per il presidio notifiche.")
    for value in (
        getattr(g, "api_tenant_slug", ""),
        getattr(g, "tenant_context_slug", ""),
        getattr(g, "tenant_slug", ""),
        getattr(g, "auth_tenant_slug", ""),
    ):
        candidate = str(value or "").strip()
        if candidate:
            return candidate
    tenant = getattr(g, "tenant", None) if has_app_context() else None
    for attr in ("slug", "id", "codice"):
        candidate = str(getattr(tenant, attr, "") or "").strip()
        if candidate:
            return candidate
    user = g.get("utente_corrente") if has_app_context() else None
    candidate = str(getattr(user, "tenant_slug", "") or "").strip()
    return candidate or "default"


def _presidio_db_path() -> Path:
    paths = getattr(g, "data_paths", {}) or {}
    configured = str(paths.get("PEC_AUDIT_DB") or current_app.config.get("PEC_AUDIT_DB") or "").strip()
    if configured:
        path = Path(configured)
    else:
        email_db = Path(tenant_data_path("EMAIL_CASELLA_DB", "./email/casella.json", require_tenant=True))
        path = email_db.parent / "pec_audit.sqlite"
    if current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False):
        return Path(assert_tenant_data_path(str(path), key="PEC_AUDIT_DB"))
    return path


def build_notification_presidio_repository():
    from pct.pec_notification_presidio import NotificationPresidioRepository

    try:
        tenant = getattr(g, "tenant", None)
        dsn = resolve_runtime_postgres_dsn(
            database=getattr(tenant, "database", None),
            config=current_app.config,
            env_url_keys=("IUSENTRA_PEC_AUDIT_DATABASE_URL", "PCT_PEC_AUDIT_DATABASE_URL"),
        )
        db_path = _presidio_db_path()
        key = (_tenant_id(), str(db_path), bool(dsn))
        cache = current_app.extensions.setdefault("notification_presidio_repositories", {})
        cached = cache.get(key)
        if cached is not None:
            return cached
        repo = NotificationPresidioRepository(db_path, tenant_id=key[0], postgres_dsn=dsn)
        cache[key] = repo
        return repo
    except (TenantDataPathError, TenantIsolationError):
        raise
    except Exception as exc:  # pragma: no cover - diagnostica governata
        current_app.logger.exception("Repository notifiche legali non disponibile")
        raise NotificationPresidiaUnavailable(str(exc)) from exc


def legal_notification_presidia_rollout(
    *,
    config: Mapping[str, Any] | None = None,
    repository_factory: Any | None = None,
    fail_closed_on_error: bool = True,
    global_enabled: bool | None = None,
    global_primary: bool | None = None,
) -> dict[str, Any]:
    if global_enabled is None or global_primary is None:
        global_enabled, global_primary = _global_rollout_flags(config)
    if not global_enabled:
        return {"enabled": False, "primary": False, "mode": "off", "reason": "global_flag_off"}
    try:
        repo = repository_factory() if repository_factory else build_notification_presidio_repository()
        tenant_config = repo.get_config()
    except Exception:
        if fail_closed_on_error:
            raise
        if has_app_context():
            current_app.logger.warning("Presidio notifiche disattivato: configurazione tenant non leggibile")
        return {"enabled": False, "primary": False, "mode": "off", "reason": "tenant_config_unavailable"}
    mode = str(tenant_config.get("rollout_mode") or "off").strip().lower()
    if mode not in {"off", "shadow", "primary"}:
        mode = "off"
    enabled = bool(tenant_config.get("rollout_enabled")) and mode != "off"
    primary = enabled and bool(global_primary) and mode == "primary"
    return {"enabled": enabled, "primary": primary, "mode": mode, "reason": "ok" if enabled else "tenant_rollout_off"}


def apply_legal_notification_presidia_effective_flags(
    flags: Mapping[str, Any],
    *,
    config: Mapping[str, Any] | None = None,
    repository_factory: Any | None = None,
) -> dict[str, Any]:
    result = dict(flags)
    enabled = bool(result.get(LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG))
    primary = bool(result.get(LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG))
    if not enabled:
        result[LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG] = False
        result[LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG] = False
        return result
    decision = legal_notification_presidia_rollout(
        config=config,
        repository_factory=repository_factory,
        fail_closed_on_error=False,
        global_enabled=enabled,
        global_primary=primary,
    )
    result[LEGAL_NOTIFICATION_PRESIDIA_ENABLED_FLAG] = bool(decision["enabled"])
    result[LEGAL_NOTIFICATION_PRESIDIA_PRIMARY_FLAG] = bool(decision["primary"])
    return result


def assert_notification_presidia_enabled() -> dict[str, Any]:
    decision = legal_notification_presidia_rollout(fail_closed_on_error=True)
    if not bool(decision["enabled"]):
        raise PermissionError("Il presidio notifiche legali non è attivo per questo studio.")
    return decision


def current_actor_id() -> str:
    user = g.get("utente_corrente")
    return str(getattr(user, "username", "") or getattr(user, "id", "") or "api")


def _can(permission: str) -> bool:
    user = g.get("utente_corrente")
    if not user:
        return True
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def presidio_permissions() -> dict[str, bool]:
    can_read = _can("messaggi.leggi")
    can_write = _can("messaggi.scrivi")
    return {
        "can_read": can_read,
        "can_write": can_write,
        "can_link_document": can_write and _can("fascicoli.scrivi"),
        "can_view_evidence": can_read and _can("fascicoli.leggi"),
        "can_configure": _can("admin.configura"),
    }


def public_permissions(permissions: Mapping[str, bool]) -> dict[str, bool]:
    return {key: bool(permissions.get(key)) for key in ("can_read", "can_write", "can_link_document", "can_view_evidence")}


def public_error(code: str, message: str, *, status: int = 400) -> tuple[dict[str, Any], int]:
    return {"ok": False, "code": code, "message": message, "status": status}, status


def mutate_presidio(repo: Any, presidio_id: str, mutation: str, body: Mapping[str, Any], *, idempotency_key: str) -> dict[str, Any]:
    permissions = presidio_permissions()
    if not permissions["can_write"]:
        raise PermissionError("Permesso messaggi.scrivi richiesto.")
    actor = current_actor_id()
    if mutation == "confirm":
        repo.transition(presidio_id, "NOTIFICATION_CONFIRMED", actor=actor, reason=str(body.get("reason") or "Notifica confermata dall'operatore."), evidence={"source": "ui_presidio"}, idempotency_key=idempotency_key)
    elif mutation == "not-required":
        reason = str(body.get("reason") or "").strip()
        if len(reason) < 8:
            raise ValueError("Inserisci una motivazione chiara per segnare la notifica come non necessaria.")
        repo.transition(presidio_id, "NOT_REQUIRED", actor=actor, reason=reason, evidence={"source": "ui_presidio"}, idempotency_key=idempotency_key)
    elif mutation == "assign":
        repo.assign_presidio(presidio_id, str(body.get("assigned_user_id") or body.get("assigned_user") or ""), actor=actor, reason=str(body.get("reason") or ""), idempotency_key=idempotency_key)
    elif mutation == "link-document":
        if not permissions["can_link_document"]:
            raise PermissionError("Permesso fascicoli.scrivi richiesto per collegare documenti.")
        document_id = str(body.get("document_id") or body.get("fascicolo_document_id") or "").strip()
        if not document_id:
            raise ValueError("Documento da collegare mancante.")
        repo.upsert_document(presidio_id, {"fascicolo_document_id": document_id, "document_role": str(body.get("document_role") or "notified_act"), "original_filename": str(body.get("document_name") or document_id), "content_sha256": str(body.get("content_sha256") or "")})
        repo.append_evidence(presidio_id, {"evidence_type": "human_decision", "source_type": "document", "source_id": document_id, "text_excerpt": "Documento collegato manualmente dal pannello Notifiche Legali.", "confidence": 1.0})
    elif mutation in {"reconcile", "retry"}:
        from pct.pec_notification_presidio import NotificationPresidioWorkQueue

        queue = NotificationPresidioWorkQueue(repo)
        job_type = "reconcile_presidio" if mutation == "reconcile" else "retry_presidio"
        queue.enqueue(job_type, {"presidio_id": presidio_id}, idempotency_key=idempotency_key, priority=1)
    else:
        raise ValueError("Operazione non supportata.")
    from web.services.notification_presidia_payloads import build_presidio_detail_payload

    return build_presidio_detail_payload(repo, presidio_id)
