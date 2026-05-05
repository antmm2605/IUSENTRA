"""API v1 UI per generazione atti con Lex nell'editor."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request

from pct.editor_ai import AttoAIDraftRequest
from pct.editor_ai.validators import (
    EditorAINotFound,
    EditorAIPermissionDenied,
    EditorAIValidationError,
    clean_text,
)
from web.services.editor_ai_runtime import (
    build_editor_ai_service,
    editor_ai_tenant_id,
    editor_ai_user_context,
)


api_v1_editor_ai = Blueprint("api_v1_editor_ai", __name__, url_prefix="/api/v1/ui")


def _api_key_valida() -> bool:
    api_key = str(current_app.config.get("API_KEY", "") or "")
    return bool(api_key and request.headers.get("X-API-Key") == api_key)


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return jsonify({"detail": "Autenticazione richiesta.", "code": "unauthorized", "mock_fallback": False}), 401

    return wrapper


def _body() -> dict[str, Any]:
    return dict(request.get_json(silent=True) or {})


def _error_response(exc: Exception):
    if isinstance(exc, EditorAIPermissionDenied):
        return jsonify({"detail": "Operazione non autorizzata", "code": "permission_denied", "mock_fallback": False}), 403
    if isinstance(exc, EditorAINotFound):
        return jsonify({"detail": str(exc) or "Atto o fascicolo non trovato", "code": "not_found", "mock_fallback": False}), 404
    if isinstance(exc, EditorAIValidationError):
        return jsonify({"detail": str(exc) or "Richiesta non valida", "code": "validation_error", "mock_fallback": False}), 400
    current_app.logger.exception("Errore Editor AI: %s", exc)
    return jsonify(
        {
            "detail": "Errore interno durante la generazione dell'atto",
            "code": "editor_ai_internal_error",
            "mock_fallback": False,
        }
    ), 500


def _version_payload(version) -> dict[str, Any]:
    return {
        "id": version.id,
        "version_number": version.version_number,
        "source": version.source,
        "created_at": version.created_at,
    }


def _source_payload(source) -> dict[str, Any]:
    return {
        "id": source.id,
        "source_type": source.source_type,
        "source_id": source.source_id,
        "document_id": source.document_id,
        "page_number": source.page_number,
        "quote": source.quote,
        "sha256": source.sha256,
        "reason": source.reason,
    }


def _proposal_payload(proposal) -> dict[str, Any]:
    return proposal.to_dict()


@api_v1_editor_ai.get("/fascicoli/<fascicolo_id>/editor-ai/bootstrap")
@_richiedi_auth
def editor_ai_bootstrap(fascicolo_id: str):
    try:
        payload = build_editor_ai_service().bootstrap(
            tenant_id=editor_ai_tenant_id(),
            fascicolo_id=fascicolo_id,
            user_context=editor_ai_user_context(),
        )
        return jsonify(payload)
    except Exception as exc:
        return _error_response(exc)


@api_v1_editor_ai.post("/fascicoli/<fascicolo_id>/editor-ai/genera")
@_richiedi_auth
def editor_ai_genera(fascicolo_id: str):
    try:
        payload = _body()
        tenant_id = editor_ai_tenant_id()
        request_model = AttoAIDraftRequest(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            tipo_atto=clean_text(payload.get("tipo_atto") or payload.get("tipoAtto")),
            template_id=clean_text(payload.get("template_id") or payload.get("templateId")),
            istruzioni_utente=clean_text(payload.get("istruzioni_utente") or payload.get("istruzioniUtente")),
            document_ids=[
                clean_text(item)
                for item in list(payload.get("document_ids") or payload.get("documentIds") or [])
                if clean_text(item)
            ],
            use_fascicolo_context=payload.get("use_fascicolo_context", payload.get("useFascicoloContext", True)) is not False,
            language=clean_text(payload.get("language") or "it"),
        )
        result = build_editor_ai_service().generate_editor_draft(request_model, editor_ai_user_context())
        return jsonify(
            {
                "mock_fallback": False,
                "atto_ai": result.record.to_dict(),
                "version": _version_payload(result.version),
                "open_url": result.open_url,
                "plan": result.plan.to_dict(),
                "sources": [_source_payload(source) for source in result.sources],
                "missing_fields": result.missing_fields,
                "warnings": result.warnings,
                "readback": {
                    "editor_document_id": result.readback.get("editor_document_id"),
                    "filename": result.readback.get("filename"),
                    "sections": [section.heading for section in result.plan.sections],
                },
            }
        ), 201
    except Exception as exc:
        return _error_response(exc)


@api_v1_editor_ai.get("/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>")
@_richiedi_auth
def editor_ai_dettaglio(fascicolo_id: str, atto_ai_id: str):
    try:
        result = build_editor_ai_service().get_atto_ai(
            tenant_id=editor_ai_tenant_id(),
            fascicolo_id=fascicolo_id,
            atto_ai_id=atto_ai_id,
            user_context=editor_ai_user_context(),
        )
        record = result["record"]
        return jsonify(
            {
                "mock_fallback": False,
                "atto_ai": record.to_dict(),
                "open_url": f"/fascicoli/{fascicolo_id}/documenti/{record.editor_document_id}/editor",
                "versions": [_version_payload(version) for version in result["versions"]],
                "sources": [_source_payload(source) for source in result["sources"]],
                "edit_proposals": [_proposal_payload(proposal) for proposal in result["edit_proposals"]],
            }
        )
    except Exception as exc:
        return _error_response(exc)


@api_v1_editor_ai.post("/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/modifiche/proponi")
@_richiedi_auth
def editor_ai_proponi_modifiche(fascicolo_id: str, atto_ai_id: str):
    try:
        payload = _body()
        proposals = build_editor_ai_service().propose_editor_edits(
            tenant_id=editor_ai_tenant_id(),
            fascicolo_id=fascicolo_id,
            atto_ai_id=atto_ai_id,
            instructions=clean_text(payload.get("istruzioni") or payload.get("instructions")),
            user_context=editor_ai_user_context(),
        )
        return jsonify(
            {
                "mock_fallback": False,
                "atto_ai_id": atto_ai_id,
                "proposals": [_proposal_payload(proposal) for proposal in proposals],
            }
        )
    except Exception as exc:
        return _error_response(exc)


@api_v1_editor_ai.post("/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/modifiche/<edit_id>/accetta")
@_richiedi_auth
def editor_ai_accetta_modifica(fascicolo_id: str, atto_ai_id: str, edit_id: str):
    try:
        result = build_editor_ai_service().accept_edit(
            tenant_id=editor_ai_tenant_id(),
            fascicolo_id=fascicolo_id,
            atto_ai_id=atto_ai_id,
            edit_id=edit_id,
            user_context=editor_ai_user_context(),
        )
        return jsonify(
            {
                "mock_fallback": False,
                "atto_ai": result["record"].to_dict(),
                "version": _version_payload(result["version"]),
                "proposal": _proposal_payload(result["proposal"]),
                "warnings": result["warnings"],
            }
        )
    except Exception as exc:
        return _error_response(exc)


@api_v1_editor_ai.post("/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/modifiche/<edit_id>/rifiuta")
@_richiedi_auth
def editor_ai_rifiuta_modifica(fascicolo_id: str, atto_ai_id: str, edit_id: str):
    try:
        proposal = build_editor_ai_service().reject_edit(
            tenant_id=editor_ai_tenant_id(),
            fascicolo_id=fascicolo_id,
            atto_ai_id=atto_ai_id,
            edit_id=edit_id,
            user_context=editor_ai_user_context(),
        )
        return jsonify({"mock_fallback": False, "proposal": _proposal_payload(proposal)})
    except Exception as exc:
        return _error_response(exc)


@api_v1_editor_ai.post("/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/export")
@_richiedi_auth
def editor_ai_export(fascicolo_id: str, atto_ai_id: str):
    try:
        payload = _body()
        result = build_editor_ai_service().export_editor_document(
            tenant_id=editor_ai_tenant_id(),
            fascicolo_id=fascicolo_id,
            atto_ai_id=atto_ai_id,
            export_format=clean_text(payload.get("format") or payload.get("formato") or "docx"),
            user_context=editor_ai_user_context(),
        )
        return jsonify({"mock_fallback": False, "export": result.to_dict()})
    except Exception as exc:
        return _error_response(exc)
