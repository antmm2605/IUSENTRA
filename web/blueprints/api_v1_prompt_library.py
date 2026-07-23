"""API JSON governate per la libreria prompt "LegalSkills Italia".

Espone il catalogo read-only (26 aree del diritto) con ricerca su tutto
il contenuto e composizione del prompt nelle varie forme. Stesse guardie
del Legal Skills Engine: autenticazione, feature flag, permesso
``legal_skills.leggi`` e blocco dei parametri riservati.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from lex.legal_skills.exceptions import LegalSkillsError
from lex.legal_skills.prompt_library import get_prompt_library
from web.blueprints.api_v1_legal_skills import (
    _api_key_valida,
    _audit_event,
    _require_auth,
    _require_feature,
    _require_permission,
)
from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)

api_v1_prompt_library = Blueprint(
    "api_v1_prompt_library", __name__, url_prefix="/api/v1/legal-skills/prompt-library"
)

_MAX_RISULTATI = 1400


@api_v1_prompt_library.errorhandler(LegalSkillsError)
def _prompt_library_error(error: LegalSkillsError):
    _audit_event("legal_skills_error", "prompt_library", getattr(error, "code", ""), str(error))
    return jsonify({"ok": False, "code": error.code, "message": str(error)}), int(error.status_code)


@api_v1_prompt_library.before_request
def _backend_security_guard():
    if not (g.get("utente_corrente") or _api_key_valida()):
        return None
    violations = backend_control_violations_for_request(request)
    if not violations:
        return None
    keys = ",".join(sorted({violation.key for violation in violations}))
    _audit_event(
        "policy_denied.backend_security", "prompt_library", request.path, f"Parametri riservati bloccati: {keys}."
    )
    return backend_security_error_response(violations)


def _limit_param() -> int:
    try:
        limit = int(request.args.get("limit", 0))
    except (TypeError, ValueError):
        limit = 0
    if limit <= 0 or limit > _MAX_RISULTATI:
        return _MAX_RISULTATI
    return limit


@api_v1_prompt_library.get("/aree")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def list_aree():
    library = get_prompt_library()
    return jsonify(
        {
            "ok": True,
            "totale_prompt": library.totale_prompt(),
            "aree": [area.to_public_dict() for area in library.aree()],
            "forme": library.forme(),
        }
    )


@api_v1_prompt_library.get("/prompts")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def search_prompts():
    library = get_prompt_library()
    risultati = library.search(
        query=request.args.get("q", ""),
        area=request.args.get("area", ""),
        forma=request.args.get("forma", ""),
        limit=_limit_param(),
    )
    return jsonify({"ok": True, "totale": len(risultati), "prompts": risultati})


@api_v1_prompt_library.get("/prompts/<prompt_id>")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def get_prompt(prompt_id: str):
    prompt = get_prompt_library().get_prompt(prompt_id)
    _audit_event("legal_skills_prompt_letto", "prompt_library", prompt_id, "Prompt LegalSkills Italia consultato.")
    return jsonify({"ok": True, "prompt": prompt})


__all__ = ["api_v1_prompt_library"]
