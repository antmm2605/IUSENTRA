"""Adapter di retrieval per la ricerca web ufficiale riconosciuta."""

from __future__ import annotations

from lex.contracts import EvidenceItem
from lex.memory.web_execution import is_web_execution_request
from lex.research.source_registry import get_source_registry
from lex.retrieval.official_web import (
    build_source_registry_context,
    resolve_official_source_ids_for_query,
    search_recognized_official_web,
)

_RECENCY_TOKENS: tuple[str, ...] = (
    "ultima", "ultime", "ultimo", "ultimi",
    "recent", "aggiornat", "oggi", "corrente", "vigente", "attuale",
)
_LEGAL_LOOKUP_TOKENS: tuple[str, ...] = (
    "web",
    "fonte ufficiale",
    "fonti ufficiali",
    "norma",
    "normativa",
    "legge",
    "decreto",
    "sentenza",
    "sentenze",
    "giurisprudenza",
    "cassazione",
    "corte costituzionale",
    "corte d'appello",
    "tribunale",
    "gazzetta",
    "agenzia entrate",
    "telematico",
    "pst",
    "pdp",
    "pat",
    "ptt",
    "pec",
    "ini pec",
    "ini-pec",
    "registro imprese",
    "reginde",
    "siga",
    "sigit",
    "firma",
    "reginde",
    "circolari",
    "circolare",
    "codice civile",
    "codice penale",
    "codice procedura",
    "regio decreto",
    "d.lgs",
    "d.l.",
    "l. n.",
    "art.",
    "articolo",
    "massima",
    "principio di diritto",
    "orientamento",
    "motivazione",
)
_FASCICOLO_FIRST_WORKFLOWS = {"fascicolo", "documento", "udienza"}


def _clean_spaces(value) -> str:
    return " ".join(str(value or "").split()).strip()


def _metadata_flag(request, *keys: str) -> bool:
    metadata = getattr(request, "metadata", {}) or {}
    for key in keys:
        if bool(metadata.get(key)):
            return True
    return False


def _should_search_official_web(request, workflow: str) -> bool:
    metadata = getattr(request, "metadata", {}) or {}
    text = _clean_spaces(getattr(request, "query", "")).lower()
    has_legal_lookup = any(token in text for token in _LEGAL_LOOKUP_TOKENS)
    external_reason = _clean_spaces(metadata.get("external_sources_reason"))

    if workflow in _FASCICOLO_FIRST_WORKFLOWS and bool(getattr(request, "fascicolo_id", None)):
        if not bool(getattr(request, "allow_external_research", False)):
            return False
        if external_reason and has_legal_lookup:
            return True
        if _metadata_flag(
            request,
            "allow_web_search",
            "needs_web_search",
            "web_execution_requested",
            "force_official_web_search",
        ) and has_legal_lookup:
            return True
        return False

    if _metadata_flag(
        request,
        "allow_web_search",
        "needs_web_search",
        "web_execution_requested",
        "force_official_web_search",
    ):
        return True

    if not text:
        return False
    if is_web_execution_request(text):
        return True

    has_recency = any(token in text for token in _RECENCY_TOKENS)
    if workflow in {"economico", "cabina", "next_action", "compliance"} and not has_legal_lookup:
        return False
    if has_legal_lookup and has_recency:
        return True

    # Workflow che beneficiano della ricerca web con semplici token normativi
    if workflow in {"telematico", "intelligence", "atto"} and has_legal_lookup:
        return True

    if get_source_registry().search(text, limit=2):
        return True

    return False


class OfficialWebSource:
    source_name = "official_web"

    def __init__(self, *, request_get=None) -> None:
        self._request_get = request_get

    @staticmethod
    def should_include(request, workflow: str) -> bool:
        return _should_search_official_web(request, workflow)

    def search(self, queries, request, context):
        workflow = _clean_spaces((context or {}).get("workflow") or (getattr(request, "metadata", {}) or {}).get("workflow"))
        if not self.should_include(request, workflow):
            return []

        query = _clean_spaces(queries[0] if queries else getattr(request, "query", ""))
        metadata_source_ids = (getattr(request, "metadata", {}) or {}).get("source_ids")
        if isinstance(metadata_source_ids, str):
            metadata_source_ids = [metadata_source_ids]
        source_ids = resolve_official_source_ids_for_query(
            query,
            explicit_source_ids=list(metadata_source_ids or []),
            limit=4,
        )
        registry_context = build_source_registry_context(
            query,
            explicit_source_ids=list(metadata_source_ids or []),
            limit=6,
        )
        request_metadata = getattr(request, "metadata", None)
        if isinstance(request_metadata, dict):
            request_metadata["source_registry"] = registry_context
        rows = search_recognized_official_web(
            query,
            source_ids=source_ids,
            request_get=self._request_get,
            limit_results=4,
        )

        evidence: list[EvidenceItem] = []
        for row in rows:
            url = _clean_spaces(row.get("url"))
            source_name = _clean_spaces(row.get("source_name") or row.get("domain") or "fonte ufficiale")
            score = 0.93 if str(row.get("kind") or "").lower() == "pdf" else 0.85
            evidence.append(
                EvidenceItem(
                    source_type="web_ufficiale",
                    source_id=str(row.get("id") or ""),
                    title=_clean_spaces(row.get("title") or source_name) or source_name,
                    content=_clean_spaces(row.get("excerpt") or f"Risorsa ufficiale trovata su {source_name}."),
                    score=score,
                    trust_class="A",
                    source_level=1,
                    verified_reference=True,
                    authority=source_name or "Fonte ufficiale",
                    official_url=_clean_spaces(row.get("official_url") or url) or None,
                    metadata={
                        "authority": "official_web",
                        "url": url,
                        "official_url": _clean_spaces(row.get("official_url") or url),
                        "domain": _clean_spaces(row.get("domain") or ""),
                        "source_name": source_name,
                        "official_source_id": _clean_spaces(row.get("source_id") or ""),
                        "kind": _clean_spaces(row.get("kind") or ""),
                        "source_registry_key": _clean_spaces(row.get("source_id") or ""),
                        "source_access_status": _clean_spaces(row.get("source_access_status") or ""),
                        "source_access_label": _clean_spaces(row.get("source_access_label") or ""),
                        "source_category": _clean_spaces(row.get("source_category") or ""),
                        "source_priority": _clean_spaces(row.get("source_priority") or ""),
                        "source_requires_credentials": bool(row.get("source_requires_credentials")),
                        "source_restricted": bool(row.get("source_restricted")),
                        "source_supports_web_search": bool(row.get("source_supports_web_search", True)),
                    },
                )
            )
        return evidence


__all__ = ["OfficialWebSource"]
