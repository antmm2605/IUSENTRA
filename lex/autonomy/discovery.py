"""Provider di ricerca del ciclo autonomo (astrazione offline/web).

- `SearchProvider`: interfaccia (Protocol) — un metodo `search`.
- `StaticSearchProvider`: risultati precotti per i test e la modalità offline;
  deterministico (output ordinato per URL), zero rete; supporta `content`
  inline che il reader usa senza fetch.
- `ConfigurableWebSearchProvider`: avvolge la ricerca web GOVERNATA esistente
  `lex.retrieval.official_web.search_recognized_official_web` (allowlist +
  guardia SSRF + cache). L'import è PIGRO dentro `search()`: quel modulo
  importa `pct.legal_intelligence` a livello di modulo (catena pesante,
  stubbata nei test unit), quindi il percorso offline non lo tocca mai.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from lex.sources.models import SourceCandidate


class SearchProvider(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
        """Restituisce candidati fonte per la query (mai eccezioni di rete)."""
        ...


class StaticSearchProvider:
    """Provider offline: mappa query → risultati precotti (test e demo CLI)."""

    def __init__(self, results: Mapping[str, list[Mapping[str, Any]]] | None = None) -> None:
        self._results = {str(query).casefold(): list(rows) for query, rows in (results or {}).items()}

    def search(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
        needle = " ".join(str(query or "").split()).casefold()
        rows = self._results.get(needle)
        if rows is None:
            # Fallback per contenimento: robusto a piccole varianti di query.
            for key, candidate_rows in sorted(self._results.items()):
                if key and (key in needle or needle in key):
                    rows = candidate_rows
                    break
        candidates = [
            SourceCandidate(
                url=str(row.get("url") or ""),
                title=str(row.get("title") or ""),
                snippet=str(row.get("snippet") or ""),
                source_id=str(row.get("source_id") or ""),
                discovered_by="static",
                query=query,
                confidence=float(row.get("confidence") or 0.5),
                content=str(row.get("content") or ""),
                content_type=str(row.get("content_type") or "text/plain"),
            )
            for row in rows or []
            if str(row.get("url") or "").strip()
        ]
        candidates.sort(key=lambda item: item.url)
        return candidates[: max(1, int(limit))]


class ConfigurableWebSearchProvider:
    """Provider web governato (riuso di official_web, import pigro)."""

    def __init__(
        self,
        *,
        source_ids: list[str] | None = None,
        request_get: Callable[..., Any] | None = None,
        limit_results: int = 4,
    ) -> None:
        self.source_ids = list(source_ids or [])
        self.request_get = request_get
        self.limit_results = max(1, int(limit_results))

    def search(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
        # Import PIGRO obbligatorio: vedi docstring del modulo.
        from lex.retrieval.official_web import search_recognized_official_web

        # official_web antepone già `site:<dominio>` per ogni dominio governato:
        # i token site: del query_builder vanno rimossi per evitare doppioni.
        clean_query = " ".join(token for token in str(query or "").split() if not token.casefold().startswith("site:"))
        kwargs: dict[str, Any] = {"limit_results": min(limit, self.limit_results)}
        if self.source_ids:
            kwargs["source_ids"] = self.source_ids
        if self.request_get is not None:
            kwargs["request_get"] = self.request_get
        try:
            rows = search_recognized_official_web(clean_query, **kwargs)
        except Exception:
            rows = []
        candidates = [
            SourceCandidate(
                url=str(row.get("url") or row.get("official_url") or ""),
                title=str(row.get("title") or ""),
                snippet=str(row.get("snippet") or row.get("excerpt") or ""),
                source_id=str(row.get("source_id") or row.get("source") or ""),
                discovered_by="official_web",
                query=query,
                confidence=float(row.get("confidence") or 0.6),
            )
            for row in rows or []
            if isinstance(row, Mapping) and str(row.get("url") or row.get("official_url") or "").strip()
        ]
        candidates.sort(key=lambda item: item.url)
        return candidates[: max(1, int(limit))]


__all__ = ["ConfigurableWebSearchProvider", "SearchProvider", "StaticSearchProvider"]
