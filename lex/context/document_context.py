"""Contesto documentale di Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_fascicoli
from web.services.document_crypto import decrypt_doc
from web.services.signed_document_runtime import (
    build_document_signed_snapshot_from_bytes,
    build_document_version_candidates,
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _apply_limit(rows: list[Any], limit: int | None) -> list[Any]:
    if limit is None:
        return rows
    try:
        max_items = int(limit)
    except Exception:
        return rows
    if max_items <= 0:
        return rows
    return rows[:max_items]


def _truncate_text(value: Any, *, max_chars: int = 2400) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _document_ai_snapshot(fascicolo_id: str) -> dict[str, Any]:
    """Prepara l'indice Lex del fascicolo e restituisce testi indicizzati per documento.

    Il contesto Lex non deve limitarsi ai metadati del fascicolo: prima tenta
    l'indicizzazione Document AI di tutti i documenti leggibili, poi passa a Lex
    estratti e stato reale. Se manca il contesto Flask, resta un fallback
    conservativo per non rompere chiamate di test o job offline.
    """
    target_id = _clean_spaces(fascicolo_id)
    if not target_id:
        return {}
    try:
        from flask import has_request_context

        if not has_request_context():
            return {}
        from web.services.document_intelligence_runtime import (
            build_document_ai_service,
            build_lex_indexing_summary_payload,
            collect_document_ai_sources_for_fascicolo,
            document_ai_tenant_id,
            document_ai_user_context,
        )

        tenant_id = document_ai_tenant_id()
        user_context = document_ai_user_context()
        summary = build_lex_indexing_summary_payload(
            target_id,
            process=True,
            retry_errors=True,
            user_context=user_context,
        )
        service = build_document_ai_service()
        sources = collect_document_ai_sources_for_fascicolo(target_id, tenant_id=tenant_id)
        records = list(service.list_fascicolo_documents(tenant_id, target_id, user_context) or [])
    except Exception:
        return {}

    records_by_sha: dict[str, Any] = {}
    records_by_name: dict[str, Any] = {}
    for record in records:
        sha = str(getattr(record, "sha256", "") or "").strip()
        if sha:
            current = records_by_sha.get(sha)
            if current is None or _record_rank(record) > _record_rank(current):
                records_by_sha[sha] = record
        for name in (
            str(getattr(record, "original_filename", "") or "").strip().casefold(),
            str(getattr(record, "safe_filename", "") or "").strip().casefold(),
        ):
            if name:
                current = records_by_name.get(name)
                if current is None or _record_rank(record) > _record_rank(current):
                    records_by_name[name] = record

    source_by_document_id: dict[str, Any] = {}
    for source in sources:
        metadata = dict(getattr(source, "metadata", {}) or {})
        document_id = str(metadata.get("documento_id") or getattr(source, "source_id", "") or "").strip()
        if document_id:
            source_by_document_id[document_id] = source

    rows: dict[str, dict[str, Any]] = {}
    for document_id, source in source_by_document_id.items():
        record = None
        sha = str(getattr(source, "sha256", "") or "").strip()
        if sha:
            record = records_by_sha.get(sha)
        if record is None:
            for name in (
                str(getattr(source, "filename", "") or "").strip().casefold(),
                str(getattr(source, "safe_filename", "") or "").strip().casefold(),
            ):
                if name and name in records_by_name:
                    record = records_by_name[name]
                    break
        status = _status_for_record(record, source=source)
        text_payload: dict[str, Any] = {}
        if record is not None and status == "ready":
            try:
                extracted = service.get_fascicolo_document_text(tenant_id, target_id, record.id, user_context)
                text = str(getattr(extracted, "text", "") or "").strip()
                text_payload = {
                    "lex_read": bool(text),
                    "lex_text_excerpt": _truncate_text(text),
                    "lex_text_chars": len(text),
                    "lex_extraction_engine": str(getattr(extracted, "extraction_engine", "") or ""),
                    "lex_index_warnings": list(getattr(extracted, "warnings", []) or []),
                    "lex_version_id": str(getattr(extracted, "version_id", "") or ""),
                }
            except Exception as exc:
                status = "error"
                text_payload = {
                    "lex_read": False,
                    "lex_text_excerpt": "",
                    "lex_text_chars": 0,
                    "lex_extraction_engine": "",
                    "lex_index_warnings": [f"Lettura testo indicizzato non completata: {exc}"],
                    "lex_version_id": "",
                }
        rows[document_id] = {
            "lex_index_status": status,
            "lex_index_document_id": str(getattr(record, "id", "") or ""),
            "lex_index_summary": dict(summary or {}),
            **text_payload,
        }
    return rows


def _record_rank(record: Any) -> int:
    status = str(getattr(record, "status", "") or "").strip().lower()
    if status == "ready":
        return 4
    if status == "processing":
        return 3
    if status == "uploaded":
        return 2
    if status == "error":
        return 1
    return 0


def _status_for_record(record: Any, *, source: Any) -> str:
    if record is not None:
        status = str(getattr(record, "status", "") or "").strip().lower()
        return status or "not_indexed"
    if bool(getattr(source, "supported", True)):
        return "not_indexed"
    return "error"


def load_document_context(
    *,
    pratica_id: str = "",
    fascicolo_id: str = "",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    target_id = _clean_spaces(pratica_id) or _clean_spaces(fascicolo_id)
    if not target_id:
        return []
    gestore = get_fascicoli()
    fascicolo = gestore.get(target_id)
    if not fascicolo:
        return []
    lex_documents = _document_ai_snapshot(target_id)
    rows: list[dict[str, Any]] = []
    for doc in _apply_limit(list(fascicolo.documenti or []), limit):
        signed_snapshot = None
        document_name = str(getattr(doc, "nome", "") or "").strip().lower()
        if document_name.endswith((".p7m", ".pm7")):
            try:
                percorso = gestore.percorso_documento(target_id, doc.id)
                signed_snapshot = build_document_signed_snapshot_from_bytes(
                    source_name=doc.nome,
                    source_path=str(percorso),
                    data=decrypt_doc(percorso.read_bytes()),
                    version_candidates=build_document_version_candidates(
                        gestore,
                        doc,
                        decrypt_doc=decrypt_doc,
                    ),
                )
            except Exception:
                signed_snapshot = None
        lex_payload = dict(lex_documents.get(str(getattr(doc, "id", "") or "").strip()) or {})
        signed_payload_available = bool(((signed_snapshot or {}).get("signed_status") or {}).get("payload_available"))
        ai_readable = bool(lex_payload.get("lex_read")) or signed_payload_available or not document_name.endswith((".p7m", ".pm7"))
        rows.append(
            {
                "id": doc.id,
                "nome": doc.nome,
                "tipo": getattr(doc.tipo, "value", ""),
                "firmato": bool(getattr(doc, "firmato_digitalmente", False)),
                "data_documento": doc.data_documento,
                "data_caricamento": doc.data_caricamento,
                "note": doc.note,
                "id_deposito_pct": doc.id_deposito_pct,
                "signed_status": (signed_snapshot or {}).get("signed_status"),
                "signed_ui": (signed_snapshot or {}).get("ui_status"),
                "ai_readable": ai_readable,
                **lex_payload,
            }
        )
    return rows
