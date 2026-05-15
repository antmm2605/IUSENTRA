"""Contratti di output per le skill integrate."""

from __future__ import annotations

from typing import Any


DEFAULT_OUTPUT_SCHEMA: dict[str, Any] = {
    "sections": ["Sintesi", "Punti di attenzione", "Prossime verifiche", "Fonti"],
    "requires_reviewer_note": True,
    "requires_citations": True,
}


SKILL_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "contract_review": {
        "sections": ["Sintesi contratto", "Rischi", "Clausole da negoziare", "Azioni consigliate", "Fonti"],
        "finding_columns": ["tema", "rischio", "azione", "fonte"],
    },
    "renewal_watch": {
        "sections": ["Scadenze", "Rinnovi", "Disdette", "Azioni", "Fonti"],
        "finding_columns": ["data", "evento", "rischio", "azione"],
    },
    "dpia_triage": {
        "sections": ["Trattamento", "Soglie DPIA", "Rischi privacy", "Misure", "Fonti"],
        "finding_columns": ["criterio", "stato", "azione", "fonte"],
    },
    "dpa_review": {
        "sections": ["Ruoli privacy", "Clausole DPA", "Gap", "Azioni", "Fonti"],
        "finding_columns": ["clausola", "gap", "azione", "fonte"],
    },
    "chronology_builder": {
        "sections": ["Cronologia", "Prove", "Lacune", "Prossime verifiche", "Fonti"],
        "finding_columns": ["data", "evento", "supporto", "nota"],
    },
    "hearing_prep": {
        "sections": ["Punti udienza", "Domande", "Documenti", "Rischi", "Fonti"],
        "finding_columns": ["tema", "preparazione", "azione", "fonte"],
    },
    "regulatory_monitor": {
        "sections": ["Novita", "Impatto", "Azioni studio", "Fonti"],
        "finding_columns": ["fonte", "impatto", "azione", "stato"],
    },
    "policy_gap_check": {
        "sections": ["Policy", "Gap", "Rischio", "Azioni", "Fonti"],
        "finding_columns": ["tema", "stato", "azione", "fonte"],
    },
}


def contract_for_skill(skill_id: str) -> dict[str, Any]:
    schema = dict(DEFAULT_OUTPUT_SCHEMA)
    schema.update(SKILL_OUTPUT_SCHEMAS.get(skill_id, {}))
    return schema


def normalize_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("reviewer_note", {})
    payload.setdefault("citations", [])
    payload.setdefault("findings", [])
    payload.setdefault("needs_review", True)
    return payload


__all__ = ["DEFAULT_OUTPUT_SCHEMA", "SKILL_OUTPUT_SCHEMAS", "contract_for_skill", "normalize_result_payload"]
