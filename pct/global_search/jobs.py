"""Job riusabili per reindicizzazione Ricerca Studio."""

from __future__ import annotations

from typing import Any

from .service import GlobalSearchService


def reindex_global_search(service: GlobalSearchService, context: dict[str, Any]) -> dict[str, Any]:
    return service.reindex(context)
