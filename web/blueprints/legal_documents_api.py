"""API REST per Legal Document Understanding, OCR forense e indicizzazione Lex."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, g, jsonify, request

from legal_document_ingestion import LegalDocumentIngestionError
from web.services.feature_flags import feature_disabled_response, is_feature_enabled
from web.services.legal_document_ingestion_runtime import (
    build_legal_ocr_store,
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


def _public_file(row: Any) -> dict[str, Any]:
    return _pick_public(
        row,
        (
            "id",
            "tenant_id",
            "document_id",
            "original_filename",
            "normalized_filename",
            "mime_type",
            "extension",
            "size",
            "sha256",
            "parent_document_id",
            "root_pec_id",
            "extraction_path_virtuale",
            "extraction_depth",
            "security_status",
            "processing_status",
            "created_at",
        ),
    )


def _public_hash_chain(row: Any) -> dict[str, Any]:
    return _pick_public(row, ("resource_type", "resource_id", "prev_hash", "current_hash", "payload_sha256", "created_at"))


def _public_audit(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {
        "occurred_at": row.get("occurred_at"),
        "actor": row.get("actor"),
        "action": row.get("action"),
        "resource_type": row.get("resource_type"),
        "resource_id": row.get("resource_id"),
        "payload": _public_audit_payload(row.get("payload") or {}),
        "prev_hash": row.get("prev_hash"),
        "entry_hash": row.get("entry_hash"),
    }


def _public_audit_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            str(key): _public_audit_payload(value)
            for key, value in payload.items()
            if str(key) not in {"stored_uri", "storage_path", "filesystem_path", "file_path", "absolute_path", "root_path"}
        }
    if isinstance(payload, list):
        return [_public_audit_payload(item) for item in payload]
    return payload


def _public_evidence_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        "document": _public_document(payload.get("document")),
        "files": [_public_file(item) for item in list(payload.get("files") or []) if isinstance(item, dict)],
        "classification": _pick_public(payload.get("classification"), _PUBLIC_CLASSIFICATION_FIELDS),
        "entities": payload.get("entities") if isinstance(payload.get("entities"), list) else [],
        "validation": _pick_public(payload.get("validation"), _PUBLIC_VALIDATION_FIELDS),
        "case_match": _pick_public(payload.get("case_match"), _PUBLIC_CASE_MATCH_FIELDS),
        "events": payload.get("events") if isinstance(payload.get("events"), list) else [],
        "lex_index": _pick_public(payload.get("lex_index"), _PUBLIC_LEX_FIELDS),
        "audit": [_public_audit(item) for item in list(payload.get("audit") or []) if isinstance(item, dict)],
        "hash_chain": [_public_hash_chain(item) for item in list(payload.get("hash_chain") or []) if isinstance(item, dict)],
    }


def _public_archive_tree(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        "link": _pick_public(
            payload.get("link"),
            (
                "id",
                "tenant_id",
                "parent_document_id",
                "child_document_id",
                "root_document_id",
                "root_pec_id",
                "extraction_path_virtuale",
                "extraction_depth",
                "security_status",
                "created_at",
            ),
        ),
        "document": _public_document(payload.get("document")),
        "children": [_public_archive_tree(item) for item in list(payload.get("children") or []) if isinstance(item, dict)],
    }


def _public_proof_bundle(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    manifest_value = payload.get("manifest")
    manifest: dict[str, Any] = manifest_value if isinstance(manifest_value, dict) else {}
    return {
        "id": payload.get("id"),
        "sha256": payload.get("sha256"),
        "manifest": {
            "created_at": manifest.get("created_at"),
            "bundle_id": manifest.get("bundle_id"),
            "tenant_id": manifest.get("tenant_id"),
            "document_id": manifest.get("document_id"),
            "chain_of_custody": manifest.get("chain_of_custody") or {},
            "files": manifest.get("files") or [],
        },
    }


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
    events_value = row.get("events")
    entities_value = row.get("entities")
    events: list[Any] = events_value if isinstance(events_value, list) else []
    entities: list[Any] = entities_value if isinstance(entities_value, list) else []
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


def _processed_document_ids(result: Any) -> list[str]:
    ids: list[str] = []
    if not isinstance(result, dict):
        return ids
    document = result.get("document")
    if isinstance(document, dict) and document.get("id"):
        ids.append(str(document["id"]))
    for key in ("children", "processed", "attachments"):
        for item in list(result.get(key) or []):
            ids.extend(_processed_document_ids(item))
    return list(dict.fromkeys(ids))


def _public_ocr_review(evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        return {}
    low_tokens = [
        {
            "token": token.get("token"),
            "confidence": token.get("confidence"),
            "bbox": token.get("bbox"),
            "page": token.get("page"),
            "line_id": token.get("line_id"),
        }
        for token in list(evidence.get("token_index") or [])
        if float(token.get("confidence") or 0.0) < 0.75
    ][:500]
    mandatory = list((evidence.get("regex_summary") or {}).get("mandatory_fields") or [])
    return {
        "run_id": evidence.get("run_id"),
        "document_id": evidence.get("document_id"),
        "metrics": evidence.get("metrics") or {},
        "qc": evidence.get("qc") or {},
        "engine_version": evidence.get("engine_version") or {},
        "mandatory_fields": mandatory,
        "low_tokens": low_tokens,
        "suggested_fixes": evidence.get("hil_suggestions") or evidence.get("suggested_hil_fixes") or [],
        "correction_history": evidence.get("correction_history_effective") or evidence.get("correction_history") or [],
        "lex_export": {
            "confidence_policy": (evidence.get("lex_export") or {}).get("confidence_policy"),
            "fragile_count": (evidence.get("lex_export") or {}).get("fragile_count"),
        },
    }


def _emit_ocr_notifications(document_ids: list[str]) -> int:
    clean_ids = [item for item in dict.fromkeys(document_ids) if item]
    if not clean_ids:
        return 0
    try:
        pending: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        store = build_legal_ocr_store(legal_document_tenant_id())
        for document_id in clean_ids:
            evidence = store.find_latest_for_document(document_id)
            if not evidence:
                continue
            proposals = list(evidence.get("notification_proposals") or [])
            mandatory = list((evidence.get("regex_summary") or {}).get("mandatory_fields") or [])
            failed = [field for field in mandatory if str(field.get("status") or "") == "fail"]
            if not proposals and ((evidence.get("qc") or {}).get("hil_required") or failed):
                proposals = [
                    {
                        "id": "ocr-review",
                        "title": "Documento da verificare",
                        "body": "La lettura OCR richiede revisione prima dell'uso sul fascicolo.",
                        "priority": "high",
                        "href": f"/documenti?documento={document_id}",
                    }
                ]
            for proposal in proposals:
                pending.append((document_id, evidence, proposal))
        if not pending:
            return 0
        from web.services.notifications_runtime import build_notification_service, current_tenant_id, current_user_id

        service = build_notification_service()
        tenant_id = current_tenant_id()
        user_id = current_user_id() or legal_document_actor()
        if not user_id:
            return 0
        emitted = 0
        for document_id, evidence, proposal in pending:
            run_id = str(evidence.get("run_id") or "")
            service.create_notification(
                tenant_id=tenant_id,
                user_id=user_id,
                type="ocr_documento",
                priority=str(proposal.get("priority") or "high"),
                title=str(proposal.get("title") or "Documento letto con OCR"),
                body=str(proposal.get("body") or "È stata rilevata un'attività nel documento."),
                href=str(proposal.get("href") or f"/documenti?documento={document_id}"),
                source_type="legal_ocr",
                source_id=run_id or document_id,
                dedupe_key=f"legal-ocr:{run_id or document_id}:{proposal.get('id') or proposal.get('kind') or 'review'}",
                payload_json={"document_id": document_id, "run_id": run_id, "fascicolo_id": evidence.get("fascicolo_id"), "proposal": proposal},
            )
            emitted += 1
        return emitted
    except Exception:
        current_app.logger.exception("Notifica OCR legal-grade non completata.")
        return 0


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
    return jsonify({"ok": True, "data": [_public_document(row) for row in rows], "count": len(rows)})


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
            _emit_ocr_notifications(_processed_document_ids(result))
            return redacted_json_response({"ok": True, "data": [_public_ingestion_result(result)], "count": 1}, 201)
        except Exception as exc:
            return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))
    if not uploaded:
        return jsonify({"ok": False, "errore": "Selezionare almeno un file."}), 400
    results = []
    for item in uploaded:
        content = item.read()
        raw_result = service.ingest_bytes(
            tenant_id=tenant_id,
            filename=item.filename or "documento.bin",
            content=content,
            source_type="upload manuale",
            fascicolo_id=fascicolo_id,
            actor=actor,
        )
        _emit_ocr_notifications(_processed_document_ids(raw_result))
        results.append(_public_ingestion_result(raw_result))
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
        _emit_ocr_notifications(_processed_document_ids(result))
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
        _emit_ocr_notifications([document_id])
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


@legal_documents_api.post("/documents/fascicoli/<fascicolo_id>/lex-index")
@_richiedi_auth
def fascicolo_lex_index(fascicolo_id: str):
    if not _feature_required("lex_validated_documents_only"):
        return feature_disabled_response("lex_validated_documents_only")
    try:
        data = _service().request_fascicolo_lex_index(legal_document_tenant_id(), fascicolo_id, actor=legal_document_actor())
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.get("/documents/<document_id>/ocr-legal-review")
@_richiedi_auth
def document_ocr_legal_review(document_id: str):
    if not _feature_required("ocr_forensic"):
        return feature_disabled_response("ocr_forensic")
    try:
        evidence = build_legal_ocr_store(legal_document_tenant_id()).find_latest_for_document(document_id)
        if not evidence:
            return jsonify({"ok": True, "data": {}})
        return jsonify({"ok": True, "data": _public_ocr_review(evidence)})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.post("/documents/<document_id>/ocr-legal-review/apply")
@_richiedi_auth
def document_ocr_legal_review_apply(document_id: str):
    if not _feature_required("ocr_forensic"):
        return feature_disabled_response("ocr_forensic")
    payload = request.get_json(silent=True) or {}
    try:
        store = build_legal_ocr_store(legal_document_tenant_id())
        evidence = store.find_latest_for_document(document_id)
        if not evidence:
            raise KeyError("Evidenza OCR non trovata.")
        fix_value = payload.get("fix") if isinstance(payload, dict) else {}
        fix: dict[str, Any] = fix_value if isinstance(fix_value, dict) else (payload if isinstance(payload, dict) else {})
        correction = {
            "user": legal_document_actor(),
            "from": str(fix.get("from") or ""),
            "to": str(fix.get("to") or ""),
            "reason": str(fix.get("reason") or "Correzione confermata in revisione OCR."),
            "rule_id": str(fix.get("rule_id") or "hil.manual"),
            "document_id": document_id,
        }
        applied = store.append_hil_correction(str(payload.get("run_id") or evidence.get("run_id") or ""), correction)
        refreshed = store.load_evidence_with_corrections(str(evidence.get("run_id") or "")) or evidence
        return jsonify({"ok": True, "data": {"applied": applied, "review": _public_ocr_review(refreshed)}})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.get("/documents/<document_id>/evidence")
@_richiedi_auth
def document_evidence(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        return jsonify({"ok": True, "data": _public_evidence_payload(_repo().evidence_payload(legal_document_tenant_id(), document_id))})
    except Exception as exc:
        return _json_error(not_found=isinstance(exc, KeyError), ingestion_error=isinstance(exc, LegalDocumentIngestionError))


@legal_documents_api.get("/documents/<document_id>/archive-tree")
@_richiedi_auth
def document_archive_tree(document_id: str):
    if not _feature_required("legal_document_understanding"):
        return feature_disabled_response("legal_document_understanding")
    try:
        return jsonify({"ok": True, "data": _public_archive_tree(_repo().archive_tree(legal_document_tenant_id(), document_id))})
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
        return jsonify({"ok": True, "data": _public_proof_bundle(data)}), 201
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
