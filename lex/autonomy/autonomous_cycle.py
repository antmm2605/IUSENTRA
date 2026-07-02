"""Ciclo di apprendimento autonomo governato di Lex.

Sequenza per ciclo: (solo primo ciclo) ingestione campioni → rilevazione lacune
→ domande di ricerca → query ufficiali → discovery → valutazione fiducia →
lettura governata → aggiornamento memoria e grafo → segnali → proposte →
report. Il ciclo PROPONE e IMPARA; non scrive codice, non committa, non
deposita, non pubblica: gli invarianti vivono in `lex.autonomy.safety`.

Stop conditions (la prima che scatta vince): max_cycles, max_queries,
max_sources, max_runtime_seconds (su clock iniettabile), no_new_information
(nessun record nuovo nelle collezioni conoscitive nel ciclo appena concluso).

Determinismo: clock (`now_fn`/`iso_now`) iniettabili, provider ordinati,
dedup per stable_id; due esecuzioni sulla stessa memoria convergono a
`no_new_information`.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from lex.autonomy.discovery import SearchProvider
from lex.autonomy.gap_detector import detect_gaps
from lex.autonomy.improvement_proposer import propose_improvements
from lex.autonomy.models import CycleConfig, LearningCycleResult, ResearchQuestion
from lex.autonomy.query_builder import build_queries
from lex.autonomy.research_planner import plan_research
from lex.autonomy.safety import SourceAccessError, assert_no_autonomous_code_write
from lex.autonomy.source_reader import read_source
from lex.evaluation.learning_metrics import KNOWLEDGE_COLLECTIONS, compute_learning_signals
from lex.knowledge.concept_graph import ConceptGraph, node_id
from lex.knowledge.knowledge_base import KnowledgeBase
from lex.learning.legal_language_analyzer import analyze_language
from lex.learning.models import LegalCitation, LegalSourceSample, LegalTermObservation
from lex.sources.polite_fetcher import PoliteFetcher
from lex.sources.trust import assess_source


def _monotonic() -> float:
    import time

    return time.monotonic()


def _iso_now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AutonomousLearningCycle:
    def __init__(
        self,
        *,
        config: CycleConfig,
        knowledge: KnowledgeBase,
        graph: ConceptGraph,
        search_provider: SearchProvider,
        fetcher: PoliteFetcher | None = None,
        trust_assessor: Callable[..., object] = assess_source,
        now_fn: Callable[[], float] = _monotonic,
        iso_now: Callable[[], str] = _iso_now_utc,
    ) -> None:
        assert_no_autonomous_code_write("autonomous_cycle")
        self.config = config
        self.knowledge = knowledge
        self.graph = graph
        self.search_provider = search_provider
        self.fetcher = fetcher
        self.trust_assessor = trust_assessor
        self._now = now_fn
        self._iso_now = iso_now

    # -- esecuzione ---------------------------------------------------------

    def run(self, samples: list[LegalSourceSample] | None = None) -> LearningCycleResult:
        started_monotonic = self._now()
        started_at = self._iso_now()
        initial_counts = self.knowledge.snapshot_counts()
        result = LearningCycleResult(mode=self.config.mode, started_at=started_at, memory_dir=str(self.knowledge.memory_dir))

        searches_attempted = 0
        searches_failed = 0
        candidates_seen = 0
        readings_ok = 0
        stop_reason = ""

        for cycle_index in range(self.config.max_cycles):
            cycle_before = self.knowledge.snapshot_counts()
            trust_payloads: list[dict] = []
            area_readings: Counter[str] = Counter()

            if cycle_index == 0:
                for sample in samples or []:
                    self._ingest_sample(sample)

            gaps = detect_gaps(self.knowledge, self.graph, min_sources_per_area=self.config.min_sources_per_area)
            for gap in gaps:
                self.knowledge.append("unknown_concepts", gap.stable_id(), gap.to_dict())

            questions = plan_research(gaps, max_questions=self.config.max_questions_per_cycle)
            for question in questions:
                question.query_candidates = build_queries(
                    question,
                    source_mode=self.config.source_mode,
                    max_queries=self.config.max_queries_per_question,
                )
                if self.knowledge.append("research_questions", question.stable_id(), question.to_dict()):
                    result.questions_generated += 1

            for question in questions:
                if stop_reason:
                    break
                for query in question.query_candidates:
                    stop_reason = self._runtime_stop(started_monotonic)
                    if stop_reason:
                        break
                    if result.queries_executed >= self.config.max_queries:
                        stop_reason = "max_queries"
                        break
                    result.queries_executed += 1
                    searches_attempted += 1
                    try:
                        candidates = self.search_provider.search(query, limit=self.config.max_sources)
                    except Exception as exc:
                        searches_failed += 1
                        result.errors.append(f"Ricerca fallita per '{query}': {exc}")
                        continue
                    candidates_seen += len(candidates)
                    for candidate in candidates:
                        stop_reason = self._runtime_stop(started_monotonic)
                        if stop_reason:
                            break
                        if result.sources_fetched >= self.config.max_sources:
                            stop_reason = "max_sources"
                            break
                        assessment = self.trust_assessor(
                            candidate.url,
                            area=question.area or "civile",
                            mode=self.config.source_mode,
                            require_official=self.config.require_official_sources,
                            allowlist=self.config.allowlist,
                            denylist=self.config.denylist,
                        )
                        payload = assessment.to_dict()
                        trust_payloads.append(payload)
                        self.knowledge.append("trust_assessments", assessment.stable_id(), payload)
                        if not payload.get("allowed_for_learning"):
                            result.sources_rejected += 1
                            continue
                        if self.knowledge.append("source_profiles", candidate.stable_id(), candidate.to_dict()) is False:
                            # Fonte già letta in una run precedente: non rileggere.
                            continue
                        result.sources_fetched += 1
                        reading, citations, terms = read_source(
                            candidate,
                            area=question.area or payload.get("area", ""),
                            fetcher=None if self.config.mode == "offline" else self.fetcher,
                            iso_now=self._iso_now(),
                        )
                        self.knowledge.append("source_readings", reading.stable_id(), reading.to_dict())
                        if reading.status == "ok":
                            readings_ok += 1
                            area_readings[reading.area or "n.d."] += 1
                            self._learn_from_reading(question, citations, terms, source_url=candidate.url)
                    if stop_reason:
                        break
                if stop_reason:
                    break

            result.cycles_run = cycle_index + 1
            cycle_after = self.knowledge.snapshot_counts()
            signals = compute_learning_signals(
                cycle_before,
                cycle_after,
                cycle_index=cycle_index,
                trust_payloads=trust_payloads,
                area_readings=dict(area_readings),
            )
            for signal in signals:
                self.knowledge.append("learning_signals", signal.stable_id(), signal.to_dict())
            result.signals.extend(signal.to_dict() for signal in signals)

            proposals = propose_improvements(self.knowledge)
            for proposal in proposals:
                self.knowledge.append("improvement_proposals", proposal.stable_id(), proposal.to_dict())
            result.proposals_count = len(self.knowledge.known_ids("improvement_proposals"))

            self._write_cycle_report(cycle_index, cycle_before, cycle_after, result)

            if stop_reason:
                break
            no_new = all(
                int(cycle_after.get(collection, 0)) == int(cycle_before.get(collection, 0))
                for collection in KNOWLEDGE_COLLECTIONS
            )
            if no_new:
                stop_reason = "no_new_information"
                break
            stop_reason = self._runtime_stop(started_monotonic)
            if stop_reason:
                break

        final_counts = self.knowledge.snapshot_counts()
        result.new_terms = final_counts["legal_terms"] - initial_counts["legal_terms"]
        result.new_citations = final_counts["citations"] - initial_counts["citations"]
        result.new_readings = final_counts["source_readings"] - initial_counts["source_readings"]
        result.new_unknown_concepts = final_counts["unknown_concepts"] - initial_counts["unknown_concepts"]
        result.stop_reason = stop_reason or "max_cycles"
        result.finished_at = self._iso_now()

        if not self.config.dry_run:
            self.graph.save(self.knowledge.memory_dir / "concept_graph.json")

        # Fonti richieste ma mai ottenute: errore di accesso (exit 2 in CLI).
        # Nota: una memoria già convergente (letture presenti da run precedenti)
        # NON è un errore fonti, anche se questa run non ha trovato candidati.
        if searches_attempted and searches_failed == searches_attempted:
            raise SourceAccessError("Tutte le ricerche del provider sono fallite: nessuna fonte raggiungibile.")
        if (
            self.config.require_official_sources
            and result.queries_executed > 0
            and candidates_seen == 0
            and readings_ok == 0
            and final_counts.get("source_readings", 0) == 0
        ):
            raise SourceAccessError(
                "Nessuna fonte ufficiale trovata per le query eseguite: configurare offline_results "
                "o abilitare la modalità web governata."
            )
        return result

    # -- passi interni --------------------------------------------------------

    def _ingest_sample(self, sample: LegalSourceSample) -> None:
        profile = analyze_language(sample.text, sample_id=sample.sample_id, area_hint=sample.area)
        seen_at = self._iso_now()
        for citation in profile.citations:
            self.knowledge.append("citations", citation.stable_id(), {**citation.to_dict(), "area": profile.area})
            self.graph.ensure_node("norma", citation.normalized_text, area=profile.area, seen_at=seen_at)
        for term in profile.terms:
            self.knowledge.append("legal_terms", term.stable_id(), term.to_dict())
            self.graph.ensure_node("concetto", term.normalized, area=term.area, seen_at=seen_at)
        self.knowledge.append(
            "source_profiles",
            sample.stable_id(),
            {**sample.to_dict(), "text": "", "profile": profile.to_dict()},
        )

    def _learn_from_reading(
        self,
        question: ResearchQuestion,
        citations: list[LegalCitation],
        terms: list[LegalTermObservation],
        *,
        source_url: str,
    ) -> None:
        seen_at = self._iso_now()
        domain = source_url.split("/")[2] if source_url.count("/") >= 2 else source_url
        fonte_id = node_id("fonte", domain)
        self.graph.ensure_node("fonte", domain, seen_at=seen_at)
        for citation in citations:
            self.knowledge.append("citations", citation.stable_id(), {**citation.to_dict(), "area": question.area})
            norma_id = node_id("norma", citation.normalized_text)
            self.graph.ensure_node("norma", citation.normalized_text, area=question.area, seen_at=seen_at)
            self.graph.add_edge(fonte_id, norma_id, "letta_per")
            if question.target_term:
                concetto_id = node_id("concetto", question.target_term)
                self.graph.ensure_node("concetto", question.target_term, area=question.area, seen_at=seen_at)
                self.graph.add_edge(concetto_id, norma_id, "correlato_a")
        for term in terms:
            self.knowledge.append("legal_terms", term.stable_id(), term.to_dict())
            self.graph.ensure_node("concetto", term.normalized, area=term.area, seen_at=seen_at)

    def _runtime_stop(self, started_monotonic: float) -> str:
        if (self._now() - started_monotonic) >= self.config.max_runtime_seconds:
            return "max_runtime"
        return ""

    def _write_cycle_report(self, cycle_index: int, before: dict, after: dict, result: LearningCycleResult) -> None:
        if self.config.dry_run:
            return
        report_dir = Path(self.knowledge.memory_dir) / "cycle_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "iusentra.lex_learning.cycle_report.v1",
            "cycle_index": cycle_index,
            "generated_at": self._iso_now(),
            "counts_before": dict(before),
            "counts_after": dict(after),
            "queries_executed": result.queries_executed,
            "sources_fetched": result.sources_fetched,
            "sources_rejected": result.sources_rejected,
            "errors": list(result.errors),
        }
        (report_dir / f"cycle_{cycle_index}.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


def run_autonomous_cycle(
    *,
    config: CycleConfig,
    samples: list[LegalSourceSample] | None = None,
    search_provider: SearchProvider,
    knowledge: KnowledgeBase | None = None,
    graph: ConceptGraph | None = None,
    fetcher: PoliteFetcher | None = None,
    now_fn: Callable[[], float] = _monotonic,
    iso_now: Callable[[], str] = _iso_now_utc,
) -> LearningCycleResult:
    """Esegue il ciclo con memoria/grafo risolti dalla configurazione."""

    kb = knowledge or KnowledgeBase(config.memory_dir or None, read_only=config.dry_run)
    concept_graph = graph or ConceptGraph.load(Path(kb.memory_dir) / "concept_graph.json")
    cycle = AutonomousLearningCycle(
        config=config,
        knowledge=kb,
        graph=concept_graph,
        search_provider=search_provider,
        fetcher=fetcher,
        now_fn=now_fn,
        iso_now=iso_now,
    )
    return cycle.run(samples)


__all__ = ["AutonomousLearningCycle", "run_autonomous_cycle"]
