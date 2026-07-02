"""Rendering del risultato del ciclo autonomo (testo italiano o JSON)."""

from __future__ import annotations

import json

from lex.autonomy.models import LearningCycleResult

_STOP_LABELS = {
    "max_cycles": "raggiunto il numero massimo di cicli",
    "max_queries": "raggiunto il numero massimo di query",
    "max_sources": "raggiunto il numero massimo di fonti",
    "max_runtime": "raggiunto il tempo massimo di esecuzione",
    "no_new_information": "nessuna nuova informazione appresa nell'ultimo ciclo",
}


def render_json(result: LearningCycleResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)


def render_text(result: LearningCycleResult) -> str:
    lines = [
        "=== Ciclo di apprendimento autonomo Lex ===",
        f"Modalità: {result.mode} | Cicli eseguiti: {result.cycles_run}",
        f"Arresto: {_STOP_LABELS.get(result.stop_reason, result.stop_reason)}",
        f"Memoria: {result.memory_dir}",
        "",
        f"Domande di ricerca generate: {result.questions_generated}",
        f"Query eseguite: {result.queries_executed}",
        f"Fonti lette: {result.sources_fetched} | Fonti respinte dalla policy: {result.sources_rejected}",
        f"Nuovi termini: {result.new_terms} | Nuove citazioni: {result.new_citations} | Nuove letture: {result.new_readings}",
        f"Lacune aperte registrate: {result.new_unknown_concepts}",
        f"Proposte di miglioramento in revisione umana: {result.proposals_count}",
    ]
    if result.errors:
        lines.append("")
        lines.append("Errori non bloccanti:")
        lines.extend(f"  - {error}" for error in result.errors[:10])
    lines.append("")
    lines.append("Nota: ogni proposta richiede revisione umana; il ciclo non modifica mai codice o produzione.")
    return "\n".join(lines)


__all__ = ["render_json", "render_text"]
