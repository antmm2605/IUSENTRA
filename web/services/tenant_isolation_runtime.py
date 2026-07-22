"""Fail-closed tenant isolation runtime for private data surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, current_app, g, has_app_context, has_request_context, jsonify, request, session

from pct.tenant import GestioneTenant
from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from web.services.tenant_api_auth import attach_api_tenant_context_from_headers


TENANT_CONTEXT_REQUIRED_MESSAGE = (
    "Contesto studio non disponibile per la richiesta corrente. "
    "Accesso ai dati bloccato per evitare letture cross-studio."
)
TENANT_FORBIDDEN_MESSAGE = "Accesso allo studio non autorizzato."
TENANT_PATH_FORBIDDEN_MESSAGE = "Percorso dati non consentito per lo studio corrente."
TENANT_API_FORBIDDEN_MESSAGE = "Autenticazione API non valida per lo studio indicato."

TENANT_SENSITIVE_PATH_KEYS = frozenset(
    {
        "CLIENTI_DB",
        "FASCICOLI_DB",
        "FASCICOLI_DOCS",
        "FASCICOLI_ARCH",
        "DOCUMENTI_AI_DIR",
        "DOCUMENTI_AI_DB",
        "EDITOR_AI_DB",
        "FASCICOLI_IMPORTAZIONI_DIR",
        "PEC_CANCELLERIA_STATE_DB",
        "AGENDA_DB",
        "CALENDAR_SYNC_DB",
        "CALENDAR_SYNC_ENGINE_DB",
        "CALENDAR_CONFLICTS_DB",
        "CALENDAR_TOKEN_DB",
        "SCADENZIARIO_DB",
        "TERMINI_PROCESSUALI_DB",
        "MESSAGGI_DB",
        "EMAIL_CASELLA_DB",
        "EMAIL_ORDINARIA_DB",
        "PEC_AUDIT_DB",
        "NOTIFICATIONS_DB",
        "FATTURAZIONE_DB",
        "PREVENTIVI_DB",
        "PREVENTIVI_REPOSITORY_DB",
        "PREVENTIVI_WORKFLOW_STATES_DB",
        "PREVENTIVI_FIELD_MAP_DB",
        "PREVENTIVI_RULES_DB",
        "PRIVACY_DB",
        "AUDIT_DB",
        "AUTH_DB",
        "STORAGE_CONFIG",
        "STUDIO_LOCAL_PACK_DB",
        "BACKUP_DIR",
        "SEARCH_INDEX",
        "TELEMATICO_DB",
        "TELEMATICO_ACTIONS_REPOSITORY_DB",
        "TELEMATICO_CAPABILITIES_REPOSITORY_DB",
        "TELEMATICO_CATALOG_SNAPSHOT_DB",
        "TELEMATICO_CATALOG_SOURCES_REPOSITORY_DB",
        "TELEMATICO_METHODS_REPOSITORY_DB",
        "TELEMATICO_MONITORING_REPOSITORY_DB",
        "TELEMATICO_REPOSITORY_JSON",
        "TELEMATICO_RULES_REPOSITORY_DB",
        "TELEMATICO_SOURCES_REPOSITORY_DB",
        "TELEMATICO_WIZARD_SECTIONS_REPOSITORY_DB",
        "TELEMATICO_WSDL_MODULES_REPOSITORY_DB",
        "TELEMATICO_XSD_CHANNELS_REPOSITORY_DB",
        "PDP_PENALE_DB",
        "TEMPLATE_ATTI_DB",
        "TEMPLATE_REPOSITORY_DB",
        "WORKSPACE_INTELLIGENCE_DB",
        "LEGAL_INTELLIGENCE_DB",
        "GIURISPRUDENZA_REPOSITORY_DB",
        "GIURISPRUDENZA_SOURCES_REPOSITORY_DB",
        "GIURISPRUDENZA_SYNC_REGISTRY_DB",
        "GIURISPRUDENZA_TAXONOMY_REPOSITORY_DB",
        "GIURISPRUDENZA_USAGE_POLICY_DB",
        "LEGAL_ENGINE_SOURCE_EDGES_DB",
        "LEGAL_ENGINES_REPOSITORY_DB",
        "LEGAL_INTELLIGENCE_REPOSITORY_DB",
        "LEGAL_KEYWORD_TO_ENGINE_DB",
        "LEGAL_KEYWORD_TO_SOURCE_DB",
        "LEGAL_OPERATIONAL_REPOSITORY_DB",
        "LEGAL_SOURCES_REPOSITORY_DB",
        "LEX_DATASET_DIR",
        "LEGAL_SKILLS_DIR",
        "LEGAL_SKILLS_PROFILE_DB",
        "LEGAL_SKILLS_RUNS_DB",
        "LEGAL_SKILLS_SCHEDULED_DB",
        "WORKFLOW_AGENTS_RUNS_DB",
        "WORKFLOW_AGENTS_METRICS_DB",
        "WORKFLOW_AGENTS_ACTIONS_DB",
        "GIURISPRUDENZA_DB",
    }
)


class TenantIsolationError(RuntimeError):
    """Controlled tenant isolation violation without leaking internals."""

    def __init__(self, message: str, *, status_code: int = 403, code: str = "tenant_isolation_error"):
        super().__init__(message)
        self.public_message = message
        self.status_code = status_code
        self.code = code


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _multi_tenant_enabled() -> bool:
    if not has_app_context():
        return False
    return bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False))


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _request_wants_json() -> bool:
    if not has_request_context():
        return False
    path = _text(request.path).lower()
    if path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"


def _public_request() -> bool:
    if not has_request_context():
        return False

    endpoint = _text(request.endpoint).lower()
    path = _text(request.path).lower()
    blueprint = _text(request.blueprint).lower()

    if request.method == "OPTIONS":
        return True
    if endpoint in {
        "login",
        "login_2fa",
        "logout",
        "static",
        "service_worker",
        "web_manifest",
        "offline",
        "health_live",
        "health_ready",
        "health_dependencies",
        "prometheus_metrics",
    }:
        return True
    if endpoint.startswith("static"):
        return True
    if blueprint in {"studio_site_public"}:
        return True
    if path in {
        "/login",
        "/logout",
        "/sw.js",
        "/manifest.webmanifest",
        "/offline",
        "/api/pronto",
        "/api/live",
        "/api/ready",
        "/metrics",
    }:
        return True
    if path in {"/api/v1", "/api/v1/"}:
        return True
    if path == "/api/v1/ui/client-portal/public" or path.startswith("/api/v1/ui/client-portal/public/"):
        return True
    return path.startswith((
        "/static/",
        "/polisweb/local-signer/download",
        "/web/",
        "/support/join/",
        "/support/operatore/",
        "/support/api/",
        "/support/ws/",
    ))


def _platform_surface_for_superadmin() -> bool:
    if not has_request_context():
        return False
    blueprint = _text(request.blueprint).lower()
    path = _text(request.path).lower()
    endpoint = _text(request.endpoint).lower()
    allowed_blueprints = {
        "admin",
        "assistente",
        "installation_pack_admin",
        "legal_coverage_admin",
        "legal_updates_admin",
        "operational_resilience_admin",
        "scheduler_admin",
        "server_maintenance_admin",
        "legal_intelligence",
        "support_remote",
        "studio_site_admin",
    }
    if blueprint in allowed_blueprints:
        return True
    if endpoint.startswith("admin."):
        return True
    return path.startswith(("/admin/", "/api/assistente"))


def _tenant_slug_from_context() -> str:
    tenant = getattr(g, "tenant", None)
    return (
        _text(getattr(tenant, "slug", "")).lower()
        or _text(getattr(g, "tenant_context_slug", "")).lower()
        or _text(getattr(g, "api_tenant_slug", "")).lower()
        or _text(session.get("tenant_slug") if has_request_context() else "").lower()
    )


def _expected_tenant_root() -> Path:
    slug = _tenant_slug_from_context()
    request_paths = (getattr(g, "data_paths", {}) or {}) if has_request_context() else {}
    if not slug:
        studio_db = _text(request_paths.get("STUDIO_DB"))
        if studio_db:
            return Path(studio_db).expanduser().resolve().parent
        raise TenantIsolationError(
            TENANT_CONTEXT_REQUIRED_MESSAGE,
            status_code=409,
            code="tenant_context_required",
        )
    registry = _text(current_app.config.get("TENANTS_REGISTRY"))
    if not registry:
        raise TenantIsolationError(
            TENANT_CONTEXT_REQUIRED_MESSAGE,
            status_code=409,
            code="tenant_registry_required",
        )
    try:
        paths = GestioneTenant(registry_path=registry).percorsi_dati(slug, reconcile_aliases=False)
    except Exception as exc:
        current_app.logger.warning("Tenant isolation: registry non risolve lo studio %s (%s)", slug, exc)
        raise TenantIsolationError(
            TENANT_CONTEXT_REQUIRED_MESSAGE,
            status_code=409,
            code="tenant_registry_required",
        ) from exc
    studio_db = _text(paths.get("STUDIO_DB"))
    if not studio_db:
        raise TenantIsolationError(
            TENANT_CONTEXT_REQUIRED_MESSAGE,
            status_code=409,
            code="tenant_root_required",
        )
    return Path(studio_db).expanduser().resolve().parent


def assert_tenant_data_path(path: str | Path, key: str = "") -> str:
    """Return a resolved path only if it stays inside the current tenant root."""

    resolved = Path(path).expanduser().resolve()
    if not _multi_tenant_enabled():
        return str(resolved)
    if not has_request_context():
        raise TenantIsolationError(
            TENANT_CONTEXT_REQUIRED_MESSAGE,
            status_code=409,
            code="tenant_context_required",
        )

    tenant_root = _expected_tenant_root()
    if not _path_is_relative_to(resolved, tenant_root):
        current_app.logger.warning(
            "Tenant isolation: percorso dati bloccato key=%s tenant=%s",
            _text(key) or "-",
            _tenant_slug_from_context() or "-",
        )
        raise TenantIsolationError(
            TENANT_PATH_FORBIDDEN_MESSAGE,
            status_code=403,
            code="tenant_path_forbidden",
        )
    return str(resolved)


def _normalise_derived_sensitive_paths(paths: dict[str, Any]) -> None:
    """Populate tenant-bound derived paths before fail-closed validation."""

    if not _text(paths.get("PEC_AUDIT_DB")):
        email_db = _text(paths.get("EMAIL_CASELLA_DB"))
        if email_db:
            paths["PEC_AUDIT_DB"] = str(Path(email_db).expanduser().resolve().parent / "pec_audit.sqlite")


def _assert_sensitive_paths(paths: dict[str, Any]) -> None:
    _normalise_derived_sensitive_paths(paths)
    missing = sorted(key for key in TENANT_SENSITIVE_PATH_KEYS if not _text(paths.get(key)))
    if missing:
        current_app.logger.warning(
            "Tenant isolation: percorsi dati incompleti tenant=%s missing=%s",
            _tenant_slug_from_context() or "-",
            ",".join(missing),
        )
        raise TenantIsolationError(
            TENANT_CONTEXT_REQUIRED_MESSAGE,
            status_code=409,
            code="tenant_data_paths_required",
        )
    for key in TENANT_SENSITIVE_PATH_KEYS:
        assert_tenant_data_path(_text(paths[key]), key=key)


def ensure_private_tenant_context() -> None:
    """Enforce tenant context for private data routes in multi-tenant mode."""

    if not _multi_tenant_enabled() or _public_request():
        return

    api_key_present = bool(_text(request.headers.get("X-API-Key"))) if has_request_context() else False
    api_context = attach_api_tenant_context_from_headers() if api_key_present else None
    if api_key_present and not getattr(api_context, "valid", False):
        reason = str(getattr(api_context, "reason", "") or "")
        if reason in {"tenant_context_required", "tenant_slug_missing_or_mismatch"}:
            raise TenantIsolationError(
                TENANT_CONTEXT_REQUIRED_MESSAGE,
                status_code=409,
                code="tenant_context_required",
            )
        raise TenantIsolationError(
            TENANT_API_FORBIDDEN_MESSAGE,
            status_code=int(getattr(api_context, "status_code", 401) or 401),
            code=reason or "tenant_api_invalid",
        )

    user = g.get("utente_corrente") if has_request_context() else None
    user_is_superadmin = bool(getattr(user, "is_superadmin", False))

    if user_is_superadmin and not session.get("superadmin_user_id"):
        if _platform_surface_for_superadmin():
            return
        raise TenantIsolationError(
            TENANT_FORBIDDEN_MESSAGE,
            status_code=403,
            code="superadmin_tenant_context_required",
        )

    if not user and not getattr(api_context, "valid", False):
        if _text(request.path).lower().startswith("/api/"):
            raise TenantIsolationError(
                "Autenticazione richiesta.",
                status_code=401,
                code="authentication_required",
            )
        return

    tenant_slug = _tenant_slug_from_context()
    paths = getattr(g, "data_paths", {}) or {}
    if not tenant_slug or not getattr(g, "tenant", None) or not paths:
        raise TenantIsolationError(
            TENANT_CONTEXT_REQUIRED_MESSAGE,
            status_code=409,
            code="tenant_context_required",
        )

    if getattr(api_context, "valid", False):
        api_slug = _text(getattr(api_context, "tenant_slug", "")).lower()
        if api_slug and api_slug != tenant_slug:
            raise TenantIsolationError(
                TENANT_API_FORBIDDEN_MESSAGE,
                status_code=403,
                code="tenant_api_slug_mismatch",
            )

    if user and not user_is_superadmin:
        user_slug = _text(getattr(user, "tenant_slug", "")).lower()
        auth_slug = _text(getattr(g, "utente_auth_tenant_slug", "")).lower()
        if user_slug and user_slug != tenant_slug:
            raise TenantIsolationError(
                TENANT_FORBIDDEN_MESSAGE,
                status_code=403,
                code="user_tenant_mismatch",
            )
        if auth_slug and auth_slug != tenant_slug:
            raise TenantIsolationError(
                TENANT_FORBIDDEN_MESSAGE,
                status_code=403,
                code="session_tenant_mismatch",
            )

    _assert_sensitive_paths(paths)


def _error_response(error: TenantIsolationError):
    status = int(error.status_code or 403)
    current_app.logger.warning(
        "Tenant isolation blocked request: code=%s status=%s path=%s tenant=%s",
        error.code,
        status,
        _text(request.path) or "-",
        _tenant_slug_from_context() or "-",
    )
    _audit_tenant_denial(error, status=status)
    if _request_wants_json():
        return jsonify({"ok": False, "errore": error.public_message, "codice": error.code}), status
    return current_app.response_class(error.public_message, status=status, mimetype="text/plain")


def _audit_tenant_denial(error: TenantIsolationError, *, status: int) -> None:
    """Registra denial tenant senza valori client, token o path filesystem."""

    try:
        from pct.auth import GestioneUtenti

        paths = getattr(g, "data_paths", {}) or {}
        auth_path = _text(paths.get("AUTH_DB")) or _text(current_app.config.get("AUTH_DB"))
        audit_path = _text(paths.get("AUDIT_DB")) or _text(current_app.config.get("AUDIT_DB"))
        if not auth_path or not audit_path:
            return

        manager = GestioneUtenti(
            db_path=auth_path,
            audit_path=audit_path,
            secret_key=_text(current_app.secret_key),
            crea_admin_se_vuoto=False,
        )
        user = g.get("utente_corrente") if has_request_context() else None
        manager.registra_evento(
            "policy_denied.tenant_isolation",
            id_utente=_text(getattr(user, "id", "")),
            username=_text(getattr(user, "username", "")) or "anonimo",
            risorsa_tipo="api",
            risorsa_id=_text(request.path) if has_request_context() else "",
            dettagli=f"codice={error.code}; status={status}",
            ip=_text(request.remote_addr) if has_request_context() else "",
            esito="DENIED",
        )
    except Exception as exc:  # pragma: no cover - audit best-effort
        current_app.logger.warning("Audit denial tenant non registrato: %s", exc.__class__.__name__)


def _authenticated_for_backend_security() -> bool:
    if not has_request_context():
        return False
    if g.get("utente_corrente"):
        return True
    if not _text(request.headers.get("X-API-Key")):
        return False
    context = attach_api_tenant_context_from_headers()
    return bool(getattr(context, "valid", False))


def _audit_backend_security_denial(violations: list[Any]) -> None:
    """Registra denial backend senza valori client, token o path filesystem."""

    try:
        from pct.auth import GestioneUtenti

        paths = getattr(g, "data_paths", {}) or {}
        auth_path = _text(paths.get("AUTH_DB")) or _text(current_app.config.get("AUTH_DB"))
        audit_path = _text(paths.get("AUDIT_DB")) or _text(current_app.config.get("AUDIT_DB"))
        if not auth_path or not audit_path:
            return

        keys = ",".join(sorted({_text(getattr(violation, "key", "")) for violation in violations if _text(getattr(violation, "key", ""))}))
        manager = GestioneUtenti(
            db_path=auth_path,
            audit_path=audit_path,
            secret_key=_text(current_app.secret_key),
            crea_admin_se_vuoto=False,
        )
        user = g.get("utente_corrente") if has_request_context() else None
        manager.registra_evento(
            "policy_denied.backend_security",
            id_utente=_text(getattr(user, "id", "")),
            username=_text(getattr(user, "username", "")) or "api",
            risorsa_tipo="api_ui",
            risorsa_id=_text(request.endpoint) or _text(request.path),
            dettagli=f"Parametri riservati bloccati: {keys}.",
            ip=_text(request.remote_addr) if has_request_context() else "",
            esito="DENIED",
        )
    except Exception as exc:  # pragma: no cover - audit best-effort
        current_app.logger.warning("Audit denial backend non registrato: %s", exc.__class__.__name__)


def register_tenant_isolation_runtime(app: Flask) -> None:
    """Register fail-closed tenant isolation middleware."""

    @app.before_request
    def enforce_tenant_isolation_runtime():
        try:
            ensure_private_tenant_context()
        except TenantIsolationError as exc:
            return _error_response(exc)
        return None

    @app.before_request
    def enforce_ui_api_backend_security_runtime():
        if request.method == "OPTIONS":
            return None
        if not _text(request.path).lower().startswith("/api/v1/ui/"):
            return None
        if not _authenticated_for_backend_security():
            return None

        violations = backend_control_violations_for_request(request)
        if not violations:
            return None

        keys = ",".join(sorted({violation.key for violation in violations}))
        current_app.logger.warning(
            "policy_denied backend_security_control_param path=%s method=%s keys=%s",
            _text(request.path) or "-",
            _text(request.method) or "-",
            keys or "-",
        )
        _audit_backend_security_denial(violations)
        return backend_security_error_response(violations)


__all__ = [
    "TENANT_SENSITIVE_PATH_KEYS",
    "TenantIsolationError",
    "assert_tenant_data_path",
    "ensure_private_tenant_context",
    "register_tenant_isolation_runtime",
]
