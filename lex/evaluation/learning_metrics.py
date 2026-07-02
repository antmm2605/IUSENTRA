"""Metriche di valutazione del ciclo di apprendimento autonomo di Lex.

Confronta lo stato della memoria prima/dopo un ciclo e produce `LearningSignal`
deterministici: quantità apprese, rapporto fonti ufficiali (pesato con
`SOURCE_WEIGHTS` del Source Policy System), concetti ignoti aperti e il flag
`no_new_information` che guida la condizione di stop del ciclo.

Importa solo `lex.learning.models` (direzione import: evaluation ← autonomy).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lex.learning.models import LearningSignal

# Collezioni "conoscitive": se nessuna cresce, il ciclo non ha imparato nulla.
KNOWLEDGE_COLLECTIONS: tuple[str, ...] = (
    "legal_terms",
    "citations",
    "source_readings",
    "research_questions",
    "unknown_concepts",
)


def official_source_ratio(trust_payloads: list[Mapping[str, Any]]) -> float:
    """Rapporto pesato di ufficialità delle fonti valutate (0..1)."""

    # Import pigro dei pesi governati (tier_1=1.0, tier_2=0.72, tier_3=0.32...).
    from lex.research.source_policy.catalog import SOURCE_WEIGHTS

    if not trust_payloads:
        return 0.0
    total = sum(float(SOURCE_WEIGHTS.get(str(item.get("tier") or "unknown"), 0.0)) for item in trust_payloads)
    return round(total / len(trust_payloads), 4)


def compute_learning_signals(
    before: Mapping[str, int],
    after: Mapping[str, int],
    *,
    cycle_index: int,
    trust_payloads: list[Mapping[str, Any]] | None = None,
    area_readings: Mapping[str, int] | None = None,
) -> list[LearningSignal]:
    """Segnali del ciclo: delta per collezione, ufficialità, no_new_information."""

    signals: list[LearningSignal] = []
    new_by_collection: dict[str, int] = {}
    for collection in KNOWLEDGE_COLLECTIONS:
        delta = max(0, int(after.get(collection, 0)) - int(before.get(collection, 0)))
        new_by_collection[collection] = delta
        signals.append(
            LearningSignal(
                name=f"nuovi_{collection}",
                value=float(delta),
                cycle_index=cycle_index,
                unit="record",
                direction="up_good",
            )
        )
    signals.append(
        LearningSignal(
            name="unknown_concepts_aperti",
            value=float(int(after.get("unknown_concepts", 0))),
            cycle_index=cycle_index,
            unit="record",
            direction="down_good",
        )
    )
    if trust_payloads is not None:
        signals.append(
            LearningSignal(
                name="official_source_ratio",
                value=official_source_ratio(trust_payloads),
                cycle_index=cycle_index,
                unit="ratio",
                direction="up_good",
                details={"fonti_valutate": len(trust_payloads)},
            )
        )
    for area, count in sorted((area_readings or {}).items()):
        signals.append(
            LearningSignal(
                name=f"coverage_area_{area}",
                value=float(count),
                cycle_index=cycle_index,
                unit="letture",
                direction="up_good",
            )
        )
    no_new = all(delta == 0 for delta in new_by_collection.values())
    signals.append(
        LearningSignal(
            name="no_new_information",
            value=1.0 if no_new else 0.0,
            cycle_index=cycle_index,
            unit="flag",
            direction="down_good",
            details=dict(new_by_collection),
        )
    )
    return signals


__all__ = ["KNOWLEDGE_COLLECTIONS", "compute_learning_signals", "official_source_ratio"]
