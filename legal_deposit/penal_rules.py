from __future__ import annotations

import re
from dataclasses import dataclass

from .office_rules import resolve_office_rule


@dataclass(slots=True)
class PenalDepositClassification:
    category: str
    channel: str
    requires_local_channel_review: bool = False
    reason: str = ""


def classify_penal_deposit(text: str, *, office_name: str = "") -> PenalDepositClassification:
    normalized = str(text or "").lower()
    normalized = normalized.replace("410 bis", "410-bis").replace("410/bis", "410-bis")

    if re.search(r"\b410\s*-\s*bis\b", normalized):
        return PenalDepositClassification(
            category="reclamo_410_bis_cpp",
            channel="pdp_penale",
            reason="Reclamo ex art. 410-bis c.p.p.: categoria autonoma.",
        )
    if re.search(r"\b666\b", normalized) or "incidente di esecuzione" in normalized:
        return PenalDepositClassification(
            category="incidente_esecuzione_666_ss_cpp",
            channel="pdp_penale",
            requires_local_channel_review=True,
            reason="Incidente di esecuzione ex artt. 666 ss. c.p.p.: verificare prassi locale del canale.",
        )
    if re.search(r"\b299\b", normalized) or "misura cautelare" in normalized or "sequestro" in normalized:
        return PenalDepositClassification(
            category="istanza_misure_cautelari_o_sequestri",
            channel="pdp_penale",
            reason="Istanze cautelari personali/reali e sequestri: canale PDP salvo diversa regola locale.",
        )

    rule = resolve_office_rule(office_name)
    return PenalDepositClassification(
        category="istanza_penale_generica",
        channel=str(rule.get("channel") or "pdp_penale"),
        reason="Istanza penale generica: usare PDP salvo verifica locale o profilo specifico.",
    )


def pdp_ministry_statuses() -> tuple[str, ...]:
    return (
        "INVIATO",
        "IN_TRANSITO",
        "IN_FASE_DI_VERIFICA",
        "ACCOLTO",
        "RIGETTATO",
        "ERRORE_TECNICO",
    )


def normalize_pdp_ministry_status(value: str) -> str:
    text = str(value or "").strip().upper().replace(" ", "_")
    aliases = {
        "IN_VERIFICA": "IN_FASE_DI_VERIFICA",
        "ACCETTATO": "ACCOLTO",
        "RIFIUTATO": "RIGETTATO",
        "ERRORE": "ERRORE_TECNICO",
    }
    return aliases.get(text, text if text in pdp_ministry_statuses() else "")


def legacy_pdp_ministry_status(value: str) -> str:
    """Return a legacy-compatible value for existing PDP tables."""

    aliases = {
        "IN_FASE_DI_VERIFICA": "IN_VERIFICA",
        "ACCOLTO": "ACCETTATO",
        "RIGETTATO": "RIFIUTATO",
    }
    canonical = normalize_pdp_ministry_status(value)
    return aliases.get(canonical, canonical)
