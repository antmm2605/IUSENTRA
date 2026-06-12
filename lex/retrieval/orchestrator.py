from __future__ import annotations

from dataclasses import asdict

from lex.guards.exact_case_law_guard import check_exact_case_law
from lex.research import LexResearchService
from lex.research.case_law_completeness import detect_case_law_fragment
from lex.research.case_law_exact_search import parse_case_law_reference
from lex.research.source_scope_policy import classify_source_scope

from .cache import get_retrieval_cache
from .citations import build_citations
from .context_builder import RetrievalContextBuilder
from .dedup import deduplicate_evidence
from .filters import RetrievalFilters
from .legal_research_integrator import (
    merge_public_research_into_evidence,
    run_public_research_for_request,
    should_run_public_research,
)
from .query_planner import QueryPlanner
from .ranker import rank_evidence
from .source_router import SourceRouter
from .sources import row_to_evidence


class RetrievalOrchestrator:
    def __init__(
        self,
        *,
        query_planner=None,
        source_router=None,
        filters=None,
        research_service: LexResearchService | None = None,
        context_builder: RetrievalContextBuilder | None = None,
        retrieval_cache=None,
    ) -> None:
        self.query_planner = query_planner or QueryPlanner()
        self.source_router = source_router or SourceRouter()
        self.filters = filters or RetrievalFilters()
        self.research_service = research_service or LexResearchService()
        self.context_builder = context_builder or RetrievalContextBuilder()
        self.retrieval_cache = retrieval_cache or get_retrieval_cache()

    def _is_official_web_source(self, source) -> bool:
        return source.__class__.__name__ == "OfficialWebSource"

    def _performance_smoke_requested(self, request) -> bool:
        metadata = getattr(request, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return False
        return bool(metadata.get("performance_smoke") or metadata.get("benchmark_mode") == "performance_smoke")

    def _performance_smoke_payload(self, workflow: str) -> dict:
        metadata = {
            "workflow": workflow,
            "performance_smoke": True,
            "retrieval_cache_hit": False,
            "retrieval_cache_ttl_seconds": self.retrieval_cache.ttl_seconds,
            "external_sources_used": False,
            "external_sources_reason": None,
            "fascicolo_first": False,
            "sources_skipped": True,
        }
        evidence_pack = {
            "queries": [],
            "items": [],
            "citations": [],
            "official_sources": [],
            "trusted_sources": [],
            "freshness": {},
            "metadata": metadata,
            "aggregate_trust_score": 0.0,
            "aggregate_freshness_score": 0.0,
            "aggregate_context_fit_score": 0.0,
            "aggregate_consensus_score": 0.0,
            "compared_sources": [],
            "conflicting_items": [],
            "coverage_gaps": [],
            "needs_human_review": False,
            "sufficient": True,
        }
        return {
            "queries": [],
            "items": [],
            "citations": [],
            "evidence_pack": evidence_pack,
            "official_sources": [],
            "trusted_sources": [],
            "retrieval_context": {
                "queries": [],
                "sources": [],
                "official_web_requested": False,
                "performance_smoke": True,
            },
            "source_comparison": [],
            "coverage_gaps": [],
            "conflicting_items": [],
            "fallback_triggered": False,
            "fascicolo_first": False,
            "external_sources_used": False,
            "external_sources_reason": None,
            "evidence_sufficient": True,
            "used_sources": [],
            "cache": {
                "hit": False,
                "ttl_seconds": self.retrieval_cache.ttl_seconds,
            },
        }

    def _search_sources(self, sources, *, queries, request, context):
        results = []
        used = []
        for source in sources:
            try:
                found = list(source.search(queries=queries, request=request, context=context) or [])
            except Exception:
                continue
            if found:
                results.extend(found)
                used.append(source.__class__.__name__)
        return results, used

    def _studio_context_seed_results(self, context, workflow: str):
        studio = dict((context or {}).get("studio") or {})
        rows = list(studio.get("sources") or [])
        if not rows:
            return []

        default_source_type = {
            "economico": "preventivo",
            "cabina": "strumento",
            "next_action": "agenda",
            "fascicolo": "fascicolo",
            "udienza": "agenda",
            "telematico_status": "telematico",
            "compliance": "compliance",
        }.get(workflow, "legal_intelligence")
        default_score = 0.82 if workflow in {"economico", "cabina", "next_action"} else 0.68

        seeded = []
        for row in rows[:6]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or row.get("citation") or "").strip()
            excerpt = str(row.get("text") or row.get("excerpt") or row.get("content") or "").strip()
            if not title and not excerpt:
                continue
            payload = dict(row)
            payload.setdefault("type", default_source_type)
            payload.setdefault("id", str(row.get("id") or title.lower().replace(" ", "-")))
            payload.setdefault("title", title or "Contesto studio")
            payload.setdefault("excerpt", excerpt or title)
            payload.setdefault("score", default_score)
            payload.setdefault("authority", "studio_context")
            payload.setdefault("source_level", 3)
            payload.setdefault("trust_class", "B" if workflow in {"economico", "cabina", "next_action"} else "")
            payload["from_studio_context"] = True
            seeded.append(row_to_evidence(payload, default_source_type))
        return seeded

    def _evidence_is_sufficient(self, results, workflow: str) -> bool:
        if not results:
            return False

        top = list(results[:5])
        official_count = 0
        strong_count = 0
        for item in top:
            trust_class = str(getattr(item, "trust_class", "") or (item.get("trust_class") if isinstance(item, dict) else "")).upper()
            source_level = int(getattr(item, "source_level", 0) or (item.get("source_level") if isinstance(item, dict) else 0) or 0)
            score = float(getattr(item, "score", 0.0) or (item.get("score") if isinstance(item, dict) else 0.0) or 0.0)
            if trust_class in {"A", "B"} or source_level <= 2:
                official_count += 1
            if score >= 0.55:
                strong_count += 1

        # Sentenza specifica: sempre insufficiente senza URL ufficiale + testo completo
        if workflow == "giurisprudenza_specifica":
            return False
        if workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}:
            return official_count >= 1 and strong_count >= 2
        if workflow in {"fascicolo", "udienza", "telematico_status", "documento"}:
            return strong_count >= 2
        return strong_count >= 1

    def _selection_limit(self, workflow: str) -> int:
        if workflow in {"fascicolo", "udienza", "documento", "telematico_status", "compliance"}:
            return 48
        if workflow in {"cabina", "next_action"}:
            return 24
        return 12

    @staticmethod
    def _item_value(item, *keys: str) -> str:
        for key in keys:
            if isinstance(item, dict):
                value = item.get(key)
            else:
                value = getattr(item, key, None)
                if not value:
                    meta = getattr(item, "metadata", None)
                    if isinstance(meta, dict):
                        value = meta.get(key)
            if value:
                return str(value).strip()
        return ""

    def _case_law_fragment_scan(self, items) -> tuple[bool, bool, list[str], object | None]:
        found = False
        complete = False
        missing: list[str] = []
        first_fragment = None
        for item in list(items or []):
            result = detect_case_law_fragment(item)
            if not result.is_case_law:
                continue
            found = True
            complete = complete or result.is_complete
            if first_fragment is None:
                first_fragment = item
            missing.extend(result.missing_parts)
        return found, complete, list(dict.fromkeys(missing)), first_fragment

    def _apply_case_law_exact_metadata(self, payload, request, workflow: str, *, public_search_run: bool, web_blocked_reason: str = ""):
        reference = parse_case_law_reference(str(getattr(request, "query", "") or ""))
        request_metadata = dict(getattr(request, "metadata", {}) or {})
        scope = classify_source_scope(
            str(getattr(request, "query", "") or ""),
            workflow=workflow,
            intent=str(getattr(request, "intent", "") or ""),
            metadata=request_metadata,
        )
        items = list(payload.get("items") or [])
        fragment_found, fragment_complete, fragment_missing, fragment_item = self._case_law_fragment_scan(items)
        exact_check = check_exact_case_law(
            items,
            exact_number=reference.number,
            exact_year=reference.year,
            exact_date=reference.date,
            exact_court=reference.court,
        )
        exact_found = exact_check.match_status == "exact_match"
        has_full_text = bool(exact_check.has_full_text)
        has_dispositivo = bool(getattr(exact_check, "has_dispositivo", False))
        has_motivazione = bool(getattr(exact_check, "has_motivazione", False))
        has_pdf = bool(getattr(exact_check, "has_pdf", False))
        official_url = str(exact_check.official_url or "")
        exact_title = ""
        for item in items:
            item_url = self._item_value(item, "official_url", "url")
            title = self._item_value(item, "title", "citation")
            combined = f"{title} {self._item_value(item, 'content', 'excerpt', 'text')}"
            if official_url and item_url == official_url:
                exact_title = title
                break
            if reference.number and reference.number in combined and (reference.year and reference.year in combined):
                exact_title = title
        missing_parts = list(fragment_missing)
        if not official_url:
            missing_parts.append("URL/PDF ufficiale")
        if not has_full_text:
            missing_parts.append("testo integrale")
        if not has_motivazione:
            missing_parts.append("motivazione")
        if not has_dispositivo:
            missing_parts.append("dispositivo")
        missing_parts = list(dict.fromkeys(missing_parts))

        ep = dict(payload.get("evidence_pack") or {})
        metadata = dict(ep.get("metadata") or {})
        metadata.update(
            {
                "source_scope": scope.scope,
                "source_scope_confidence": scope.confidence,
                "source_scope_reason": scope.reason,
                "exact_reference": bool(reference.is_exact_reference),
                "exact_reference_number": reference.number,
                "exact_reference_date": reference.date,
                "exact_reference_year": reference.year,
                "exact_reference_kind": reference.kind or "sentenza",
                "local_case_law_fragment_found": bool(fragment_found),
                "local_case_law_complete": bool(fragment_complete),
                "local_case_law_missing_parts": missing_parts,
                "public_web_forced": True,
                "complete_public_source": True,
                "official_search_run": bool(public_search_run),
                "exact_match_found": bool(exact_found),
                "possible_match_found": exact_check.match_status == "possible_match",
                "completed_from_web": bool(exact_found and official_url),
                "official_url": official_url,
                "official_title": exact_title,
                "official_court": reference.court or "Corte di Cassazione",
                "official_date": reference.date,
                "official_number": reference.number,
                "has_full_text": has_full_text,
                "has_pdf": has_pdf,
                "has_dispositivo": has_dispositivo,
                "has_motivazione": has_motivazione,
                "confidence_cap": exact_check.confidence_cap,
                "confidence_cap_reason": exact_check.confidence_cap_reason,
                "discarded_unrelated_case_law_count": exact_check.discarded_unrelated_count,
                "web_blocked_reason": web_blocked_reason,
                "local_fragment_summary": self._item_value(fragment_item, "title", "content", "excerpt", "text") if fragment_item else "",
            }
        )
        ep["metadata"] = metadata
        ep["sufficient"] = bool(exact_found and (has_full_text or has_dispositivo or has_motivazione))
        payload["evidence_pack"] = ep
        payload["evidence_sufficient"] = bool(ep["sufficient"])
        if exact_found and exact_title:
            payload["official_sources"] = [exact_title]
        elif not exact_found:
            payload["official_sources"] = []
        return payload

    def collect(self, request, context, workflow: str):
        if self._performance_smoke_requested(request):
            return self._performance_smoke_payload(workflow)

        cache_disabled = bool((getattr(request, "metadata", {}) or {}).get("disable_retrieval_cache"))
        cache_key = self.retrieval_cache.build_key(request, context, workflow)
        if not cache_disabled:
            cached_payload = self.retrieval_cache.get(cache_key)
            if cached_payload is not None:
                evidence_pack = dict(cached_payload.get("evidence_pack") or {})
                metadata = dict(evidence_pack.get("metadata") or {})
                metadata["retrieval_cache_hit"] = True
                metadata["retrieval_cache_ttl_seconds"] = self.retrieval_cache.ttl_seconds
                evidence_pack["metadata"] = metadata
                cached_payload["evidence_pack"] = evidence_pack
                cached_payload["cache"] = {
                    "hit": True,
                    "ttl_seconds": self.retrieval_cache.ttl_seconds,
                }
                return cached_payload

        queries = self.query_planner.plan(request, context, workflow)
        sources = self.source_router.resolve(request, context, workflow)
        studio_seed_results = self._studio_context_seed_results(context, workflow)

        internal_sources = [source for source in sources if not self._is_official_web_source(source)]
        external_sources = [source for source in sources if self._is_official_web_source(source)]

        internal_results, internal_used = self._search_sources(
            internal_sources,
            queries=queries,
            request=request,
            context=context,
        )
        if studio_seed_results:
            internal_results = [*studio_seed_results, *internal_results]
            internal_used = ["StudioContext", *internal_used]
        internal_results = self.filters.apply(internal_results, request, context, workflow)
        internal_results = deduplicate_evidence(internal_results)
        internal_results = rank_evidence(internal_results, request, workflow)
        request_metadata_live = dict(getattr(request, "metadata", {}) or {})
        reference_live = parse_case_law_reference(str(getattr(request, "query", "") or ""))
        fragment_found_live, fragment_complete_live, fragment_missing_live, _ = self._case_law_fragment_scan(internal_results)
        if workflow == "giurisprudenza_specifica" or reference_live.is_exact_reference:
            scope_live = classify_source_scope(
                str(getattr(request, "query", "") or ""),
                workflow="giurisprudenza_specifica",
                intent=str(getattr(request, "intent", "") or ""),
                metadata=request_metadata_live,
            )
            request_metadata_live.update(
                {
                    "source_scope": scope_live.scope,
                    "public_web_forced": True,
                    "complete_public_source": True,
                    "exact_reference": True,
                    "exact_legal_reference": True,
                    "local_case_law_fragment_found": bool(fragment_found_live),
                    "local_case_law_complete": bool(fragment_complete_live),
                    "local_case_law_missing_parts": fragment_missing_live,
                }
            )
            request.metadata = request_metadata_live

        fallback_triggered = False
        results = list(internal_results)
        used_sources = list(internal_used)

        if (
            not self._evidence_is_sufficient(results, workflow)
            and bool(getattr(request, "allow_external_research", True))
            and external_sources
        ):
            fallback_triggered = True
            external_results, external_used = self._search_sources(
                external_sources,
                queries=queries,
                request=request,
                context=context,
            )
            results.extend(external_results)
            used_sources.extend(external_used)

        results = self.filters.apply(results, request, context, workflow)
        results = deduplicate_evidence(results)
        results = rank_evidence(results, request, workflow)

        selected = results[: self._selection_limit(workflow)]
        citations = build_citations(selected)
        evidence_pack_obj = self.research_service.build_evidence_pack(
            request,
            context,
            workflow,
            queries,
            selected,
            citations,
        )
        retrieval_context = self.context_builder.build(request, context, workflow, queries, sources)
        sufficient = bool(getattr(evidence_pack_obj, "sufficient", False))
        evidence_pack = asdict(evidence_pack_obj)
        metadata = dict(evidence_pack.get("metadata") or {})
        metadata["retrieval_cache_hit"] = False
        metadata["retrieval_cache_ttl_seconds"] = self.retrieval_cache.ttl_seconds
        request_metadata = dict(getattr(request, "metadata", {}) or {})
        external_sources_used = bool(
            "OfficialWebSource" in used_sources
            or any(str(getattr(item, "source_type", "")).lower() == "web_ufficiale" for item in selected)
        )
        metadata["fascicolo_first"] = bool(request_metadata.get("fascicolo_first"))
        metadata["external_sources_used"] = external_sources_used
        metadata["external_sources_reason"] = request_metadata.get("external_sources_reason") or None
        evidence_pack["metadata"] = metadata
        payload = {
            "queries": list(evidence_pack_obj.queries or queries),
            "items": selected,
            "citations": list(evidence_pack_obj.citations or citations),
            "evidence_pack": evidence_pack,
            "official_sources": list(evidence_pack_obj.official_sources or []),
            "trusted_sources": list(evidence_pack_obj.trusted_sources or []),
            "retrieval_context": retrieval_context,
            "source_comparison": list(getattr(evidence_pack_obj, "compared_sources", []) or []),
            "coverage_gaps": list(getattr(evidence_pack_obj, "coverage_gaps", []) or []),
            "conflicting_items": list(getattr(evidence_pack_obj, "conflicting_items", []) or []),
            "fallback_triggered": fallback_triggered,
            "fascicolo_first": bool(request_metadata.get("fascicolo_first")),
            "external_sources_used": external_sources_used,
            "external_sources_reason": request_metadata.get("external_sources_reason") or None,
            "evidence_sufficient": sufficient,
            "used_sources": used_sources,
            "cache": {
                "hit": False,
                "ttl_seconds": self.retrieval_cache.ttl_seconds,
            },
        }
        # ------------------------------------------------------------------
        # Integrazione ricerca legale pubblica (Phase 5 — Professional Upgrade)
        # Viene eseguita solo per workflow strict legal quando l'evidenza interna
        # è insufficiente e la richiesta consente fonti esterne.
        # ------------------------------------------------------------------
        exact_reference = bool(request_metadata.get("exact_legal_reference") or request_metadata.get("exact_reference"))
        local_case_law_incomplete = workflow == "giurisprudenza_specifica"
        user_requested_public_source = bool(request_metadata.get("complete_public_source") or request_metadata.get("public_web_forced"))
        public_research_run = False
        web_blocked_reason = ""
        official_exact_already_found = False
        if workflow == "giurisprudenza_specifica" or exact_reference:
            precheck = check_exact_case_law(
                list(payload.get("items") or []),
                exact_number=reference_live.number,
                exact_year=reference_live.year,
                exact_date=reference_live.date,
                exact_court=reference_live.court,
            )
            official_exact_already_found = precheck.match_status == "exact_match"
        if not official_exact_already_found and should_run_public_research(
            workflow,
            sufficient,
            bool(getattr(request, "allow_external_research", True)),
            force=bool(request_metadata.get("public_web_forced") or request_metadata.get("complete_public_source")),
            exact_reference=exact_reference,
            local_case_law_incomplete=local_case_law_incomplete,
            user_requested_public_source=user_requested_public_source,
        ):
            public_research_run = True
            source_mode = str(
                (dict(request_metadata.get("request_profile") or {}).get("source_mode"))
                or request_metadata.get("source_mode")
                or "balanced"
            )
            public_research = run_public_research_for_request(
                request,
                context,
                workflow,
                source_mode=source_mode,
                max_results=6,
            )
            if public_research and not public_research.get("public_research_error"):
                payload = merge_public_research_into_evidence(payload, public_research)
                # Aggiorna evidence_sufficient se le fonti pubbliche lo migliorano
                if workflow != "giurisprudenza_specifica" and list(public_research.get("public_official_sources") or []):
                    payload["evidence_sufficient"] = True
                # Propaga warnings e next_actions public research
                payload.setdefault("_public_research", public_research)
                web_blocked_reason = str(public_research.get("web_blocked_reason") or "")
            elif public_research:
                web_blocked_reason = str(public_research.get("public_research_error") or public_research.get("web_blocked_reason") or "")

        if workflow == "giurisprudenza_specifica" or exact_reference:
            payload = self._apply_case_law_exact_metadata(
                payload,
                request,
                workflow,
                public_search_run=bool(public_research_run or external_sources_used or official_exact_already_found),
                web_blocked_reason=web_blocked_reason,
            )

        if not cache_disabled:
            self.retrieval_cache.set(cache_key, payload)
        return payload
