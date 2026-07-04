"""Provider di ricerca del ciclo autonomo (astrazione offline/web/archivi).

- `SearchProvider`: interfaccia (Protocol) — un metodo `search`.
- `StaticSearchProvider`: risultati precotti per i test e la modalità offline;
  deterministico (output ordinato per URL), zero rete; supporta `content`
  inline che il reader usa senza fetch.
- `ConfigurableWebSearchProvider`: avvolge la ricerca web GOVERNATA esistente
  `lex.retrieval.official_web.search_recognized_official_web` (allowlist +
  guardia SSRF + cache). L'import è PIGRO dentro `search()`: quel modulo
  importa `pct.legal_intelligence` a livello di modulo (catena pesante,
  stubbata nei test unit), quindi il percorso offline non lo tocca mai.
- `LocalArchiveSearchProvider`: legge gli ARCHIVI UFFICIALI LOCALI di
  Normattiva e Gazzetta Ufficiale (scaricati ogni notte dal job
  `legal_official_archives_daily` via canali sanzionati) tramite il retriever
  esistente `lex.retrieval.official_sources_retriever`. Il testo arriva dal
  mirror locale (zero rete, immune ai blocchi anti-bot del sito live), ma
  l'autorità resta ancorata all'URL ufficiale (URN Normattiva risolto in
  `https://www.normattiva.it/uri-res/N2Ls?<urn>`): il trust valuta il dominio
  reale, mai un indirizzo fabbricato. Righe senza URL http o senza testo
  vengono scartate (fail-closed).
- `CompositeSearchProvider`: concatena più provider in ordine (archivi locali
  PRIMA della ricerca web) con dedup per URL e tetto complessivo.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
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


class LocalArchiveSearchProvider:
    """Provider sugli archivi ufficiali locali Normattiva/Gazzetta (zero rete)."""

    def __init__(self, *, per_archive_limit: int = 4) -> None:
        self.per_archive_limit = max(1, int(per_archive_limit))

    def search(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
        clean_query = " ".join(
            token for token in str(query or "").replace('"', " ").split() if not token.casefold().startswith("site:")
        )
        if not clean_query:
            return []
        # Import pigro del retriever (stdlib puro: sqlite3/json/re).
        try:
            from lex.retrieval import official_sources_retriever as retriever
        except Exception:
            return []
        rows: list[tuple[str, Mapping[str, Any]]] = []
        try:
            rows.extend(("normattiva", row) for row in retriever.search_normattiva(clean_query, limit=self.per_archive_limit))
        except Exception:
            pass
        try:
            rows.extend(("gazzetta_ufficiale", row) for row in retriever.search_gazzetta(clean_query, limit=self.per_archive_limit))
        except Exception:
            pass
        candidates: list[SourceCandidate] = []
        seen: set[str] = set()
        for archive_id, row in rows:
            url = _archive_http_url(str(row.get("url_origine") or ""))
            testo = " ".join(str(row.get("testo") or "").split())
            if not url or not testo:
                continue  # fail-closed: niente ancora ufficiale o niente testo
            key = url.casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                SourceCandidate(
                    url=url,
                    title=str(row.get("titolo") or ""),
                    snippet=testo[:220],
                    source_id=f"archivio_locale:{archive_id}",
                    discovered_by="archivio_locale",
                    query=query,
                    confidence=0.9,
                    content=testo,
                    content_type="text/plain",
                )
            )
            if len(candidates) >= max(1, int(limit)):
                break
        return candidates


def _archive_http_url(url_origine: str) -> str:
    """URL http ufficiale della riga d'archivio; '' se non ancorabile."""

    value = url_origine.strip()
    if value.casefold().startswith(("http://", "https://")):
        return value
    # URN con corpo reale (es. urn:nir:stato:legge:1990-08-07;241): un "urn:"
    # nudo produrrebbe un'ancora generica non onesta -> scartato (run #4).
    if value.casefold().startswith("urn:") and len(value) > len("urn:"):
        return f"https://www.normattiva.it/uri-res/N2Ls?{value}"
    return ""


