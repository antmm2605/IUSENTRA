"""API v1 UI per Documenti AI Fascicolo."""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request, session

from pct.document_intelligence import DocumentAIRecord, DocumentAIRepository, DocumentAIService
from pct.document_intelligence.security import (
    DocumentAIPermissionDenied,
    DocumentAINotFound,
    DocumentAIValidationError,
)
from web.helpers import get_fascicoli
from web.services.storage_runtime import get_request_studio_db, get_request_storage_runtime


api_v1_documenti_ai = Blueprint("api_v1_documenti_ai", __name__, url_prefix="/api/v1/ui")


def _api_key_valida() -> bool:
    api_key = str(current_app.config.get("API_KEY", "") or "")
    return bool(api_key and request.headers.get("X-API-Key") == api_key)


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return _errore("Autenticazione richiesta.", "permission_denied", 403)

    return wrapper


def _tenant_id() -> str:
    tenant = getattr(g, "tenant", None)
    slug = str(getattr(tenant, "slug", "") or "").strip()
    if slug:
        return slug
    user = g.get("utente_corrente")
    user_slug = str(getattr(user, "tenant_slug", "") or session.get("tenant_slug") or "").strip()
    if user_slug:
        return user_slug
    profile = get_request_storage_runtime(_fascicoli_db_path())
    return profile.tenant_slug or "single-studio"


def _fascicoli_db_path() -> str:
    return str(
        current_app.config.get("FASCICOLI_DB")
        or current_app.config.get("FASCICOLI_DB_PATH")
        or Path(current_app.instance_path) / "fascicoli" / "fascicoli.json"
    )


def build_document_ai_service() -> DocumentAIService:
    anchor = _fascicoli_db_path()
    structured_db = get_request_studio_db(anchor)
    repository = DocumentAIRepository.from_fascicoli_db(anchor, structured_db=structured_db)
    max_size = int(current_app.config.get("DOCUMENT_AI_MAX_UPLOAD_BYTES") or 25 * 1024 * 1024)
    return DocumentAIService(repository, get_fascicoli(), max_size_bytes=max_size)


def _user_context() -> dict[str, Any]:
    return {
        "user": g.get("utente_corrente"),
        "user_id": str(getattr(g.get("utente_corrente"), "id", "") or ""),
    }


def _errore(detail: str, code: str, status: int):
    return jsonify({"mock_fallback": False, "detail": detail, "code": code}), status


def _handle_error(exc: Exception):
    if isinstance(exc, DocumentAIValidationError):
        return _errore(str(exc) or "Richiesta non valida.", "validation_error", 400)
    if isinstance(exc, DocumentAIPermissionDenied):
        return _errore("Operazione non autorizzata", "permission_denied", 403)
    if isinstance(exc, DocumentAINotFound):
        return _errore("Documento o fascicolo non trovato", "not_found", 404)
    current_app.logger.exception("Errore Documenti AI Fascicolo")
    return _errore(
        "Errore interno durante l'elaborazione del documento",
        "document_ai_internal_error",
        500,
    )


def _serialize_document(document: DocumentAIRecord) -> dict[str, Any]:
    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "safe_filename": document.safe_filename,
        "file_type": document.file_type,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256,
        "status": document.status,
        "current_version_id": document.current_version_id,
        "page_count": document.page_count,
        "created_by": document.created_by,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _serialize_version(version: Any) -> dict[str, Any]:
    return {
        "id": version.id,
        "version_number": version.version_number,
        "source": version.source,
        "sha256": version.sha256,
        "created_at": version.created_at,
    }


def _capabilities() -> dict[str, bool]:
    return {
        "upload": True,
        "read": True,
        "search": True,
        "lex_tools": True,
        "generate_docx": False,
        "propose_edits": False,
        "compare": False,
    }


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/documenti-ai")
@_richiedi_auth
def lista_documenti_ai(fascicolo_id: str):
    try:
        service = build_document_ai_service()
        documents = service.list_fascicolo_documents(_tenant_id(), fascicolo_id, _user_context())
        return jsonify(
            {
                "mock_fallback": False,
                "fascicolo_id": fascicolo_id,
                "documents": [_serialize_document(document) for document in documents],
                "capabilities": _capabilities(),
            }
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/documenti-ai/upload")
@_richiedi_auth
def upload_documento_ai(fascicolo_id: str):
    try:
        uploaded = request.files.get("file")
        if uploaded is None:
            raise DocumentAIValidationError("File mancante.")
        service = build_document_ai_service()
        upload_outcome = service.upload_document_for_fascicolo(_tenant_id(), fascicolo_id, uploaded, _user_context())
        document = upload_outcome.document
        upload_result = service.last_upload_result or {}
        version = upload_result.get("version") or upload_outcome.version
        extraction = upload_result.get("extraction") or {}
        return (
            jsonify(
                {
                    "mock_fallback": False,
                    "document": _serialize_document(document),
                    "version": _serialize_version(version) if version else None,
                    "extraction": {
                        "status": extraction.get("status") or ("completed" if document.status == "ready" else "failed"),
                        "engine": extraction.get("engine") or "",
                        "page_count": extraction.get("page_count"),
                        "warnings": extraction.get("warnings") or [],
                    },
                }
            ),
            201,
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>")
@_richiedi_auth
def dettaglio_documento_ai(fascicolo_id: str, documento_id: str):
    try:
        service = build_document_ai_service()
        document, versions, audit_summary = service.get_fascicolo_document_detail(
            _tenant_id(),
            fascicolo_id,
            documento_id,
            _user_context(),
        )
        return jsonify(
            {
                "mock_fallback": False,
                "document": _serialize_document(document),
                "versions": [_serialize_version(version) for version in versions],
                "audit_summary": audit_summary,
            }
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>/testo")
@_richiedi_auth
def testo_documento_ai(fascicolo_id: str, documento_id: str):
    try:
        service = build_document_ai_service()
        text = service.get_fascicolo_document_text(_tenant_id(), fascicolo_id, documento_id, _user_context())
        return jsonify(
            {
                "mock_fallback": False,
                "document_id": text.document_id,
                "version_id": text.version_id,
                "status": "ready",
                "extraction_engine": text.extraction_engine,
                "page_count": len(text.pages) if text.pages else None,
                "text": text.text,
                "pages": [page.to_dict() for page in text.pages],
                "warnings": list(text.warnings),
            }
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>/cerca")
@_richiedi_auth
def cerca_documento_ai(fascicolo_id: str, documento_id: str):
    try:
        payload = request.get_json(silent=True) or {}
        query = str(payload.get("query") or "").strip()
        if not query:
            raise DocumentAIValidationError("Query di ricerca mancante.")
        max_results = int(payload.get("max_results") or 20)
        service = build_document_ai_service()
        results = service.search_fascicolo_document(
            _tenant_id(),
            fascicolo_id,
            documento_id,
            query,
            _user_context(),
            max_results=max_results,
        )
        return jsonify(
            {
                "mock_fallback": False,
                "document_id": documento_id,
                "query": query,
                "results": [
                    {
                        "page_number": result.page_number,
                        "snippet": result.snippet,
                        "start_offset": result.start_offset,
                        "end_offset": result.end_offset,
                    }
                    for result in results
                ],
            }
        )
    except Exception as exc:
        return _handle_error(exc)
