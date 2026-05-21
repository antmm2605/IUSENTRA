"""API REST per Legal Document Understanding, OCR forense e indicizzazione Lex."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, g, jsonify, request

from legal_document_ingestion import LegalDocumentIngestionError
from web.services.feature_flags import feature_disabled_response, is_feature_enabled
from web.services.legal_document_ingestion_runtime import (
    build_legal_document_repository,
    build_legal_document_service,
    legal_document_actor,
    legal_document_tenant_id,
)
from web.services.security_redaction import redacted_json_response
from web.services.tenant_api_auth import api_key_valid_for_request


legal_documents_api = Blueprint("legal_documents_api", __name__, url_prefix="/api")


_PUBLIC_DOCUMENT_FIELDS = (
    "id",
    "tenant_id",
    "fascicolo_id",
    "parent_document_id",
    "root_document_id",
    "source_type",
    "source_message_id",
    "original_filename",
    "normalized_filename",
    "mime_type",
    "extension",
    "sha256",
    "file_size",
    "status",
    "security_status",
    "processing_status",
    "root_pec_id",
    "extraction_path_virtuale",
    "extraction_depth",
    "created_at",
    "updated_at",
    "created_by",
    "reviewed_by",
    "reviewed_at",
)

_PUBLIC_CLASSIFICATION_FIELDS = (
    "document_type",
    "legal_area",
    "macro_area",
    "rito",
    "fase",
    "procedimento",
    "portale_probabile",
    "confidence",
    "status",
)

_PUBLIC_VALIDATION_FIELDS = ("result", "status", "valid", "missing_critical_fields", "summary")
_PUBLIC_CASE_MATCH_FIELDS = ("matched_case_id", "confidence", "matched_signals", "conflicts", "status")
_PUBLIC_LEX_FIELDS = ("status", "job_id", "chunks", "warnings")


def _pick_public(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {field: row.get(field) for field in fields if field in row}


def _public_document(row: Any) -> dict[str, Any] | None:
    payload = _pick_public(row, _PUBLIC_DOCUMENT_FIELDS)
    return payload or None


def _public_blocked(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"status": "blocked", "reason": "Elemento bloccato."}
    return {
        "filename": row.get("filename") or row.get("name") or row.get("original_filename") or "",
        "extraction_path_virtuale": row.get("extraction_path_virtuale") or row.get("path") or "",
        "security_status": row.get("security_status") or "blocked",
        "reason": row.get("reason") or row.get("blocked_reason") or "Elemento bloccato.",
        "size": row.get("size") or row.get("file_size") or 0,
    }


def _public_processed(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    events = row.get("events") if isinstance(row.get("events"), list) else []
    entities = row.get("entities") if isinstance(row.get("entities"), list) else []
    return {
        "document": _public_document(row.get("document")),
        "classification": _pick_public(row.get("classification"), _PUBLIC_CLASSIFICATION_FIELDS),
        "validation": _pick_public(row.get("validation"), _PUBLIC_VALIDATION_FIELDS),
        "case_match": _pick_public(row.get("case_match"), _PUBLIC_CASE_MATCH_FIELDS),
        "lex": _pick_public(row.get("lex"), _PUBLIC_LEX_FIELDS),
        "events_count": len(events),
        "entities_count": len(entities),
    }


def _public_ingestion_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    children = [
        {
            "document": _public_document((item.get("document") if isinstance(item, dict) else None)),
            "metadata": _pick_public((item.get("metadata") if isinstance(item, dict) else {}), ("original_filename", "mime_type", "extension", "sha256", "size", "security_status", "processing_status", "extraction_path_virtuale", "extraction_depth")),
        }
        for item in list(result.get("children") or [])
        if isinstance(item, dict)
    ]
    return {
        "document": _public_document(result.get("document")),
        "children": children,
        "blocked": [_public_blocked(item) for item in list(result.get("blocked") or [])],
        "processed": [_public_processed(item) for item in list(result.get("processed") or [])],
    }


def _public_pec_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    return {
        "document": _public_document(result.get("document")),
        "attachments": [_public_ingestion_result(item) for item in list(result.get("attachments") or [])],
    }


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or api_key_valid_for_request():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "errore": "Autenticazione richiesta."}), 401

    return wrapper


def _feature_required(flag_key: str) -> bool:
    return is_feature_enabled(flag_key, current_app.config)


def _json_error(status: int = 400, *, not_found: bool = False, ingestion_error: bool = False):
    if status == 404 or not_found:
        message = "Documento non trovato."
        status = 404
    elif status == 403:
        message = "Dati dello studio non disponibili per questa richiesta."
    elif ingestion_error:
        message = "Documento non acquisito."
    else:
        message = "Operazione documentale non completata."
    return jsonify({"ok": False, "errore": message}), status


def _service():
    return build_legal_document_service()


def _repo():
    return build_legal_document_repository()


@legal_documents_api.get("/documents")
@_richiedi_auth
def documents_list():
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    tenant_id = legal_document_tenant_id()
    fascicolo_id = str(request.args.get("fascicolo_id") or "").strip()
    limit = int(request.args.get("limit") or 100)
    rows = _repo().list_documents(tenant_id, fascicolo_id=fascicolo_id, limit=limit)
    return jsonify({"ok": True, "data": rows, "count": len(rows)})


@legal_documents_api.post("/documents/upload")
@_richiedi_auth
def documents_upload():
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    service = _service()
    tenant_id = legal_document_tenant_id()
    actor = legal_document_actor()
    fascicolo_id = str(request.form.get("fascicolo_id") or request.args.get("fascicolo_id") or "").strip()
    uploaded = request.files.getlist("file") or request.files.getlist("files")
    if not uploaded and request.data:
        filename = str(request.headers.get("X-IUSENTRA-Filename") or request.args.get("filename") or "documento.bin")
        try:
            result = service.ingest_bytes(
                tenant_id=tenant_id,
                filename=filename,
                content=request.get_data(),
                source_type=str(request.args.get("source_type") or "upload manuale"),
                fascicolo_id=fascicolo_id,
                actor=actor,
            )
            return redacted_json_response({"ok": True, "data": [_public_ingestion_result(result)], "count": 1}, 201)
        except Exception as exc:
            return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))
    if not uploaded:
        return jsonify({"ok": False, "errore": "Selezionare almeno un file."}), 400
    results = []
    for item in uploaded:
        content = item.read()
        results.append(
            _public_ingestion_result(
                service.ingest_bytes(
                    tenant_id=tenant_id,
                    filename=item.filename or "documento.bin",
                    content=content,
                    source_type="upload manuale",
                    fascicolo_id=fascicolo_id,
                    actor=actor,
                )
            )
        )
    return redacted_json_response({"ok": True, "data": results, "count": len(results)}, 201)


@legal_documents_api.post("/pec/<pec_id>/process")
@_richiedi_auth
def pec_process_legal_documents(pec_id: str):
    if not _feature_required("legal_document_understanding") or not _feature_required("pec_zip_ocr"):
        return feature_disabled_response("pec_zip_ocr")
    try:
        from web.blueprints.pec_pipeline_api import _repo as pec_repo

        raw, _row = pec_repo().original_mime(pec_id)
        payload = request.get_json(silent=True) or {}
        result = _service().process_pec_message(
            tenant_id=legal_document_tenant_id(),
            pec_id=pec_id,
            raw_mime=raw,
            actor=legal_document_actor(),
            fascicolo_id=str(payload.get("fascicolo_id") or ""),
        )
        return redacted_json_response({"ok": True, "data": _public_pec_result(result)})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/ocr")
@_richiedi_auth
def document_ocr(document_id: str):
    if not _feature_required("ocr_forensic"):
        return feature_disabled_response("ocr_forensic")
    try:
        data = _service().run_ocr(legal_document_tenant_id(), document_id, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/classify")
@_richiedi_auth
def document_classify(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        data = _service().classify_document(legal_document_tenant_id(), document_id, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/validate")
@_richiedi_auth
def document_validate(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        data = _service().validate_document(legal_document_tenant_id(), document_id, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/match-case")
@_richiedi_auth
def document_match_case(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        data = _service().match_case(legal_document_tenant_id(), document_id, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/review")
@_richiedi_auth
def document_review(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    payload = request.get_json(silent=True) or {}
    try:
        data = _service().review_document(legal_document_tenant_id(), document_id, payload, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/events/approve")
@_richiedi_auth
def document_events_approve(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    payload = request.get_json(silent=True) or {}
    ids = payload.get("event_ids") or payload.get("ids") or []
    try:
        data = _repo().approve_events(legal_document_tenant_id(), document_id, ids, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/lex-index")
@_richiedi_auth
def document_lex_index(document_id: str):
    if not _feature_required("lex_validated_documents_only"):
        return feature_disabled_response("lex_validated_documents_only")
    try:
        data = _service().request_lex_index(legal_document_tenant_id(), document_id, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.get("/documents/<document_id>/evidence")
@_richiedi_auth
def document_evidence(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        return jsonify({"ok": True, "data": _repo().evidence_payload(legal_document_tenant_id(), document_id)})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.get("/documents/<document_id>/archive-tree")
@_richiedi_auth
def document_archive_tree(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        return jsonify({"ok": True, "data": _repo().archive_tree(legal_document_tenant_id(), document_id)})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.get("/documents/<document_id>/ocr-overlay")
@_richiedi_auth
def document_ocr_overlay(document_id: str):
    if not _feature_required("ocr_forensic"):
        return feature_disabled_response("ocr_forensic")
    try:
        return jsonify({"ok": True, "data": _repo().get_ocr_overlay(legal_document_tenant_id(), document_id)})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/proof-bundle")
@_richiedi_auth
def document_proof_bundle(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        data = _repo().create_proof_bundle(legal_document_tenant_id(), document_id, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data}), 201
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.get("/documents/<document_id>/proof-bundle/<bundle_id>")
@_richiedi_auth
def document_proof_bundle_download(document_id: str, bundle_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    repo = _repo()
    tenant_id = legal_document_tenant_id()
    try:
        with repo.connect() as conn:
            row = conn.execute(
                "SELECT * FROM proof_bundles WHERE tenant_id=? AND document_id=? AND id=?",
                (tenant_id, document_id, bundle_id),
            ).fetchone()
        if not row:
            raise KeyError("Proof bundle non trovato.")
        data = repo.read_file(str(row["stored_uri"]))
        response = Response(data, mimetype="application/zip")
        response.headers["Content-Disposition"] = f'attachment; filename="proof-bundle-{bundle_id}.zip"'
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))