class LocalCorpusSearchProvider:
    """Provider sul corpus giurisprudenza locale (sentenze/massime verificate).

    Legge il corpus SQLite popolato dai motori di produzione
    (`pct/giurisprudenza_corpus.py`, FTS su sentenze/massime): il contenuto è
    la massima ufficiale/principio sintetico, l'ancora è l'URL ufficiale della
    decisione. Entrano SOLO le sentenze che superano `can_cite_sentenza`
    (stato verificato + ancora ufficiale/ECLI): niente massime non citabili.
    Corpus assente -> risultato vuoto, senza mai creare il database.
    """

    def __init__(self, *, db_path: str | Path | None = None, per_query_limit: int = 6) -> None:
        self._db_path = Path(db_path) if db_path else None
        self.per_query_limit = max(1, int(per_query_limit))

    def search(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
        clean_query = " ".join(
            token for token in str(query or "").replace('"', " ").split() if not token.casefold().startswith("site:")
        )
        if not clean_query:
            return []
        db_path = self._db_path or _default_corpus_db_path()
        if not db_path.exists():
            return []  # mai creare il corpus da qui: solo lettura
        try:
            from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza

            manager = GestioneCorpusGiurisprudenza(str(db_path))
            rows = manager.cerca_sentenze(q=clean_query, limit=self.per_query_limit)
        except Exception:
            return []
        candidates: list[SourceCandidate] = []
        seen: set[str] = set()
        for row in rows:
            if not manager.can_cite_sentenza(row):
                continue  # fail-closed: solo decisioni verificate e ancorate
            url = str(row.get("url_pagina_ufficiale") or row.get("url_pdf_ufficiale") or "").strip()
            massima = " ".join(str(row.get("massima_ufficiale") or "").split())
            principio = " ".join(str(row.get("principio_sintetico") or "").split())
            contenuto = " ".join(part for part in (str(row.get("titolo") or ""), massima, principio) if part).strip()
            if not url or not (massima or principio):
                continue  # senza ancora http o senza sostanza non si impara
            key = url.casefold()
            if key in seen:
                continue
            seen.add(key)
            estremi = " ".join(
                str(part)
                for part in (row.get("organo_giudicante"), row.get("numero_sentenza"), row.get("anno_sentenza"))
                if part
            )
            candidates.append(
                SourceCandidate(
                    url=url,
                    title=str(row.get("titolo") or estremi or "Sentenza dal corpus locale"),
                    snippet=contenuto[:220],
                    source_id="corpus_locale:giurisprudenza",
                    discovered_by="corpus_locale",
                    query=query,
                    confidence=0.9,
                    content=contenuto,
                    content_type="text/plain",
                )
            )
            if len(candidates) >= max(1, int(limit)):
                break
        return candidates


def _default_corpus_db_path() -> Path:
    import os

    from pct.giurisprudenza_corpus import derive_corpus_db_path

    anchor = str(os.getenv("PCT_GIURISPRUDENZA_DB", "") or "").strip()
    if not anchor:
        for key in ("PCT_DATA_ROOT", "IUSENTRA_DATA_DIR"):
            root = str(os.getenv(key, "") or "").strip()
            if root:
                anchor = str(Path(root) / "intelligence" / "giurisprudenza.json")
                break
    if not anchor:
        anchor = str(Path("data") / "intelligence" / "giurisprudenza.json")
    return Path(derive_corpus_db_path(anchor))


class CompositeSearchProvider:
    """Concatena provider in ordine (es. archivi locali, poi web governato)."""

    def __init__(self, providers: list[SearchProvider]) -> None:
        self.providers = list(providers)

    def search(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
        cap = max(1, int(limit))
        results: list[SourceCandidate] = []
        seen: set[str] = set()
        for provider in self.providers:
            if len(results) >= cap:
                break
            try:
                candidates = provider.search(query, limit=cap - len(results))
            except Exception:
                continue  # un provider guasto non ferma gli altri
            for candidate in candidates:
                key = candidate.url.casefold()
                if not candidate.url or key in seen:
                    continue
                seen.add(key)
                results.append(candidate)
                if len(results) >= cap:
                    break
        return results


__all__ = [
    "CompositeSearchProvider",
    "ConfigurableWebSearchProvider",
    "LocalArchiveSearchProvider",
    "LocalCorpusSearchProvider",
    "SearchProvider",
    "StaticSearchProvider",
]
