"""API JSON governate per la libreria prompt "LegalSkills Italia".

Espone il catalogo read-only (26 aree del diritto) con ricerca su tutto
il contenuto e composizione del prompt nelle varie forme. Stesse guardie
del Legal Skills Engine: autenticazione, feature flag, permesso
``legal_skills.leggi`` e blocco dei parametri riservati.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from lex.legal_skills.exceptions import LegalSkillsError
from lex.legal_skills.prompt_library import (
    aree_preferite_da_profilo,
    get_prompt_library,
    prepara_esecuzione_prompt,
)
from web.blueprints.api_v1_legal_skills import (
    _actor_label,
    _api_key_valida,
    _audit_event,
    _has_permission,
    _json_payload,
    _profile_store,
    _require_auth,
    _require_feature,
    _require_permission,
    _runs_storage,
    _user_roles,
    _workflow,
)
from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from web.services.prompt_library_fascicolo_bridge import costruisci_contesto_fascicolo

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


def _aree_preferite_studio(aree_disponibili: set[str]) -> list[str]:
    """Aree praticate dallo studio secondo il PracticeProfile; vuoto se non configurato."""
    try:
        profile = _profile_store().load()
    except Exception:
        return []
    practice_areas = list(getattr(profile, "practice_areas", []) or [])
    return aree_preferite_da_profilo(practice_areas, aree_disponibili)


@api_v1_prompt_library.get("/aree")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def list_aree():
    library = get_prompt_library()
    aree = library.aree()
    preferite = _aree_preferite_studio({area.area_id for area in aree})
    payload_aree = []
    for area in aree:
        dati = area.to_public_dict()
        dati["preferita"] = area.area_id in preferite
        payload_aree.append(dati)
    payload_aree.sort(key=lambda dati: (not dati["preferita"], dati["nome"].lower()))
    return jsonify(
        {
            "ok": True,
            "totale_prompt": library.totale_prompt(),
            "aree": payload_aree,
            "forme": library.forme(),
            "aree_preferite": preferite,
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


def _risolvi_contesto(fascicolo_id: str):
    """Contesto dal fascicolo o risposta d'errore governata (tupla Flask)."""
    if not fascicolo_id:
        return None
    if not _has_permission("fascicoli.leggi"):
        _audit_event("policy_denied.legal_skills", "permission", "fascicoli.leggi", "Contesto fascicolo prompt negato.")
        return jsonify({"ok": False, "code": "permission_denied", "message": "Permesso fascicoli mancante."}), 403
    contesto = costruisci_contesto_fascicolo(fascicolo_id)
    if contesto is None:
        return jsonify({"ok": False, "code": "fascicolo_not_found", "message": "Fascicolo non trovato."}), 404
    return contesto


@api_v1_prompt_library.get("/prompts/<prompt_id>")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def get_prompt(prompt_id: str):
    contesto = _risolvi_contesto(str(request.args.get("fascicolo", "") or "").strip())
    if isinstance(contesto, tuple):
        return contesto
    prompt = get_prompt_library().get_prompt(prompt_id, contesto=contesto)
    _audit_event("legal_skills_prompt_letto", "prompt_library", prompt_id, "Prompt LegalSkills Italia consultato.")
    return jsonify({"ok": True, "prompt": prompt})


@api_v1_prompt_library.post("/run")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.esegui")
def run_prompt():
    payload = _json_payload()
    prompt_id = str(payload.get("prompt_id") or "").strip()
    contesto = _risolvi_contesto(str(payload.get("fascicolo") or payload.get("fascicolo_id") or "").strip())
    if isinstance(contesto, tuple):
        return contesto
    dettaglio = get_prompt_library().get_prompt(prompt_id, contesto=contesto)
    documents = payload.get("documents") if isinstance(payload.get("documents"), list) else []
    skill, richiesta = prepara_esecuzione_prompt(
        dettaglio,
        nota=str(payload.get("nota") or payload.get("question") or ""),
        documents=documents,
        source_mode=str(payload.get("source_mode") or ""),
    )
    result = _workflow().run(richiesta, actor=_actor_label(), user_roles=_user_roles(), skill=skill)
    aggiornato = _runs_storage().update(
        result.run_id,
        {
            "prompt_id": prompt_id,
            "prompt_titolo": dettaglio.get("titolo", ""),
            "fascicolo_id": contesto.fascicolo_id if contesto else "",
        },
    )
    _audit_event(
        "legal_skills_prompt_eseguito", "prompt_library", prompt_id, f"Prompt eseguito con Lex (run {result.run_id})."
    )
    return jsonify({"ok": True, "result": aggiornato})


__all__ = ["api_v1_prompt_library"]
