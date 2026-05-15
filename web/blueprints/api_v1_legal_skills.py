"""API JSON governate per il Legal Skills Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Mapping

from flask import Blueprint, current_app, g, jsonify, request

from lex.legal_skills import (
    LegalSkillProfileStore,
    LegalSkillRegistry,
    LegalSkillTrustLayer,
    LegalSkillWorkflowEngine,
    ScheduledLegalAgentsService,
    SkillRunRequest,
    SkillRunStorage,
)
from lex.legal_skills.exceptions import LegalSkillsError
from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from web.services.feature_flags import feature_disabled_response, is_feature_enabled
from web.services.tenant_api_auth import api_key_valid_for_request
from web.services.tenant_paths import TenantDataPathError, tenant_data_path


api_v1_legal_skills = Blueprint("api_v1_legal_skills", __name__, url_prefix="/api/v1/legal-skills")


def _api_key_valida() -> bool:
    return api_key_valid_for_request()


def _core_runtime_func(name: str) -> Callable[..., Any] | None:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    func = core_runtime.get(name)
    return func if callable(func) else None


def _audit_event(action: str, resource_type: str = "", resource_id: str = "", details: str = "") -> None:
    audit = _core_runtime_func("audit")
    if callable(audit):
        audit(action, resource_type, resource_id, details)


def _actor_label() -> str:
    utente = g.get("utente_corrente")
    return str(
        getattr(utente, "nome_completo", "")
        or getattr(utente, "username", "")
        or getattr(utente, "email", "")
        or "operatore"
    )


def _user_roles() -> list[str]:
    utente = g.get("utente_corrente")
    ruolo = getattr(utente, "ruolo", "")
    role_value = getattr(ruolo, "value", str(ruolo or ""))
    return [role_value] if role_value else []


def _has_permission(permission: str) -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)(permission))


def _json_payload() -> dict[str, Any]:
    raw = request.get_json(silent=True) if request.is_json else request.form.to_dict()
    if not isinstance(raw, Mapping):
        return {}
    blocked = {"tenant_id", "studio_id", "tenant", "studio"}
    return {str(key): value for key, value in raw.items() if str(key) not in blocked}


def _require_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "code": "unauthorized", "message": "Autenticazione richiesta."}), 401

    return wrapper


def _require_feature(flag_key: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if is_feature_enabled(flag_key):
                return func(*args, **kwargs)
            return feature_disabled_response(flag_key)

        return wrapper

    return decorator


def _require_permission(permission: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if _has_permission(permission):
                return func(*args, **kwargs)
            _audit_event("policy_denied.legal_skills", "permission", permission, "Permesso Legal Skills mancante.")
            return jsonify({"ok": False, "code": "permission_denied", "message": "Permesso non disponibile."}), 403

        return wrapper

    return decorator


@api_v1_legal_skills.errorhandler(TenantDataPathError)
def _tenant_data_path_error(error: TenantDataPathError):
    return jsonify({"ok": False, "code": "tenant_context_required", "message": str(error)}), 409


@api_v1_legal_skills.errorhandler(LegalSkillsError)
def _legal_skills_error(error: LegalSkillsError):
    _audit_event("legal_skills_error", "legal_skills", getattr(error, "code", ""), str(error))
    return jsonify({"ok": False, "code": error.code, "message": str(error)}), int(error.status_code)


@api_v1_legal_skills.before_request
def _backend_security_guard():
    if not (g.get("utente_corrente") or _api_key_valida()):
        return None
    violations = backend_control_violations_for_request(request)
    if not violations:
        return None
    keys = ",".join(sorted({violation.key for violation in violations}))
    _audit_event("policy_denied.backend_security", "legal_skills", request.path, f"Parametri riservati bloccati: {keys}.")
    return backend_security_error_response(violations)


def _registry() -> LegalSkillRegistry:
    return LegalSkillRegistry(feature_enabled=is_feature_enabled, custom_enabled=is_feature_enabled)


def _profile_store() -> LegalSkillProfileStore:
    path = tenant_data_path(
        "LEGAL_SKILLS_PROFILE_DB",
        "./data/intelligence/legal_skills/profile.json",
        require_tenant=True,
    )
    return LegalSkillProfileStore(path, audit=_audit_event)


def _runs_storage() -> SkillRunStorage:
    path = tenant_data_path(
        "LEGAL_SKILLS_RUNS_DB",
        "./data/intelligence/legal_skills/runs.json",
        require_tenant=True,
    )
    return SkillRunStorage(path)


def _scheduled_service() -> ScheduledLegalAgentsService:
    path = tenant_data_path(
        "LEGAL_SKILLS_SCHEDULED_DB",
        "./data/intelligence/legal_skills/scheduled.json",
        require_tenant=True,
    )
    return ScheduledLegalAgentsService(path)


def _workflow() -> LegalSkillWorkflowEngine:
    return LegalSkillWorkflowEngine(
        registry=_registry(),
        profile_store=_profile_store(),
        storage=_runs_storage(),
        audit=_audit_event,
    )


@api_v1_legal_skills.get("/packs")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def list_packs():
    packs = [pack.to_public_dict(include_skills=False) for pack in _registry().list_packs()]
    return jsonify({"ok": True, "packs": packs})


@api_v1_legal_skills.get("/packs/<pack_id>")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def get_pack(pack_id: str):
    return jsonify({"ok": True, "pack": _registry().get_pack(pack_id).to_public_dict(include_skills=True)})


@api_v1_legal_skills.get("/packs/<pack_id>/skills")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def list_skills(pack_id: str):
    skills = [skill.to_public_dict() for skill in _registry().list_skills(pack_id)]
    return jsonify({"ok": True, "skills": skills})


@api_v1_legal_skills.get("/packs/<pack_id>/skills/<skill_id>")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def get_skill(pack_id: str, skill_id: str):
    return jsonify({"ok": True, "skill": _registry().get_skill(pack_id, skill_id).to_public_dict()})


@api_v1_legal_skills.get("/profile")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def get_profile():
    return jsonify(_profile_store().placeholder_report())


@api_v1_legal_skills.post("/profile/cold-start")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.profilo.scrivi")
def cold_start_profile():
    profile = _profile_store().cold_start(_json_payload(), actor=_actor_label())
    return jsonify({"ok": True, "profile": profile.to_public_dict()})


@api_v1_legal_skills.post("/run")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.esegui")
def run_skill():
    result = _workflow().run(SkillRunRequest.from_payload(_json_payload()), actor=_actor_label(), user_roles=_user_roles())
    return jsonify({"ok": True, "result": result.to_public_dict()})


@api_v1_legal_skills.get("/runs/<run_id>")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def get_run(run_id: str):
    return jsonify({"ok": True, "result": _runs_storage().get(run_id)})


@api_v1_legal_skills.post("/runs/<run_id>/approve")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.approva")
def approve_run(run_id: str):
    updated = _runs_storage().update(
        run_id,
        {
            "approved_at": current_app.config.get("TEST_APPROVAL_TIMESTAMP")
            or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "approved_by": _actor_label(),
            "needs_review": False,
        },
    )
    _audit_event("legal_skills_run_approved", "legal_skills", run_id, "Risultato Legal Skills approvato.")
    return jsonify({"ok": True, "result": updated})


@api_v1_legal_skills.post("/runs/<run_id>/export")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.esporta")
def export_run(run_id: str):
    result = _runs_storage().get(run_id)
    if result.get("disable_exports") or not result.get("approved_at"):
        return jsonify({"ok": False, "code": "export_blocked", "message": "Esportazione disponibile solo dopo revisione e approvazione."}), 409
    _audit_event("legal_skills_run_exported", "legal_skills", run_id, "Risultato Legal Skills esportato.")
    return jsonify({"ok": True, "export": {"format": "json", "result": result}})


@api_v1_legal_skills.post("/trust/check")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_feature("lex.legalSkills.trustLayer")
@_require_permission("legal_skills.trust_check")
def trust_check():
    payload = _json_payload()
    raw_skill = str(payload.get("skill_markdown") or payload.get("content") or "")
    result = LegalSkillTrustLayer().check_raw_skill(raw_skill, metadata={"builtin": False})
    _audit_event("legal_skills_trust_checked", "legal_skills_trust", result.verdict, "Controllo fiducia completato.")
    return jsonify({"ok": True, "trust": result.to_public_dict()})


@api_v1_legal_skills.get("/scheduled")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_feature("lex.legalSkills.scheduledAgents")
@_require_permission("legal_skills.scheduled.esegui")
def list_scheduled_agents():
    enabled = is_feature_enabled("lex.legalSkills.scheduledAgents")
    return jsonify({"ok": True, "agents": [agent.to_public_dict() for agent in _scheduled_service().list_agents(enabled=enabled)]})


@api_v1_legal_skills.post("/scheduled/<agent_id>/run-now")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_feature("lex.legalSkills.scheduledAgents")
@_require_permission("legal_skills.scheduled.esegui")
def run_scheduled_agent(agent_id: str):
    try:
        result = _scheduled_service().run_now(agent_id, enabled=is_feature_enabled("lex.legalSkills.scheduledAgents"))
    except KeyError:
        return jsonify({"ok": False, "code": "agent_not_found", "message": "Agente Legal Skills non trovato."}), 404
    _audit_event("legal_skills_scheduled_run", "legal_skills_agent", agent_id, "Agente Legal Skills eseguito manualmente.")
    return jsonify({"ok": True, "result": result.to_public_dict()})


__all__ = ["api_v1_legal_skills"]
