"""Indicizzazione automatica interna dei documenti del fascicolo per Lex."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import LexIndexingSummary
from .security import DocumentAIValidationError
from .sources import DocumentAISource

_READY = "ready"
_ERROR = "error"
_INDEXING = "indexing"
_QUEUED = "queued"
_STALE = "stale"
_ARCHIVED = "archived"
_STATE_PRIORITY = {
    "not_indexed": 0,
    _ERROR: 1,
    _ARCHIVED: 2,
    _INDEXING: 3,
    _QUEUED: 4,
    _STALE: 4,
    _READY: 5,
}


@dataclass(slots=True)
class DocumentAIIndexingResult:
    summary: LexIndexingSummary
    indexed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class DocumentAIIndexer:
    def __init__(self, service: Any) -> None:
        self.service = service

    def summarize(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        sources: list[DocumentAISource],
        user_context: object,
    ) -> LexIndexingSummary:
        records = self.service.list_fascicolo_documents(tenant_id, fascicolo_id, user_context)
        return build_lex_indexing_summary(sources=sources, records=records)

    def process(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        sources: list[DocumentAISource],
        user_context: object,
        retry_errors: bool = False,
    ) -> DocumentAIIndexingResult:
        records = self.service.list_fascicolo_documents(tenant_id, fascicolo_id, user_context)
        indexed = 0
        skipped = 0
        errors: list[str] = []
        for source in sources:
            state = _state_for_source(source, records)
            if state == _READY or state == _INDEXING or state == _ARCHIVED:
                skipped += 1
                continue
            if state == _ERROR and not retry_errors:
                skipped += 1
                continue
            if not source.supported:
                errors.append(f"{source.filename}: formato non supportato per indicizzazione Lex.")
                skipped += 1
                continue
            try:
                upload_filename = source.safe_filename if source.file_type == "bin" else source.filename
                self.service.upload_document_bytes_for_fascicolo(
                    tenant_id=tenant_id,
                    fascicolo_id=fascicolo_id,
                    filename=upload_filename,
                    content=source.read_bytes(),
                    mime_type=source.mime_type,
                    user_context=user_context,
                    source_metadata=source.public_metadata(),
                )
                indexed += 1
            except (OSError, DocumentAIValidationError) as exc:
                errors.append(f"{source.filename}: {exc}")
            except Exception as exc:
                errors.append(f"{source.filename}: indicizzazione non completata ({exc})")
        refreshed = self.service.list_fascicolo_documents(tenant_id, fascicolo_id, user_context)
        summary = build_lex_indexing_summary(sources=sources, records=refreshed, extra_warnings=errors)
        return DocumentAIIndexingResult(summary=summary, indexed=indexed, skipped=skipped, errors=errors)


def build_lex_indexing_summary(
    *,
    sources: list[DocumentAISource],
    records: list[Any],
    extra_warnings: list[str] | None = None,
) -> LexIndexingSummary:
    states = [_state_for_source(source, records) for source in sources]
    counts = Counter(states)
    total = len(sources)
    last_indexed_at = _last_ready_update(records)
    status = _overall_status(total=total, counts=counts)
    warnings = _indexing_warnings(sources, records, extra_warnings=extra_warnings)
    return LexIndexingSummary(
        total_documents=total,
        ready=int(counts[_READY]),
        queued=int(counts[_QUEUED]),
        indexing=int(counts[_INDEXING]),
        errors=int(counts[_ERROR]),
        stale=int(counts[_STALE]),
        not_indexed=int(counts["not_indexed"]),
        archived=int(counts[_ARCHIVED]),
        last_indexed_at=last_indexed_at,
        status=status,
        warnings=warnings,
    )


def _state_for_source(source: DocumentAISource, records: list[Any]) -> str:
    if not source.supported:
        return _ERROR
    if not source.sha256:
        return "not_indexed"
    same_hash = [record for record in records if str(getattr(record, "sha256", "") or "") == source.sha256]
    if same_hash:
        states = [_state_from_record(record) for record in same_hash]
        return max(states, key=lambda state: _STATE_PRIORITY.get(state, 0))
    source_names = {source.filename.casefold(), source.safe_filename.casefold()}
    for record in records:
        names = {
            str(getattr(record, "original_filename", "") or "").casefold(),
            str(getattr(record, "safe_filename", "") or "").casefold(),
        }
        if source_names & names:
            return _STALE
    return _QUEUED


def _state_from_record(record: Any) -> str:
    status = str(getattr(record, "status", "") or "").strip()
    if status == "ready":
        return _READY
    if status == "processing":
        if _processing_record_is_stale(record):
            return _STALE
        return _INDEXING
    if status == "uploaded":
        return _QUEUED
    if status == "archived":
        return _ARCHIVED
    if status == "error":
        return _ERROR
    return "not_indexed"


def _processing_record_is_stale(record: Any) -> bool:
    updated = _parse_datetime(getattr(record, "updated_at", "") or getattr(record, "created_at", ""))
    if updated is None:
        return False
    now = datetime.now(timezone.utc)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    minutes = _stale_processing_minutes()
    return (now - updated).total_seconds() >= minutes * 60


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _stale_processing_minutes() -> int:
    try:
        value = int(str(os.environ.get("IUSENTRA_DOCUMENT_AI_INDEXING_STALE_MINUTES", "30")).strip())
    except (TypeError, ValueError):
        return 30
    return max(5, min(1440, value))


def _last_ready_update(records: list[Any]) -> str | None:
    values = [
        str(getattr(record, "updated_at", "") or getattr(record, "created_at", "") or "")
        for record in records
        if str(getattr(record, "status", "") or "") == "ready"
    ]
    values = [value for value in values if value]
    return max(values) if values else None


def _overall_status(*, total: int, counts: Counter[str]) -> str:
    if total <= 0:
        return "ready"
    if counts[_ERROR] and not counts[_READY]:
        return "error"
    if counts[_ERROR]:
        return "partial"
    if counts[_STALE]:
        return "stale"
    if counts[_INDEXING] or counts[_QUEUED] or counts["not_indexed"]:
        return "working"
    if counts[_READY] == total:
        return "ready"
    return "partial"


def _indexing_warnings(
    sources: list[DocumentAISource],
    records: list[Any],
    *,
    extra_warnings: list[str] | None = None,
) -> list[str]:
    warnings: list[str] = list(extra_warnings or [])
    for source in sources:
        state = _state_for_source(source, records)
        if state == _ERROR and not source.supported:
            warnings.append(f"{source.filename}: formato non supportato per indicizzazione Lex.")
        elif state == _ERROR:
            warnings.append(f"{source.filename}: indicizzazione non completata; riprova o verifica il documento.")
        elif state == _STALE:
            warnings.append(f"{source.filename}: documento cambiato dopo l'ultimo indice; aggiorna l'indice.")
        elif state == "not_indexed":
            warnings.append(f"{source.filename}: documento non ancora indicizzabile per Lex.")
    return _unique_warnings(warnings)


def _unique_warnings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        key = clean.casefold()
        if not clean or key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out[:12]


__all__ = ["DocumentAIIndexer", "DocumentAIIndexingResult", "build_lex_indexing_summary"]
