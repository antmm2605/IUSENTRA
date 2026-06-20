"""Runtime Flask per l'indicizzazione Lex dei documenti fascicolo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context, session

from pct.document_intelligence import DocumentAIRepository, DocumentAIService, LexIndexingSummary
from pct.document_intelligence.security import DocumentAINotFound
from pct.document_intelligence.sources import DocumentAISource, collect_fascicolo_document_sources
from pct.fascicolo_sentenza_economica import (
    AUTOMATION_KEY,
    ORIGIN,
    SentenzaAutomationOutcome,
    apply_sentenza_tribunale_automation,
)
from web.helpers import get_fascicoli, get_fatturazione
from web.services.storage_runtime import get_request_studio_db, get_request_storage_runtime
from web.services.tenant_paths import tenant_data_path


def fascicoli_db_path() -> str:
    if has_request_context():
        return tenant_data_path(
            "FASCICOLI_DB",
            str(
                current_app.config.get("FASCICOLI_DB")
                or current_app.config.get("FASCICOLI_DB_PATH")
                or Path(current_app.instance_path) / "fascicoli" / "fascicoli.json"
            ),
            require_tenant=bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False)),
        )
    if has_app_context():
        return str(
            current_app.config.get("FASCICOLI_DB")
            or current_app.config.get("FASCICOLI_DB_PATH")
            or Path(current_app.instance_path) / "fascicoli" / "fascicoli.json"
        )
    return str(Path("data") / "fascicoli" / "fascicoli.json")


def document_ai_tenant_id() -> str:
    if has_request_context():
        tenant = getattr(g, "tenant", None)
        slug = str(getattr(tenant, "slug", "") or "").strip()
        if slug:
            return slug
        user = g.get("utente_corrente")
        user_slug = str(getattr(user, "tenant_slug", "") or session.get("tenant_slug") or "").strip()
        if user_slug:
            return user_slug
    if has_app_context():
        profile = get_request_storage_runtime(fascicoli_db_path())
        return profile.tenant_slug or "single-studio"
    return "single-studio"


def document_ai_user_context() -> dict[str, Any]:
    user = g.get("utente_corrente") if has_request_context() else None
    context: dict[str, Any] = {
        "user": user,
        "user_id": str(getattr(user, "id", "") or getattr(user, "username", "") or ""),
    }
    if has_request_context() and getattr(g, "api_tenant_authenticated", False):
        tenant_slug = str(getattr(g, "api_tenant_slug", "") or getattr(g, "tenant_context_slug", "") or "").strip()
        context.update(
            {
                "user_id": f"api:{tenant_slug or 'tenant'}",
                "tenant_slug": tenant_slug,
                "skip_permission_check": True,
            }
        )
    return context


def build_document_ai_service() -> DocumentAIService:
    anchor = fascicoli_db_path()
    structured_db = get_request_studio_db(anchor) if has_app_context() else None
    repository = DocumentAIRepository.from_fascicoli_db(anchor, structured_db=structured_db)
    max_size = 25 * 1024 * 1024
    if has_app_context():
        max_size = int(current_app.config.get("DOCUMENT_AI_MAX_UPLOAD_BYTES") or max_size)
    return DocumentAIService(repository, get_fascicoli(), max_size_bytes=max_size)


def collect_document_ai_sources_for_fascicolo(
    fascicolo_id: str,
    *,
    tenant_id: str | None = None,
) -> list[DocumentAISource]:
    gestore = get_fascicoli()
    fascicolo = gestore.get(str(fascicolo_id or "").strip())
    if not fascicolo:
        return []
    try:
        from web.services.document_crypto import decrypt_doc
    except Exception:
        decrypt_doc = None
    return collect_fascicolo_document_sources(
        tenant_id=tenant_id or document_ai_tenant_id(),
        fascicolo_id=str(fascicolo_id or "").strip(),
        fascicolo=fascicolo,
        documents_root=getattr(gestore, "documents_dir", Path(".")),
        decrypt=decrypt_doc,
    )


def assert_document_ai_fascicolo_current_tenant(fascicolo_id: str) -> None:
    """Fail closed when a requested fascicolo is not in the current tenant repository."""

    value = str(fascicolo_id or "").strip()
    if not value:
        raise DocumentAINotFound("Documento o fascicolo non trovato")
    fascicolo = get_fascicoli().get(value)
    if not fascicolo:
        raise DocumentAINotFound("Documento o fascicolo non trovato")


def build_lex_indexing_summary_payload(
    fascicolo_id: str,
    *,
    process: bool = False,
    retry_errors: bool = False,
    user_context: object | None = None,
) -> dict[str, Any]:
    assert_document_ai_fascicolo_current_tenant(fascicolo_id)
    tenant_id = document_ai_tenant_id()
    context = user_context if user_context is not None else document_ai_user_context()
    service = build_document_ai_service()
    sources = collect_document_ai_sources_for_fascicolo(fascicolo_id, tenant_id=tenant_id)
    if process:
        result = service.process_lex_indexing_sources(
            tenant_id,
            fascicolo_id,
            sources,
            context,
            retry_errors=retry_errors,
        )
        payload = result.summary.to_dict()
        payload["sentenza_automation"] = _apply_sentenza_automations_for_ready_documents(
            service=service,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            sources=sources,
            user_context=context,
        )
        return payload
    summary: LexIndexingSummary = service.build_lex_indexing_summary(tenant_id, fascicolo_id, sources, context)
    if _lex_summary_needs_automatic_processing(summary, sources):
        result = service.process_lex_indexing_sources(
            tenant_id,
            fascicolo_id,
            sources,
            context,
            retry_errors=True,
        )
        payload = result.summary.to_dict()
        payload["sentenza_automation"] = _apply_sentenza_automations_for_ready_documents(
            service=service,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            sources=sources,
            user_context=context,
        )
        return payload
    payload = summary.to_dict()
    payload["sentenza_automation"] = _apply_sentenza_automations_for_ready_documents(
        service=service,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        sources=sources,
        user_context=context,
    )
    return payload


def _lex_summary_needs_automatic_processing(summary: LexIndexingSummary, sources: list[DocumentAISource]) -> bool:
    if summary.queued or summary.stale or summary.not_indexed:
        return True
    if not summary.errors:
        return False
    return any(
        source.supported and str(source.filename or "").lower().endswith(".p7m")
        for source in sources
    )


def apply_sentenza_automation_for_document_text(
    *,
    fascicolo_id: str,
    tenant_id: str,
    document_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    actor: str = "",
) -> dict[str, Any]:
    """Applica la matrice sentenza a un singolo documento AI già estratto."""

    clean_metadata = dict(metadata or {})
    clean_metadata.setdefault("tenant_id", tenant_id)
    clean_metadata.setdefault("fascicolo_id", fascicolo_id)
    clean_metadata.setdefault("document_id", document_id)
    fascicoli = get_fascicoli()
    fatturazione = get_fatturazione()
    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id=fascicolo_id,
        text=text,
        document_metadata=clean_metadata,
        actor=actor or "Lex AI",
    )
    document_key = _document_key(clean_metadata)
    vector_result: dict[str, Any] = {}
    if outcome.extraction.found and not _sentenza_vector_index_ok(
        fascicoli_repository=fascicoli,
        fascicolo_id=fascicolo_id,
        document_key=document_key,
    ):
        vector_result = _feed_sentenza_vector_index(
            fascicoli_repository=fascicoli,
            fascicolo_id=fascicolo_id,
            tenant_id=tenant_id,
            text=text,
            metadata=clean_metadata,
            outcome=outcome,
        )
        _record_vector_index_result(
            fascicoli_repository=fascicoli,
            fascicolo_id=fascicolo_id,
            document_key=document_key,
            vector_result=vector_result,
        )
    elif outcome.extraction.found:
        vector_result = _existing_sentenza_vector_index(
            fascicoli_repository=fascicoli,
            fascicolo_id=fascicolo_id,
            document_key=document_key,
        )
    payload = outcome.to_dict()
    if vector_result:
        payload["vector_index"] = vector_result
    return payload


def _apply_sentenza_automations_for_ready_documents(
    *,
    service: DocumentAIService,
    tenant_id: str,
    fascicolo_id: str,
    sources: list[DocumentAISource],
    user_context: object,
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    try:
        records = service.list_fascicolo_documents(tenant_id, fascicolo_id, user_context)
    except Exception:
        current_app.logger.exception("Lettura documenti AI non riuscita per automazione sentenza")
        return applied
    source_index = _source_metadata_index(sources)
    for record in records:
        if str(getattr(record, "status", "") or "") != "ready":
            continue
        try:
            text_record = service.get_fascicolo_document_text(tenant_id, fascicolo_id, record.id, user_context)
            metadata = _metadata_for_record(record, source_index)
            result = apply_sentenza_automation_for_document_text(
                fascicolo_id=fascicolo_id,
                tenant_id=tenant_id,
                document_id=record.id,
                text=text_record.text,
                metadata=metadata,
                actor=_actor_from_context(user_context),
            )
            if result.get("applied") or result.get("vector_index"):
                applied.append(result)
        except Exception as exc:
            current_app.logger.exception("Automazione sentenza Lex non riuscita per documento %s", getattr(record, "id", ""))
            applied.append(
                {
                    "applied": False,
                    "message": "Automazione sentenza non completata.",
                    "document_id": getattr(record, "id", ""),
                    "error": str(exc),
                }
            )
    return applied


def _source_metadata_index(sources: list[DocumentAISource]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for source in sources:
        metadata = source.public_metadata()
        nested = metadata.get("metadata")
        if isinstance(nested, dict):
            metadata.update(nested)
        for key in (
            str(source.sha256 or ""),
            str(source.filename or "").casefold(),
            str(source.safe_filename or "").casefold(),
            str(source.source_id or ""),
        ):
            if key:
                index[key] = dict(metadata)
    return index


def _metadata_for_record(record: Any, source_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        str(getattr(record, "sha256", "") or ""),
        str(getattr(record, "original_filename", "") or "").casefold(),
        str(getattr(record, "safe_filename", "") or "").casefold(),
        str(getattr(record, "id", "") or ""),
    ):
        if key and key in source_index:
            metadata.update(source_index[key])
            break
    metadata.update(
        {
            "tenant_id": str(getattr(record, "tenant_id", "") or metadata.get("tenant_id") or ""),
            "fascicolo_id": str(getattr(record, "fascicolo_id", "") or metadata.get("fascicolo_id") or ""),
            "document_id": str(getattr(record, "id", "") or metadata.get("document_id") or ""),
            "documento_id": str(metadata.get("documento_id") or getattr(record, "id", "") or ""),
            "filename": str(getattr(record, "original_filename", "") or metadata.get("filename") or ""),
            "safe_filename": str(getattr(record, "safe_filename", "") or metadata.get("safe_filename") or ""),
            "sha256": str(getattr(record, "sha256", "") or metadata.get("sha256") or ""),
        }
    )
    return metadata


def _actor_from_context(user_context: object) -> str:
    if isinstance(user_context, dict):
        return str(user_context.get("user_id") or user_context.get("username") or "Lex AI")
    return "Lex AI"


def _document_key(metadata: dict[str, Any]) -> str:
    for key in ("document_id", "documento_id", "source_id", "sha256", "filename"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return ""


def _feed_sentenza_vector_index(
    *,
    fascicoli_repository: Any,
    fascicolo_id: str,
    tenant_id: str,
    text: str,
    metadata: dict[str, Any],
    outcome: SentenzaAutomationOutcome,
) -> dict[str, Any]:
    try:
        from lex.providers.local_ai_service import get_local_ai_service

        service = get_local_ai_service()
        fascicolo = fascicoli_repository.get(fascicolo_id)
        extraction = outcome.extraction
        document_key = _document_key(metadata)
        source_id = f"{tenant_id}:{fascicolo_id}:{document_key or metadata.get('sha256') or metadata.get('document_id')}"
        title = _sentenza_vector_title(extraction, fascicolo)
        vector_metadata = {
            "tenant_id": tenant_id,
            "fascicolo_id": fascicolo_id,
            "document_id": str(metadata.get("document_id") or ""),
            "document_key": document_key,
            "sha256": str(metadata.get("sha256") or ""),
            "tipo_documento": "sentenza_tribunale",
            "data_sentenza": extraction.sentence_date,
            "rg": _rg_label(extraction),
            "cliente": str(getattr(fascicolo, "nome_cliente", "") or metadata.get("cliente") or ""),
            "importo_liquidazione": extraction.liquidazione_importo,
            "contributo_unificato": extraction.contributo_unificato_importo,
            "fondo_spese": extraction.fondo_spese_importo,
            "proforma_id": outcome.proforma_id,
            "origin": ORIGIN,
        }
        indexed = service.index_text_document(
            source_type="lex_sentenza_tribunale",
            source_id=source_id,
            practice_id=fascicolo_id,
            title=title,
            text=_sentenza_vector_text(extraction, fascicolo, metadata, outcome, text),
            metadata=vector_metadata,
        )
        embedded = {}
        document_id = str(indexed.get("document_id") or "")
        if document_id:
            try:
                embedded = service.embed_all_pending_chunks(document_id=document_id, batch_size=100, max_batches=20)
            except Exception as exc:
                embedded = {"status": "error", "error": str(exc)}
        return {
            "ok": True,
            "status": indexed.get("status"),
            "document_id": document_id,
            "chunk_count": indexed.get("chunk_count"),
            "embedding": embedded,
        }
    except Exception as exc:
        current_app.logger.exception("Indicizzazione vettoriale Lex AI non riuscita per sentenza")
        return {"ok": False, "status": "error", "error": str(exc)}


def _record_vector_index_result(
    *,
    fascicoli_repository: Any,
    fascicolo_id: str,
    document_key: str,
    vector_result: dict[str, Any],
) -> None:
    if not document_key:
        return
    fascicolo = fascicoli_repository.get(fascicolo_id)
    if not fascicolo:
        return
    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    automation = dict(payments.get(AUTOMATION_KEY) or {})
    vector_indexes = automation.get("vector_indexes") if isinstance(automation.get("vector_indexes"), dict) else {}
    vector_indexes[document_key] = dict(vector_result or {})
    automation["vector_indexes"] = vector_indexes
    payments[AUTOMATION_KEY] = automation
    fascicoli_repository.aggiorna(fascicolo_id, pagamenti=payments)


def _existing_sentenza_vector_index(
    *,
    fascicoli_repository: Any,
    fascicolo_id: str,
    document_key: str,
) -> dict[str, Any]:
    if not document_key:
        return {}
    fascicolo = fascicoli_repository.get(fascicolo_id)
    if not fascicolo:
        return {}
    payments = getattr(fascicolo, "pagamenti", {}) or {}
    automation = payments.get(AUTOMATION_KEY) if isinstance(payments, dict) else {}
    if not isinstance(automation, dict):
        return {}
    vector_indexes = automation.get("vector_indexes")
    if not isinstance(vector_indexes, dict):
        return {}
    result = vector_indexes.get(document_key)
    return dict(result) if isinstance(result, dict) else {}


def _sentenza_vector_index_ok(
    *,
    fascicoli_repository: Any,
    fascicolo_id: str,
    document_key: str,
) -> bool:
    result = _existing_sentenza_vector_index(
        fascicoli_repository=fascicoli_repository,
        fascicolo_id=fascicolo_id,
        document_key=document_key,
    )
    return bool(result.get("ok") and result.get("document_id"))


def _rg_label(extraction: Any) -> str:
    if extraction.rg_number and extraction.rg_year:
        return f"{extraction.rg_number}/{extraction.rg_year}"
    return ""


def _sentenza_vector_title(extraction: Any, fascicolo: Any) -> str:
    sentence = ""
    if extraction.sentence_number and extraction.sentence_year:
        sentence = f"Sentenza Tribunale n. {extraction.sentence_number}/{extraction.sentence_year}"
    rg = _rg_label(extraction)
    title = sentence or "Sentenza Tribunale"
    if rg:
        title = f"{title} - RG {rg}"
    fascicolo_title = str(getattr(fascicolo, "titolo", "") or "").strip()
    return f"{title} - {fascicolo_title}" if fascicolo_title else title


def _sentenza_vector_text(
    extraction: Any,
    fascicolo: Any,
    metadata: dict[str, Any],
    outcome: SentenzaAutomationOutcome,
    text: str,
) -> str:
    rows = [
        "Scheda conoscenza Lex AI - Sentenza Tribunale",
        f"Fascicolo: {getattr(fascicolo, 'titolo', '') or getattr(fascicolo, 'numero_rg', '') or metadata.get('fascicolo_id', '')}",
        f"RG: {_rg_label(extraction) or metadata.get('numero_rg', '')}",
        f"Data sentenza: {extraction.sentence_date}",
        f"Liquidazione giudice: {extraction.liquidazione_importo if extraction.liquidazione_importo is not None else 'n.d.'}",
        f"Contributo unificato: {extraction.contributo_unificato_importo if extraction.contributo_unificato_importo is not None else 'n.d.'}",
        f"Fondo spese: {extraction.fondo_spese_importo if extraction.fondo_spese_importo is not None else 'n.d.'}",
        f"Proforma collegata: {outcome.proforma_id or 'n.d.'}",
        f"Documento fonte: {metadata.get('filename') or metadata.get('document_id') or 'n.d.'}",
        "",
        "Estratto liquidazione:",
        extraction.liquidazione_titolo or "n.d.",
        "",
        "Testo sentenza:",
        str(text or "")[:200000],
    ]
    return "\n".join(str(row) for row in rows)


__all__ = [
    "build_document_ai_service",
    "build_lex_indexing_summary_payload",
    "collect_document_ai_sources_for_fascicolo",
    "document_ai_tenant_id",
    "document_ai_user_context",
    "fascicoli_db_path",
    "assert_document_ai_fascicolo_current_tenant",
    "apply_sentenza_automation_for_document_text",
]
