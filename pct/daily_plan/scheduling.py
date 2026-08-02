"""Pianificazione della giornata intorno agli impegni fissi dell'agenda.

Produce SOLO una proposta di fasce orarie (``scheduled_start`` sugli item):
non modifica mai l'agenda. Regole:

- fuso Europe/Rome, finestra lavorativa 08:30–19:00;
- gli appuntamenti e le udienze esistenti sono blocchi fissi;
- prima delle udienze viene riservato tempo di preparazione;
- P0 viene inserito per primo e non finisce mai nel backlog;
- P1 viene inserito dopo i P0 (entro giornata anche oltre il budget, con
  avviso);
- il piano occupa al massimo ~75% del tempo libero: serve capacità per PEC
  nuove e imprevisti;
- P2 e P3 eccedenti vanno nel backlog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from pct.formatting import parse_datetime_rome

from .clock import ROME_TZ
from .models import DailyWorkItem

WORK_START = (8, 30)
WORK_END = (19, 0)
CAPACITY_RATIO = 0.75
HEARING_PREP_MINUTES = 30
TRAVEL_BUFFER_MINUTES = 20

# Stima di impegno per tipo di attività (minuti).
DEFAULT_EFFORT_MINUTES: dict[str, int] = {
    "pec_review": 15,
    "pec_deadline": 20,
    "deadline_fulfill": 45,
    "hearing_prepare": 45,
    "document_review": 30,
    "relata_completion": 25,
    "deposit_outcome_check": 20,
    "economic_entry": 15,
    "invoice_draft_needed": 20,
    "quote_followup": 15,
    "payment_review": 15,
    "duplicate_reconciliation": 15,
}
FALLBACK_EFFORT_MINUTES = 20


@dataclass(frozen=True)
class FixedBlock:
    """Impegno fisso della giornata (udienza o appuntamento agenda)."""

    start: datetime
    minutes: int
    kind: str = "appuntamento"  # udienza|appuntamento
    label: str = ""
    luogo: str = ""

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=max(int(self.minutes), 15))


@dataclass
class DayScheduleResult:
    scheduled: list[DailyWorkItem] = field(default_factory=list)
    backlog: list[DailyWorkItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    free_minutes: int = 0
    used_minutes: int = 0
    budget_minutes: int = 0


def effort_minutes_for(item: DailyWorkItem) -> int:
    if item.estimated_minutes:
        return max(int(item.estimated_minutes), 5)
    return DEFAULT_EFFORT_MINUTES.get(item.action_kind, FALLBACK_EFFORT_MINUTES)


def _day_window(target_date: date) -> tuple[datetime, datetime]:
    start = datetime(
        target_date.year, target_date.month, target_date.day, *WORK_START, tzinfo=ROME_TZ
    )
    end = datetime(
        target_date.year, target_date.month, target_date.day, *WORK_END, tzinfo=ROME_TZ
    )
    return start, end


def _blocked_intervals(
    blocks: list[FixedBlock], window: tuple[datetime, datetime]
) -> list[tuple[datetime, datetime]]:
    """Intervalli occupati (con preparazione udienza e margini spostamento)."""
    intervals: list[tuple[datetime, datetime]] = []
    for block in blocks:
        start = block.start
        end = block.end
        if block.kind == "udienza":
            start = start - timedelta(minutes=HEARING_PREP_MINUTES)
        if block.luogo:
            start = start - timedelta(minutes=TRAVEL_BUFFER_MINUTES)
            end = end + timedelta(minutes=TRAVEL_BUFFER_MINUTES)
        start = max(start, window[0])
        end = min(end, window[1])
        if start < end:
            intervals.append((start, end))
    intervals.sort()
    merged: list[tuple[datetime, datetime]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _free_slots(
    blocks: list[FixedBlock], window: tuple[datetime, datetime]
) -> list[tuple[datetime, datetime]]:
    busy = _blocked_intervals(blocks, window)
    slots: list[tuple[datetime, datetime]] = []
    cursor = window[0]
    for start, end in busy:
        if cursor < start:
            slots.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < window[1]:
        slots.append((cursor, window[1]))
    return slots


def plan_day(
    items: list[DailyWorkItem],
    fixed_blocks: list[FixedBlock],
    *,
    target_date: date,
    capacity_ratio: float = CAPACITY_RATIO,
) -> DayScheduleResult:
    """Assegna fasce orarie proposte agli item già ordinati per priorità/rank."""
    window = _day_window(target_date)
    slots = _free_slots(fixed_blocks, window)
    free_minutes = sum(int((end - start).total_seconds() // 60) for start, end in slots)
    budget = int(free_minutes * max(min(capacity_ratio, 1.0), 0.1))

    result = DayScheduleResult(
        free_minutes=free_minutes, budget_minutes=budget
    )
    cursors = [start for start, _ in slots]
    used = 0

    ordered = sorted(items, key=lambda i: (i.priority, i.item_rank, i.dedupe_key))
    for item in ordered:
        needed = effort_minutes_for(item)
        must_schedule = item.priority in ("P0", "P1")
        within_budget = (used + needed) <= budget
        if not must_schedule and not within_budget:
            item.in_backlog = True
            item.scheduled_start = ""
            result.backlog.append(item)
            continue

        placed = False
        for idx, (slot_start, slot_end) in enumerate(slots):
            cursor = max(cursors[idx], slot_start)
            if cursor + timedelta(minutes=needed) <= slot_end:
                item.scheduled_start = cursor.isoformat(timespec="minutes")
                item.estimated_minutes = needed
                item.in_backlog = False
                cursors[idx] = cursor + timedelta(minutes=needed)
                used += needed
                result.scheduled.append(item)
                placed = True
                break

        if placed:
            if not within_budget and item.priority == "P0":
                result.warnings.append(
                    "La giornata supera la capacità consigliata: le urgenze P0 sono "
                    "state comunque pianificate."
                )
            continue

        if must_schedule:
            # Nessuna fascia libera sufficiente: l'urgenza resta nel piano
            # senza orario proposto, con avviso esplicito.
            item.scheduled_start = ""
            item.estimated_minutes = needed
            item.in_backlog = False
            result.scheduled.append(item)
            result.warnings.append(
                f"Nessuna fascia libera sufficiente per «{item.title}»: da incastrare "
                "manualmente o delegare."
            )
            used += needed
        else:
            item.in_backlog = True
            item.scheduled_start = ""
            result.backlog.append(item)

    result.used_minutes = used
    return result


def fixed_block_from_agenda(entry: dict[str, Any]) -> FixedBlock | None:
    """Converte un appuntamento serializzato dell'agenda in blocco fisso."""
    raw = str(entry.get("data_ora") or entry.get("data_inizio") or "").strip()
    if not raw:
        return None
    start = parse_datetime_rome(raw)
    if start is None:
        return None
    tipo = str(entry.get("tipo") or "").upper()
    kind = "udienza" if "UDIENZA" in tipo else "appuntamento"
    minutes = int(entry.get("durata_minuti") or 0) or 60
    return FixedBlock(
        start=start,
        minutes=minutes,
        kind=kind,
        label=str(entry.get("titolo") or ""),
        luogo=str(entry.get("luogo") or ""),
    )


__all__ = [
    "CAPACITY_RATIO",
    "DEFAULT_EFFORT_MINUTES",
    "DayScheduleResult",
    "FixedBlock",
    "HEARING_PREP_MINUTES",
    "effort_minutes_for",
    "fixed_block_from_agenda",
    "plan_day",
]
