"""Service layer della Ricerca Studio."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from .indexer import GlobalSearchIndexer
from .repository import GlobalSearchRepository


def default_global_search_db_path(search_index_path: str | Path) -> Path:
    path = Path(search_index_path or "./data/search/index.db")
    if path.suffix:
        return path.with_name("global_search.db")
    return path / "global_search.db"


class GlobalSearchService:
    def __init__(
        self,
        repository: GlobalSearchRepository,
        *,
        indexer: GlobalSearchIndexer | None = None,
    ):
        self.repository = repository
        self.indexer = indexer or GlobalSearchIndexer(repository)

    def search(
        self,
        context: dict[str, Any],
        query: str,
        *,
        entity_types: list[str] | None = None,
        limit: int = 20,
        user: Any = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        tenant_id = str(context.get("tenant_id") or "default")
        results = self.repository.search(
            tenant_id=tenant_id,
            query=query,
            entity_types=entity_types,
            limit=limit,
            user=user,
        )
        took_ms = (perf_counter() - started) * 1000
        return {
            "ok": True,
            "query": query,
            "tenant_id": tenant_id,
            "took_ms": round(took_ms, 2),
            "total": len(results),
            "results": [result.to_api() for result in results],
        }

    def suggest(self, context: dict[str, Any], query: str, *, limit: int = 8) -> dict[str, Any]:
        tenant_id = str(context.get("tenant_id") or "default")
        return {
            "ok": True,
            "suggestions": self.repository.suggest(tenant_id=tenant_id, query=query, limit=limit),
        }

    def reindex(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "report": self.indexer.reindex_all(context).to_dict(), "stats": self.stats(context)}

    def reindex_entity(self, context: dict[str, Any], entity_type: str, entity_id: str) -> dict[str, Any]:
        return {"ok": True, "report": self.indexer.reindex_entity(context, entity_type, entity_id), "stats": self.stats(context)}

    def stats(self, context: dict[str, Any]) -> dict[str, Any]:
        tenant_id = str(context.get("tenant_id") or "default")
        return self.repository.stats(tenant_id)

    def search_for_lex(self, context: dict[str, Any], query: str, limit: int = 10) -> list[dict[str, Any]]:
        payload = self.search(context, query, limit=limit)
        return [
            {
                "fonte": "Ricerca Studio",
                "titolo": item["title"],
                "tipo": item["entity_type"],
                "url": item["source_url"],
                "snippet": item["snippet"],
                "affidabilita": "interna_verificata",
                "data_acquisizione": item.get("date") or "",
                "metadata": item.get("metadata") or {},
            }
            for item in payload.get("results", [])
        ]


def search_for_lex(context: dict[str, Any], query: str, limit: int = 10) -> list[dict[str, Any]]:
    search_index_path = context.get("search_index_path") or "./data/search/index.db"
    repository = GlobalSearchRepository(default_global_search_db_path(search_index_path))
    try:
        return GlobalSearchService(repository).search_for_lex(context, query, limit)
    finally:
        repository.close()
