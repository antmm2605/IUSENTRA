"""Conservative scorecard logic for Legal Source Engine sources."""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from .models import SourceScorecard
from .source_contract import LegalSourceContract


def evaluate_scorecard(source: LegalSourceContract) -> SourceScorecard:
    card = deepcopy(source.scorecard)
    recommendation = True
    notes = list(card.notes)

    if not source.citation_policy:
        recommendation = False
        notes.append("Citation policy mancante: non raccomandare abilitazione.")
    if not source.manuscript:
        recommendation = False
        notes.append("Manoscritto mancante: non raccomandare abilitazione.")
    if source.metadata.network_allowed_by_default:
        recommendation = False
        notes.append("Rete abilitata di default: non raccomandare abilitazione.")
    if source.metadata.enabled_by_default:
        recommendation = False
        notes.append("Fonte abilitata di default: non raccomandare abilitazione.")
    if card.implementation_completeness_score < 0.75:
        recommendation = False
        notes.append("Completezza implementativa insufficiente per produzione.")

    card.enabled_recommendation = bool(recommendation)
    card.notes = notes
    return card


def rank_scorecards(scorecards: Iterable[SourceScorecard]) -> list[SourceScorecard]:
    return sorted(
        list(scorecards),
        key=lambda card: (
            card.officiality_score,
            card.citation_quality_score,
            card.identifier_stability_score,
            -card.legal_risk_score,
        ),
        reverse=True,
    )


__all__ = ["evaluate_scorecard", "rank_scorecards"]
