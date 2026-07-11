"""Copertura e salute delle fonti del piano del giorno.

Un piano vuoto con fonti non aggiornate NON deve essere descritto come
"nessuna attività": questo modulo trasforma gli esiti dei collettori e i
watermark persistiti in un report di copertura con avvisi espliciti.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from ..clock import Clock, system_clock
from ..models import SourceCoverage
from .base import CollectorResult

# oltre questa età il dato di una fonte è considerato "stale"
STALE_AFTER_MINUTES = {
    "pec": 240,
    "agenda": 1440,
    "scadenziario": 1440,
    "case_presidio": 1440,
    "economic": 2880,
}

_SOURCE_LABELS = {
    "pec": "Presidio PEC",
    "agenda": "Agenda",
    "scadenziario": "Scadenziario",
    "case_presidio": "Presidio fascicoli",
    "economic": "Presidio economico",
}


def _parse_ts(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:19])
    except Exception:
        return None


def build_coverage_report(
    results: Iterable[CollectorResult],
    *,
    watermarks: dict[str, dict[str, Any]] | None = None,
    clock: Clock | None = None,
) -> tuple[list[SourceCoverage], list[str]]:
    """(coverage per fonte, warning leggibili per l'avvocato)."""
    clock = clock or system_clock()
    now = clock.local_naive_now()
    watermarks = watermarks or {}
    coverage: list[SourceCoverage] = []
    warnings: list[str] = []

    for result in results:
        entry = result.coverage or SourceCoverage(
            source_type=result.source_type, status="complete"
        )
        # una fonte "completa" ma con ultimo successo troppo vecchio è stale
        mark = watermarks.get(result.source_type) or {}
        last_success = _parse_ts(str(mark.get("last_success_at") or ""))
        stale_after = STALE_AFTER_MINUTES.get(result.source_type)
        if (
            entry.status == "complete"
            and stale_after is not None
            and last_success is not None
            and now - last_success > timedelta(minutes=stale_after)
        ):
            entry = SourceCoverage(
                source_type=entry.source_type,
                status="stale",
                watermark=entry.watermark,
                last_success_at=str(mark.get("last_success_at") or ""),
                note="Dati non aggiornati di recente.",
            )
        if not entry.last_success_at:
            entry.last_success_at = str(mark.get("last_success_at") or "")

        coverage.append(entry)
        label = _SOURCE_LABELS.get(entry.source_type, entry.source_type)
        if entry.status == "unavailable":
            warnings.append(
                f"{label}: fonte non disponibile — il piano è incompleto, "
                "non significa che non ci siano attività."
            )
        elif entry.status == "stale":
            nota = f" ({entry.note})" if entry.note else ""
            warnings.append(f"{label}: dati non aggiornati{nota}.")

    return coverage, warnings


__all__ = ["STALE_AFTER_MINUTES", "build_coverage_report"]
