"""Indicizzazione incrementale e completa della Ricerca Studio."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any

from .adapters import BaseSearchAdapter, default_adapters
from .models import GlobalSearchDocument
from .repository import GlobalSearchRepository


@dataclass(slots=True)
class ReindexReport:
    tenant_id: str
    indexed: int = 0
    removed: int = 0
    took_ms: float = 0.0
    per_adapter: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "indexed": self.indexed,
            "removed": self.removed,
            "took_ms": round(self.took_ms, 2),
            "per_adapter": self.per_adapter,
            "errors": self.errors,
            "started_at": self.started_at,
        }


class GlobalSearchIndexer:
    def __init__(
        self,
        repository: GlobalSearchRepository,
        adapters: list[BaseSearchAdapter] | None = None,
    ):
        self.repository = repository
        self.adapters = adapters or default_adapters()

    def collect_documents(self, context: dict[str, Any]) -> tuple[list[GlobalSearchDocument], dict[str, int], list[dict[str, str]]]:
        documents: list[GlobalSearchDocument] = []
        per_adapter: dict[str, int] = {}
        errors: list[dict[str, str]] = []
        for adapter in self.adapters:
            name = adapter.__class__.__name__
            try:
                items = adapter.collect(context)
                documents.extend(items)
                per_adapter[name] = len(items)
            except Exception as exc:
                per_adapter[name] = 0
                errors.append({"adapter": name, "error": str(exc)})
        return documents, per_adapter, errors

    def reindex_all(self, context: dict[str, Any]) -> ReindexReport:
        tenant_id = str(context.get("tenant_id") or "default")
        started = perf_counter()
        documents, per_adapter, errors = self.collect_documents(context)
        removed = self.repository.clear_tenant(tenant_id)
        indexed = self.repository.upsert_many(documents)
        report = ReindexReport(
            tenant_id=tenant_id,
            indexed=indexed,
            removed=removed,
            took_ms=(perf_counter() - started) * 1000,
            per_adapter=per_adapter,
            errors=errors,
        )
        self.repository.audit(tenant_id, "reindex_all", report.to_dict())
        return report

    def reindex_entity(self, context: dict[str, Any], entity_type: str, entity_id: str) -> dict[str, Any]:
        tenant_id = str(context.get("tenant_id") or "default")
        documents, _, errors = self.collect_documents(context)
        matched = [
            doc for doc in documents
            if doc.entity_type == entity_type and str(doc.entity_id) == str(entity_id)
        ]
        removed = self.repository.remove_entity(tenant_id, entity_type, str(entity_id))
        indexed = self.repository.upsert_many(matched)
        payload = {"tenant_id": tenant_id, "entity_type": entity_type, "entity_id": entity_id, "removed": removed, "indexed": indexed, "errors": errors}
        self.repository.audit(tenant_id, "reindex_entity", payload)
        return payload
