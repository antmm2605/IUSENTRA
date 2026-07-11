"""Servizio principale del piano del giorno (Lex Oggi).

Orchestrazione deterministica: collettori → normalizzazione → correlazione →
deduplicazione → priorità → assegnazione → pianificazione → snapshot.

Tre modalità separate (requisito prestazionale):
- ``read_plan``: legge SOLO lo snapshot materializzato (2-3 query);
- ``refresh_incremental``: rielabora solo fonti/fascicoli cambiati, con budget;
- ``rebuild_full``: riconciliazione completa (solo scheduler o comando admin).

Il LLM non è mai nel percorso di lettura: la sintesi Lex è cache per
``plan_version`` con fallback deterministico.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .assignment import (
    AssignmentCandidates,
    LawyerResolver,
    resolve_assignment,
)
from .clock import Clock, system_clock
from .collectors import (
    AgendaCollector,
    CasePresidioCollector,
    CollectorContext,
    CollectorResult,
    EconomicSignalCollector,
    PecSignalCollector,
    ScadenzarioCollector,
    build_coverage_report,
)
from .correlation import correlate
from .deduplication import MergedSignalGroup, merge_signals
from .models import (
    DailyPlan,
    DailyWorkItem,
    SourceCoverage,
)
from .priority_engine import decide_priority, rank_sort_key
from .repository import DailyPlanRepository
from .scheduling import fixed_block_from_agenda, plan_day

# fonti economiche/cheap rilette per intero anche nel refresh incrementale
_ALWAYS_FULL_SOURCES = {"agenda", "scadenziario", "economic"}

_SECTOR_BY_SOURCE = {
    "pec": "pec",
    "agenda": "agenda",
    "scadenziario": "scadenze",
    "economic": "economico",
    "deposit": "telematico",
}

_DOMAIN_ACTIONS_BY_KIND = {
    "deadline_fulfill": ("create_task", "create_deadline"),
    "pec_deadline": ("create_task", "create_deadline"),
    "hearing_attend": ("create_task", "create_calendar_proposal"),
    "hearing_link_missing": ("create_task",),
    "pec_review": ("create_task", "create_pec_draft"),
    "payment_review": ("create_task",),
    "invoice_draft_needed": ("create_task",),
    "quote_followup": ("create_task", "create_pec_draft"),
}
_STATUS_ACTIONS = ("accept", "complete", "delegate", "snooze", "reject")


@dataclass
class RunReport:
    mode: str
    target_date: str
    signals_upserted: int = 0
    signals_resolved: int = 0
    items_written: int = 0
    users_planned: int = 0
    warnings: list[str] = field(default_factory=list)
    coverage: list[dict[str, Any]] = field(default_factory=list)
    dirty_consumed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": self.mode,
            "target_date": self.target_date,
            "signals_upserted": self.signals_upserted,
            "signals_resolved": self.signals_resolved,
            "items_written": self.items_written,
            "users_planned": self.users_planned,
            "warnings": list(self.warnings),
            "coverage": list(self.coverage),
            "dirty_consumed": self.dirty_consumed,
        }


class DailyPlanService:
    def __init__(
        self,
        repository: DailyPlanRepository,
        *,
        context_factory: Callable[[set[str] | None], CollectorContext],
        resolver_factory: Callable[[], LawyerResolver],
        fascicoli_lookup_factory: Callable[[], dict[str, dict[str, Any]]] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository
        self.context_factory = context_factory
        self.resolver_factory = resolver_factory
        self.fascicoli_lookup_factory = fascicoli_lookup_factory or (lambda: {})
        self.clock = clock or system_clock()

    # ------------------------------------------------------------- letture

    def read_plan(self, *, user_id: str, target_date: str = "") -> DailyPlan | None:
        """Lettura pura dello snapshot: nessun collettore, nessun ricalcolo."""
        target = target_date or self.clock.today().isoformat()
        snapshot = self.repository.get_snapshot(target, user_id)
        if snapshot is None:
            return None
        items = self.repository.list_items(target, assigned_user_id=user_id)
        coverage = [
            SourceCoverage(
                source_type=str(entry.get("source_type") or key),
                status=str(entry.get("status") or "never"),
                watermark=str(entry.get("watermark") or ""),
                last_success_at=str(entry.get("last_success_at") or ""),
                note=str(entry.get("note") or ""),
            )
            for key, entry in (snapshot.get("coverage") or {}).items()
        ]
        return DailyPlan(
            id=str(snapshot.get("id") or ""),
            tenant_id=self.repository.tenant_id,
            target_date=target,
            user_id=user_id,
            plan_version=str(snapshot.get("plan_version") or ""),
            generated_at=str(snapshot.get("generated_at") or ""),
            generation_mode=str(snapshot.get("generation_mode") or ""),
            freshness=dict(snapshot.get("freshness") or {}),
            coverage=coverage,
            summary=dict(snapshot.get("summary") or {}),
            work_items=[i for i in items if not i.in_backlog],
            fixed_agenda_items=list(snapshot.get("fixed_agenda") or []),
            backlog=[],  # il backlog si legge paginato, mai in blocco
            warnings=[str(w) for w in (snapshot.get("warnings") or [])],
            lex_summary=str(snapshot.get("lex_summary") or ""),
            lex_summary_version=str(snapshot.get("lex_summary_version") or ""),
        )

    # ------------------------------------------------------------ ricostruzioni

    def rebuild_full(self, *, target_date: str = "", actor: str = "scheduler") -> dict[str, Any]:
        return self._run(mode="full", target_date=target_date, dirty=None, actor=actor)

    def refresh_incremental(self, *, target_date: str = "", actor: str = "scheduler") -> dict[str, Any]:
        dirty_rows = self.repository.consume_dirty(limit=200)
        dirty_fascicoli = {
            str(row.get("entity_id") or "")
            for row in dirty_rows
            if str(row.get("entity_type") or "") == "fascicolo"
        }
        report = self._run(
            mode="incremental",
            target_date=target_date,
            dirty=dirty_fascicoli,
            actor=actor,
        )
        report["dirty_consumed"] = len(dirty_rows)
        return report

    def refresh_from_event(
        self, *, entity_type: str, entity_ids: Iterable[str], reason: str = ""
    ) -> int:
        """Registra entità cambiate: verranno rielaborate al prossimo refresh."""
        return self.repository.mark_dirty(entity_type, entity_ids, reason=reason)

    # ------------------------------------------------------------- pipeline

    def _run(
        self,
        *,
        mode: str,
        target_date: str,
        dirty: set[str] | None,
        actor: str,
    ) -> dict[str, Any]:
        target = target_date or self.clock.today().isoformat()
        today = self.clock.today()
        report = RunReport(mode=mode, target_date=target)

        ctx = self.context_factory(dirty)
        ctx.watermarks = self.repository.get_watermarks()

        collectors = [
            ScadenzarioCollector(),
            AgendaCollector(),
            PecSignalCollector(),
            CasePresidioCollector(),
            EconomicSignalCollector(),
        ]
        results: list[CollectorResult] = []
        fixed_agenda: list[dict[str, Any]] = []
        for collector in collectors:
            result = collector.collect(ctx)
            results.append(result)
            fixed_agenda.extend(result.fixed_agenda)
            status = (result.coverage.status if result.coverage else "complete")
            if status == "unavailable":
                self.repository.set_watermark(
                    result.source_type,
                    status="error",
                    error=(result.coverage.note if result.coverage else ""),
                )
            else:
                self.repository.set_watermark(
                    result.source_type, watermark=result.watermark, status="ok"
                )

        # normalizzazione + correlazione + upsert nella proiezione tenant-wide
        collected = [s for r in results for s in r.signals]
        correlated = correlate(collected, clock=self.clock)
        stats = self.repository.upsert_signals(correlated)
        report.signals_upserted = stats["inserted"] + stats["updated"]

        # riconciliazione: i segnali non riemessi da una fonte scandita per
        # intero e senza troncamenti vengono risolti
        for result in results:
            full_scan = mode == "full" or result.source_type in _ALWAYS_FULL_SOURCES
            complete = bool(result.coverage) and result.coverage.status == "complete"
            if full_scan and complete and not result.truncated:
                keep = {s.dedupe_key for s in correlated if s.source_type == result.source_type}
                report.signals_resolved += self.repository.resolve_signals_not_in(
                    result.source_type, keep
                )

        # dalla proiezione condivisa ai piani personali (mai rianalizzare le
        # stesse fonti per ogni avvocato)
        active_signals = self.repository.list_active_signals(limit=5000)
        groups = merge_signals(active_signals)
        resolver = self.resolver_factory()
        fascicoli_lookup = self.fascicoli_lookup_factory()

        drafts: list[tuple[MergedSignalGroup, DailyWorkItem]] = []
        for group in groups:
            item = self._item_from_group(group, resolver, fascicoli_lookup, target, today)
            drafts.append((group, item))

        # ordinamento secondario deterministico → rank totale
        decorated = sorted(
            drafts,
            key=lambda pair: rank_sort_key(
                pair[0], _DecisionShim(pair[1].priority), today=today
            ),
        )
        for rank, (_, item) in enumerate(decorated):
            item.item_rank = rank

        items = [item for _, item in decorated]

        # pianificazione per utente intorno all'agenda (proposta, mai scritture)
        coverage, warnings = build_coverage_report(
            results, watermarks=self.repository.get_watermarks(), clock=self.clock
        )
        report.warnings = list(warnings)
        report.coverage = [c.to_dict() for c in coverage]

        # ogni utente attivo riceve il proprio snapshot, anche vuoto: un piano
        # vuoto con fonti non aggiornate deve dichiararlo, non sparire
        resolver_user_ids = {
            str(u.get("id") or "") for u in getattr(resolver, "users", []) if u.get("id")
        }
        user_ids = sorted(
            {item.assigned_user_id for item in items} | {""} | resolver_user_ids
        )
        all_warnings = list(warnings)
        if not items and any(c.status != "complete" for c in coverage):
            all_warnings.append(
                "Nessuna attività elencata, ma alcune fonti non sono aggiornate: "
                "il piano potrebbe essere incompleto."
            )

        plan_versions: dict[str, str] = {}
        summaries: dict[str, dict[str, Any]] = {}
        schedule_warnings: dict[str, list[str]] = {}
        for user_id in user_ids:
            user_items = [i for i in items if i.assigned_user_id == user_id]
            if user_id:
                user_blocks = [
                    block
                    for entry in fixed_agenda
                    if (block := fixed_block_from_agenda(entry)) is not None
                    and resolver.resolve_label(str(entry.get("avvocato") or "")) in ("", user_id)
                ]
                outcome = plan_day(user_items, user_blocks, target_date=today)
                schedule_warnings[user_id] = outcome.warnings
            else:
                # la coda studio non viene pianificata: resta da assegnare
                schedule_warnings[user_id] = []
            plan_versions[user_id] = _plan_version(user_items)
            summaries[user_id] = _summary_of(user_items, unassigned=[i for i in items if not i.assigned_user_id])

        global_version = _plan_version(items)
        write_stats = self.repository.replace_items_for_date(
            target, items, plan_version=global_version
        )
        report.items_written = write_stats["inserted"] + write_stats["updated"]

        coverage_payload = {c.source_type: c.to_dict() for c in coverage}
        freshness = {
            c.source_type: {
                "last_success_at": c.last_success_at,
                "status": c.status,
            }
            for c in coverage
        }
        generated_at = self.clock.now().isoformat(timespec="seconds")
        for user_id in user_ids:
            user_agenda = [
                entry
                for entry in fixed_agenda
                if not user_id
                or resolver.resolve_label(str(entry.get("avvocato") or "")) in ("", user_id)
            ]
            self.repository.save_snapshot(
                target_date=target,
                user_id=user_id,
                plan_version=plan_versions[user_id],
                generation_mode=mode,
                freshness=freshness,
                coverage=coverage_payload,
                summary=summaries[user_id],
                fixed_agenda=user_agenda,
                warnings=all_warnings + schedule_warnings.get(user_id, []),
            )
        report.users_planned = len(user_ids)
        out = report.to_dict()
        out["generated_at"] = generated_at
        out["actor"] = actor
        out["plan_version"] = global_version
        return out

    # ------------------------------------------------------------- helper

    def _item_from_group(
        self,
        group: MergedSignalGroup,
        resolver: LawyerResolver,
        fascicoli_lookup: dict[str, dict[str, Any]],
        target_date: str,
        today,
    ) -> DailyWorkItem:
        primary = group.primary
        decision = decide_priority(group, today=today)
        fascicolo_meta = fascicoli_lookup.get(primary.fascicolo_id, {})

        referente = str(fascicolo_meta.get("avvocato_referente") or "")
        dominus = str(fascicolo_meta.get("avvocato_dominus") or "")
        agenda_avvocato = ""
        responsible = ""
        pec_taker = ""
        for sig in group.signals:
            meta = sig.metadata or {}
            referente = referente or str(meta.get("fascicolo_referente") or "")
            dominus = dominus or str(meta.get("fascicolo_dominus") or "")
            agenda_avvocato = agenda_avvocato or str(meta.get("agenda_avvocato") or "")
            responsible = responsible or sig.responsible_user_id
            pec_taker = pec_taker or str(meta.get("pec_taker_user_id") or "")
            if sig.source_type == "agenda":
                agenda_avvocato = agenda_avvocato or sig.lawyer_hint

        assignment = resolve_assignment(
            AssignmentCandidates(
                fascicolo_referente=referente,
                agenda_avvocato=agenda_avvocato,
                responsible_user_id=responsible,
                pec_taker_user_id=pec_taker,
                fascicolo_dominus=dominus,
            ),
            resolver,
        )

        sector = str((primary.metadata or {}).get("sector") or "")
        if not sector:
            sector = _SECTOR_BY_SOURCE.get(primary.source_type, "organizzativo")

        needs_review = group.needs_review
        reason = primary.reason or decision.reason
        if group.conflicts:
            reason = f"{reason} Attenzione: {group.conflicts[0]}"

        actions = list(_STATUS_ACTIONS) + list(
            _DOMAIN_ACTIONS_BY_KIND.get(primary.kind, ("create_task",))
        )

        fascicolo_label = str(
            fascicolo_meta.get("numero")
            or (primary.metadata or {}).get("fascicolo_label")
            or ""
        )
        cliente_label = str(fascicolo_meta.get("nome_cliente") or "")

        return DailyWorkItem(
            id="",
            tenant_id=self.repository.tenant_id,
            target_date=target_date,
            title=primary.title,
            action_kind=primary.kind,
            dedupe_key=group.dedupe_key,
            priority=decision.priority,
            assigned_user_id=assignment.user_id,
            assigned_lawyer_label=assignment.lawyer_label,
            sector=sector,
            status="needs_review" if needs_review else "proposed",
            reason=reason,
            priority_reason=decision.reason,
            priority_rule=decision.rule_id,
            fascicolo_id=primary.fascicolo_id,
            fascicolo_label=fascicolo_label,
            cliente_id=primary.cliente_id or str(fascicolo_meta.get("id_cliente") or ""),
            cliente_label=cliente_label,
            due_at=primary.due_at,
            blocking=any(s.blocking for s in group.signals),
            peremptory=any(s.peremptory for s in group.signals),
            confidence=group.confidence,
            review_required=needs_review,
            source_signal_ids=[s.id for s in group.signals],
            evidence=group.evidence,
            available_actions=actions,
            href=primary.href,
        )


@dataclass(frozen=True)
class _DecisionShim:
    priority: str
    rule_id: str = ""
    reason: str = ""


def _plan_version(items: list[DailyWorkItem]) -> str:
    canonical = [
        (
            i.dedupe_key,
            i.priority,
            i.item_rank,
            i.status,
            i.due_at,
            i.assigned_user_id,
            i.in_backlog,
            i.scheduled_start,
        )
        for i in sorted(items, key=lambda x: x.dedupe_key)
    ]
    payload = json.dumps(canonical, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _summary_of(user_items: list[DailyWorkItem], *, unassigned: list[DailyWorkItem]) -> dict[str, Any]:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    backlog = 0
    review = 0
    for item in user_items:
        counts[item.priority] = counts.get(item.priority, 0) + 1
        if item.in_backlog:
            backlog += 1
        if item.review_required:
            review += 1
    return {
        "totale": len(user_items),
        "per_priorita": counts,
        "backlog": backlog,
        "da_rivedere": review,
        "da_assegnare_studio": len(unassigned),
    }


__all__ = ["DailyPlanService", "RunReport"]
