"""Ricerca Studio: indice operativo globale tenant-aware."""

from .models import GlobalSearchDocument, GlobalSearchResult
from .repository import GlobalSearchRepository
from .service import GlobalSearchService, search_for_lex

__all__ = [
    "GlobalSearchDocument",
    "GlobalSearchRepository",
    "GlobalSearchResult",
    "GlobalSearchService",
    "search_for_lex",
]
