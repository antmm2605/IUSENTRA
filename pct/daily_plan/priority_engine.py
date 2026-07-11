"""Motore deterministico di priorità P0–P3 del piano del giorno.

Tabella di regole valutate dall'alto verso il basso (first-match). I termini
perentori e i blocchi processuali hanno override espliciti e non dipendono
da punteggi numerici. Ogni decisione è spiegabile: la regola scattata e il
motivo in linguaggio operativo restano sull'attività.

Base normativa: le regole non calcolano termini — usano le scadenze già
governate da ``pct.scadenziario`` (c.p.c., D.M. 44/2011 per il telematico).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .deduplication import MergedSignalGroup, SOURCE_RELIABILITY, normalize_due_date

LEGAL_RISK_RANK = {"high": 0, "medium": 1, "low": 2, "": 3, "none": 3}

# Kind che indicano esito negativo di un invio telematico (rifiuto/errore).
REJECTION_KINDS = frozenset({"deposit_outcome_check"})

HEARING_KINDS = frozenset({"hearing_attend"})


@dataclass(frozen=True)
class PriorityDecision:
    priority: str
    rule_id: str
    reason: str


def _due_date_of(group: MergedSignalGroup) -> date | None:
    primary = group.primary
    normalized = normalize_due_date(primary.due_at)
    if not normalized:
        for sig in group.signals:
            normalized = normalize_due_date(sig.due_at)
            if normalized:
                break
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except Exception:
        return None


def _is_peremptory(group: MergedSignalGroup) -> bool:
    return any(s.peremptory for s in group.signals)


def _is_blocking(group: MergedSignalGroup) -> bool:
    return any(s.blocking for s in group.signals)


def _is_rejection(group: MergedSignalGroup) -> bool:
    for sig in group.signals:
        if sig.kind in REJECTION_KINDS:
            esito = str((sig.metadata or {}).get("esito") or "").lower()
            if esito in {"rifiutato", "errore", "mancata_consegna", "ko"}:
                return True
            if sig.blocking:
                return True
    return False


def _is_hearing(group: MergedSignalGroup) -> bool:
    return any(sig.kind in HEARING_KINDS for sig in group.signals)


def _hint(group: MergedSignalGroup) -> str:
    hints = [s.priority_hint for s in group.signals if s.priority_hint in ("P0", "P1", "P2", "P3")]
    if not hints:
        return ""
    return min(hints)  # P0 < P1 < ... in ordine lessicografico


def decide_priority(group: MergedSignalGroup, *, today: date) -> PriorityDecision:
    """Applica la tabella di regole R1–R9 (first-match, spiegabile)."""
    due = _due_date_of(group)
    peremptory = _is_peremptory(group)
    blocking = _is_blocking(group)

    if peremptory and due is not None and due <= today:
        if due < today:
            return PriorityDecision(
                "P0", "R1", "Termine perentorio scaduto e ancora aperto: intervento immediato."
            )
        return PriorityDecision("P0", "R1", "Termine perentorio in scadenza oggi.")

    if _is_rejection(group):
        return PriorityDecision(
            "P0",
            "R2",
            "Invio telematico rifiutato o non consegnato: verificare subito ricevute ed esito.",
        )

    if _is_hearing(group) and due is not None and due <= today:
        return PriorityDecision("P0", "R3", "Udienza fissata oggi.")

    if blocking and due is not None and due <= today:
        return PriorityDecision(
            "P0", "R3", "Attività bloccante con scadenza odierna o già superata."
        )

    if peremptory and due is not None and (due - today).days <= 3:
        return PriorityDecision(
            "P1", "R4", "Termine perentorio entro tre giorni: da completare oggi."
        )

    if due is not None and due <= today:
        return PriorityDecision(
            "P1", "R5", "Scadenza odierna o arretrata ancora aperta."
        )

    if _is_hearing(group) and due is not None and (due - today).days <= 2:
        return PriorityDecision(
            "P1", "R6", "Udienza entro quarantotto ore: preparare oggi."
        )

    if blocking and due is not None and (due - today).days <= 7:
        return PriorityDecision(
            "P1", "R6", "Attività bloccante entro la settimana."
        )

    hint = _hint(group)
    if hint in ("P0", "P1"):
        motivo = group.primary.reason or "Priorità segnalata dal presidio del fascicolo."
        return PriorityDecision(hint, "R8", motivo)

    if due is not None and (due - today).days <= 14:
        return PriorityDecision("P2", "R7", "Scadenza entro quattordici giorni.")

    if hint in ("P2", "P3"):
        motivo = group.primary.reason or "Priorità segnalata dal presidio del fascicolo."
        return PriorityDecision(hint, "R8", motivo)

    return PriorityDecision("P3", "R9", "Attività organizzativa senza scadenza ravvicinata.")


def rank_sort_key(
    group: MergedSignalGroup,
    decision: PriorityDecision,
    *,
    today: date,
    assignee_load: dict[str, int] | None = None,
) -> tuple:
    """Chiave di ordinamento secondario deterministica (ordine totale).

    Considera: urgenza temporale, carattere bloccante, rischio processuale,
    impatto economico, prossimità udienza, affidabilità fonte, completezza
    dati; la dedupe_key finale garantisce stabilità (idempotenza).
    """
    due = _due_date_of(group)
    overdue_days = (today - due).days if due is not None else -9999
    primary = group.primary
    legal_risk = LEGAL_RISK_RANK.get(str(primary.legal_risk or "").lower(), 3)
    economic_impact = 0.0
    for sig in group.signals:
        try:
            economic_impact = max(
                economic_impact, float((sig.metadata or {}).get("importo") or 0.0)
            )
        except Exception:
            continue
    hearing_distance = (due - today).days if (_is_hearing(group) and due) else 9999
    completeness = 1 if (primary.fascicolo_id and primary.due_at) else 0
    load = 0
    if assignee_load:
        load = int(assignee_load.get(primary.responsible_user_id or "", 0))
    return (
        decision.priority,
        -overdue_days,
        0 if _is_blocking(group) else 1,
        legal_risk,
        -economic_impact,
        hearing_distance,
        group.best_reliability,
        -completeness,
        load,
        group.dedupe_key,
    )


__all__ = [
    "LEGAL_RISK_RANK",
    "PriorityDecision",
    "decide_priority",
    "rank_sort_key",
    "SOURCE_RELIABILITY",
]
