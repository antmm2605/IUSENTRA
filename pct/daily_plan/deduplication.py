"""Deduplicazione deterministica dei segnali operativi.

Lo stesso evento può apparire in PEC, allegato, documento, scadenziario,
agenda, deposito, notifica e presidio: deve diventare UNA sola attività con
più evidenze. La chiave stabile è

    sha256(tenant_id | fascicolo_id | action_kind | evento_canonico | data_scadenza_Rome)

Invarianti:
- mai fondere eventi di fascicoli diversi (il fascicolo è nella chiave);
- mai fondere scadenze diverse dello stesso giorno (l'evento canonico è
  nella chiave);
- tutte le evidenze vengono conservate (cap 10, ordinate per affidabilità);
- la confidence aumenta solo quando fonti INDIPENDENTI concordano;
- i conflitti non vengono nascosti: il gruppo diventa ``needs_review``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from .clock import Clock, system_clock
from .models import OperationalSignal, SignalEvidence

# Affidabilità delle fonti (1 = più affidabile): governa l'ordine delle
# evidenze e lo spareggio del rank.
SOURCE_RELIABILITY = {
    "scadenziario": 1,
    "pec": 2,
    "deposit": 3,
    "case_presidio": 4,
    "agenda": 5,
    "economic": 6,
    "notification": 7,
    "health": 8,
}

MAX_EVIDENCE = 10


def normalize_due_date(value: Any, clock: Clock | None = None) -> str:
    """Data di scadenza normalizzata (solo data, fuso Europe/Rome)."""
    clock = clock or system_clock()
    if isinstance(value, datetime):
        return clock.local_date_of(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = " ".join(str(value or "").split()).strip()
    if not raw:
        return ""
    for sample, fmt in (
        (raw[:19], "%Y-%m-%dT%H:%M:%S"),
        (raw[:16], "%Y-%m-%dT%H:%M"),
        (raw[:10], "%Y-%m-%d"),
        (raw[:10], "%d/%m/%Y"),
    ):
        try:
            parsed = datetime.strptime(sample, fmt)
        except Exception:
            continue
        if fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            return parsed.date().isoformat()
        return clock.local_date_of(parsed).isoformat()
    return ""


def build_dedupe_key(
    tenant_id: str,
    fascicolo_id: str,
    action_kind: str,
    canonical_event: str,
    due_date: str,
) -> str:
    payload = "|".join(
        [
            str(tenant_id or "").strip().lower(),
            str(fascicolo_id or "").strip() or "-",
            str(action_kind or "").strip(),
            str(canonical_event or "").strip(),
            str(due_date or "").strip() or "-",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class MergedSignalGroup:
    """Gruppo di segnali fusi sotto la stessa chiave di deduplicazione."""

    dedupe_key: str
    signals: list[OperationalSignal] = field(default_factory=list)
    evidence: list[SignalEvidence] = field(default_factory=list)
    confidence: float = 0.0
    needs_review: bool = False
    conflicts: list[str] = field(default_factory=list)

    @property
    def primary(self) -> OperationalSignal:
        """Segnale guida: quello della fonte più affidabile."""
        return min(
            self.signals,
            key=lambda s: (SOURCE_RELIABILITY.get(s.source_type, 99), s.id),
        )

    @property
    def source_types(self) -> list[str]:
        return sorted({s.source_type for s in self.signals})

    @property
    def best_reliability(self) -> int:
        return min(SOURCE_RELIABILITY.get(s.source_type, 99) for s in self.signals)


def _combined_confidence(signals: list[OperationalSignal]) -> float:
    """Compone la confidence: prodotto inverso solo tra fonti indipendenti."""
    best_per_source: dict[str, float] = {}
    for sig in signals:
        value = max(0.0, min(float(sig.confidence or 0.0), 1.0))
        best_per_source[sig.source_type] = max(
            best_per_source.get(sig.source_type, 0.0), value
        )
    combined = 1.0
    for value in best_per_source.values():
        combined *= 1.0 - value
    return round(1.0 - combined, 4)


def _detect_conflicts(signals: list[OperationalSignal]) -> list[str]:
    conflicts: list[str] = []
    perentori = {bool(s.peremptory) for s in signals}
    if len(perentori) > 1:
        conflicts.append(
            "Le fonti non concordano sul carattere perentorio del termine."
        )
    responsabili = {s.responsible_user_id for s in signals if s.responsible_user_id}
    if len(responsabili) > 1:
        conflicts.append("Le fonti indicano responsabili diversi per la stessa attività.")
    orari = {s.due_at for s in signals if s.due_at and "T" in s.due_at}
    if len(orari) > 1:
        conflicts.append("Le fonti riportano orari di scadenza diversi nello stesso giorno.")
    return conflicts


def merge_signals(signals: Iterable[OperationalSignal]) -> list[MergedSignalGroup]:
    """Raggruppa i segnali per dedupe_key conservando tutte le evidenze."""
    groups: dict[str, list[OperationalSignal]] = {}
    for sig in signals:
        if not sig.dedupe_key:
            raise ValueError(f"segnale senza dedupe_key: {sig.id or sig.title}")
        groups.setdefault(sig.dedupe_key, []).append(sig)

    merged: list[MergedSignalGroup] = []
    for key in sorted(groups):
        bucket = sorted(
            groups[key],
            key=lambda s: (SOURCE_RELIABILITY.get(s.source_type, 99), s.id),
        )
        evidence: list[SignalEvidence] = []
        seen_refs: set[tuple[str, str]] = set()
        for sig in bucket:
            own = sig.evidence or [
                SignalEvidence(
                    source_type=sig.source_type,
                    source_id=sig.source_id,
                    label=sig.title,
                    timestamp=sig.event_at,
                    href=sig.href,
                    confidence=float(sig.confidence or 0.0),
                )
            ]
            for ev in own:
                ref = (ev.source_type, ev.source_id or ev.label)
                if ref in seen_refs:
                    continue
                seen_refs.add(ref)
                evidence.append(ev)
        evidence = evidence[:MAX_EVIDENCE]

        conflicts = _detect_conflicts(bucket)
        needs_review = bool(conflicts) or any(
            bool((s.metadata or {}).get("needs_review")) for s in bucket
        )
        group = MergedSignalGroup(
            dedupe_key=key,
            signals=bucket,
            evidence=evidence,
            confidence=_combined_confidence(bucket),
            needs_review=needs_review,
            conflicts=conflicts,
        )
        merged.append(group)
    return merged


__all__ = [
    "MAX_EVIDENCE",
    "MergedSignalGroup",
    "SOURCE_RELIABILITY",
    "build_dedupe_key",
    "merge_signals",
    "normalize_due_date",
]
