"""API v1 UI per generazione atti con Lex nell'editor."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request

from pct.editor_ai import AttoAIDraftRequest
from pct.editor_ai.editor_renderer import create_editor_document, legal_markdown_to_editor_html
from pct.editor_ai.validators import (
    EditorAINotFound,
    EditorAIPermissionDenied,
    EditorAIValidationError,
    assert_user_can_write,
    clean_text,
)
from lex.formatting.legal_draft_layout import normalize_legal_draft_layout
from web.helpers import get_fascicoli
from web.services.editor_ai_runtime import (
    build_editor_ai_service,
    editor_ai_tenant_id,
    editor_ai_user_context,
)
from web.services.tenant_api_auth import api_key_valid_for_request


api_v1_editor_ai = Blueprint("api_v1_editor_ai", __name__, url_prefix="/api/v1/ui")


def _api_key_valida() -> bool:
    return api_key_valid_for_request()


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
        return jsonify({"detail": "Atto o fascicolo non trovato", "code": "not_found", "mock_fallback": False}), 404
    if isinstance(exc, EditorAIValidationError):
        return jsonify({"detail": "Richiesta non valida", "code": "validation_error", "mock_fallback": False}), 400
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


def _draft_import_title(payload: dict[str, Any], normalized_answer: str) -> str:
    title = clean_text(payload.get("title") or payload.get("titolo"))
    if title:
        return title[:120]
    for raw_line in normalized_answer.splitlines():
        line = clean_text(raw_line.replace("**", "").replace("#", "").strip("- "))
        if line and line != "---":
            return line[:120]
    return "Bozza Lex"


def _audit_chat_draft_import(fascicolo_id: str, document_id: str) -> None:
    try:
        core_runtime = current_app.extensions.get("core_runtime", {}) or {}
        audit = core_runtime.get("audit")
        if callable(audit):
            audit(
                "editor_ai.importa_bozza_chat",
                "fascicolo",
                fascicolo_id,
                dettagli=f"documento_editor={document_id}",
            )
    except Exception:
        current_app.logger.debug("Audit import bozza Lex non registrato.", exc_info=True)


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


@api_v1_editor_ai.post("/fascicoli/<fascicolo_id>/editor-ai/importa-bozza")
@_richiedi_auth
def editor_ai_importa_bozza_chat(fascicolo_id: str):
    try:
        user_context = editor_ai_user_context()
        assert_user_can_write(user_context)
        payload = _body()
        answer = str(payload.get("answer") or payload.get("content") or payload.get("testo") or "").strip()
        if not answer:
            raise EditorAIValidationError("Bozza non disponibile per l'apertura nell'editor.")
        if len(answer) > 250_000:
            raise EditorAIValidationError("La bozza è troppo lunga per l'apertura diretta nell'editor.")

        normalized_answer = normalize_legal_draft_layout(answer)
        html_content = legal_markdown_to_editor_html(normalized_answer)
        title = _draft_import_title(payload, normalized_answer)
        try:
            from web.services.document_crypto import encrypt_doc
        except Exception:
            encrypt_doc = None
        created = create_editor_document(
            fascicoli_repository=get_fascicoli(),
            fascicolo_id=fascicolo_id,
            title=title,
            html_content=html_content,
            created_by=clean_text(user_context.get("user_id")) or "sistema",
            encrypt=encrypt_doc,
        )
        _audit_chat_draft_import(fascicolo_id, str(created.get("document_id") or ""))
        return jsonify(
            {
                "mock_fallback": False,
                "message": "Bozza aperta nell'editor professionale.",
                "document_id": created["document_id"],
                "filename": created["filename"],
                "open_url": created["open_url"],
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
