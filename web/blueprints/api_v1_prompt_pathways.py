"""API JSON governate per i percorsi guidati LegalSkills Italia.

Espone il catalogo dei percorsi per procedimento (passi, termini,
riferimenti) e l'avanzamento per fascicolo. Stesse guardie della libreria
prompt: autenticazione, feature flag, permessi e blocco dei parametri
riservati; l'avanzamento è tenant-aware.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from lex.legal_skills.exceptions import LegalSkillsError
from lex.legal_skills.prompt_library import (
    PathwayProgressStore,
    Percorso,
    get_pathway_catalog,
    get_prompt_library,
)
from web.blueprints.api_v1_legal_skills import (
    _actor_label,
    _api_key_valida,
    _audit_event,
    _has_permission,
    _json_payload,
    _require_auth,
    _require_feature,
    _require_permission,
)
from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from web.services.prompt_library_fascicolo_bridge import costruisci_contesto_fascicolo
from web.services.prompt_pathway_templates import templates_per_refs
from web.services.tenant_paths import tenant_data_path

api_v1_prompt_pathways = Blueprint(
    "api_v1_prompt_pathways", __name__, url_prefix="/api/v1/legal-skills/prompt-library/percorsi"
)


@api_v1_prompt_pathways.errorhandler(LegalSkillsError)
def _pathway_error(error: LegalSkillsError):
    _audit_event("legal_skills_error", "prompt_pathways", getattr(error, "code", ""), str(error))
    return jsonify({"ok": False, "code": error.code, "message": str(error)}), int(error.status_code)


@api_v1_prompt_pathways.before_request
def _backend_security_guard():
    if not (g.get("utente_corrente") or _api_key_valida()):
        return None
    violations = backend_control_violations_for_request(request)
    if not violations:
        return None
    keys = ",".join(sorted({violation.key for violation in violations}))
    _audit_event(
        "policy_denied.backend_security", "prompt_pathways", request.path, f"Parametri riservati bloccati: {keys}."
    )
    return backend_security_error_response(violations)


def _progress_store() -> PathwayProgressStore:
    path = tenant_data_path(
        "LEGAL_SKILLS_PATHWAYS_DB",
        "./data/intelligence/legal_skills/pathway_progress.json",
        require_tenant=True,
    )
    return PathwayProgressStore(path)


def _verifica_fascicolo(fascicolo_id: str):
    """Contesto fascicolo verificato o risposta d'errore (tupla Flask)."""
    if not _has_permission("fascicoli.leggi"):
        _audit_event("policy_denied.legal_skills", "permission", "fascicoli.leggi", "Avanzamento percorso negato.")
        return jsonify({"ok": False, "code": "permission_denied", "message": "Permesso fascicoli mancante."}), 403
    contesto = costruisci_contesto_fascicolo(fascicolo_id)
    if contesto is None:
        return jsonify({"ok": False, "code": "fascicolo_not_found", "message": "Fascicolo non trovato."}), 404
    return contesto


def _titoli_prompt(percorso: Percorso) -> dict[str, dict[str, str]]:
    library = get_prompt_library()
    titoli: dict[str, dict[str, str]] = {}
    for entry in library.search():
        titoli[entry["prompt_id"]] = {"titolo": entry["titolo"], "forma_label": entry["forma_label"]}
    return {passo.prompt_ref: titoli.get(passo.prompt_ref, {}) for passo in percorso.passi}


def _dettaglio_percorso(percorso: Percorso, fascicolo_id: str) -> dict[str, object]:
    passi_stato = _progress_store().stato(percorso.percorso_id, fascicolo_id) if fascicolo_id else {}
    titoli = _titoli_prompt(percorso)
    passi_payload = []
    prossimo_passo = ""
    for passo in percorso.passi:
        completato = passo.passo_id in passi_stato
        if not completato and not prossimo_passo:
            prossimo_passo = passo.passo_id
        dati = passo.to_public_dict()
        dati["prompt_titolo"] = titoli.get(passo.prompt_ref, {}).get("titolo", "")
        dati["prompt_forma"] = titoli.get(passo.prompt_ref, {}).get("forma_label", "")
        dati["templates"] = templates_per_refs(passo.template_refs)
        dati["completato"] = completato
        dati["completato_il"] = str((passi_stato.get(passo.passo_id) or {}).get("completato_il", ""))
        passi_payload.append(dati)
    payload = percorso.to_public_dict()
    payload["passi"] = passi_payload
    payload["fascicolo_id"] = fascicolo_id
    payload["prossimo_passo"] = prossimo_passo if fascicolo_id else ""
    return payload


@api_v1_prompt_pathways.get("")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def list_percorsi():
    percorsi = [percorso.to_public_dict() for percorso in get_pathway_catalog().percorsi()]
    return jsonify({"ok": True, "percorsi": percorsi, "totale": len(percorsi)})


@api_v1_prompt_pathways.get("/<percorso_id>")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.leggi")
def get_percorso(percorso_id: str):
    percorso = get_pathway_catalog().get(percorso_id)
    fascicolo_id = str(request.args.get("fascicolo", "") or "").strip()
    if fascicolo_id:
        esito = _verifica_fascicolo(fascicolo_id)
        if isinstance(esito, tuple):
            return esito
    return jsonify({"ok": True, "percorso": _dettaglio_percorso(percorso, fascicolo_id)})


@api_v1_prompt_pathways.post("/<percorso_id>/passi/<passo_id>/stato")
@_require_auth
@_require_feature("lex.legalSkills.enabled")
@_require_permission("legal_skills.esegui")
def segna_passo(percorso_id: str, passo_id: str):
    percorso = get_pathway_catalog().get(percorso_id)
    if passo_id not in {passo.passo_id for passo in percorso.passi}:
        return jsonify({"ok": False, "code": "passo_not_found", "message": "Passo del percorso non trovato."}), 404
    payload = _json_payload()
    fascicolo_id = str(payload.get("fascicolo") or payload.get("fascicolo_id") or "").strip()
    if not fascicolo_id:
        return jsonify(
            {"ok": False, "code": "fascicolo_required", "message": "Indica il fascicolo per tracciare il percorso."}
        ), 400
    esito = _verifica_fascicolo(fascicolo_id)
    if isinstance(esito, tuple):
        return esito
    completato = bool(payload.get("completato", True))
    _progress_store().segna(percorso_id, fascicolo_id, passo_id, completato=completato, actor=_actor_label())
    _audit_event(
        "legal_skills_percorso_passo",
        "prompt_pathways",
        f"{percorso_id}/{passo_id}",
        f"Passo {'completato' if completato else 'riaperto'} per fascicolo {fascicolo_id}.",
    )
    return jsonify({"ok": True, "percorso": _dettaglio_percorso(percorso, fascicolo_id)})


__all__ = ["api_v1_prompt_pathways"]
