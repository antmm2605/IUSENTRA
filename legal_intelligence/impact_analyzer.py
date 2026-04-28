"""Analisi impatto delle variazioni rilevate."""

from __future__ import annotations

from dataclasses import dataclass

from .sources import LegalSource


KEYWORD_IMPACTS = {
    "pct": "PCT",
    "deposito": "compliance",
    "datiatto": "template_atti",
    "pdf/a": "compliance",
    "firma digitale": "compliance",
    "scadenza": "scadenze",
    "termine": "scadenze",
    "tariffa": "tariffario",
    "compenso": "tariffario",
    "penale": "PDP",
    "tributario": "PTT",
    "amministrativo": "PAT",
}


@dataclass(frozen=True)
class ImpactAnalysis:
    title: str
    summary: str
    impact_areas: list[str]
    apply_mode: str
    severity: str


def analyze_impact(source: LegalSource, normalized_text: str) -> ImpactAnalysis:
    text = (normalized_text or "").lower()
    impacts = list(dict.fromkeys(source.impact_areas))
    for keyword, area in KEYWORD_IMPACTS.items():
        if keyword in text and area not in impacts:
            impacts.append(area)
    severity = "media"
    if any(area in {"PCT", "PAT", "PTT", "PDP", "compliance"} for area in impacts):
        severity = "alta" if source.apply_mode == "manual" else "media"
    title = f"Variazione rilevata su {source.name}"
    summary = (
        "La fonte ufficiale ha restituito un contenuto diverso dall'ultimo snapshot. "
        f"Aree impattate: {', '.join(impacts) or 'da classificare'}. "
        "L'applicazione automatica e' consentita solo per aggiornamenti tecnici sicuri."
    )
    return ImpactAnalysis(
        title=title,
        summary=summary,
        impact_areas=impacts,
        apply_mode=source.apply_mode if source.apply_mode == "auto" else "manual",
        severity=severity,
    )
