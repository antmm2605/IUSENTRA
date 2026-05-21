"""Sintesi operative deterministiche dei run agentici."""

from __future__ import annotations

from typing import Any

from .models import AgentRun
from .serialization import redact_value


def _count_items(value: Any) -> int:
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list):
            return len(items)
        if isinstance(value.get("total"), int):
            return int(value["total"])
    if isinstance(value, list):
        return len(value)
    return 0


def build_run_result(run: AgentRun) -> dict[str, Any]:
    evidence = dict(run.evidence_json or {})
    read_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    priorities: list[dict[str, Any]] = []

    for step in run.plan.steps:
        output = evidence.get(step.step_key, step.output_json)
        row = {
            "step_key": step.step_key,
            "title": step.title,
            "tool_name": step.tool_name,
            "status": step.status,
            "items_count": _count_items(output),
        }
        if step.status in {"blocked", "failed"}:
            row["message"] = step.error_message or "Passaggio non completato."
            blocked_rows.append(row)
            continue
        if not step.mutates_state:
            read_rows.append(row)
            count = row["items_count"]
            if count:
                priorities.append(
                    {
                        "level": "alta" if step.tool_name in {"scadenziario", "telematico"} else "media",
                        "source_step": step.step_key,
                        "title": f"{step.title}: {count} elementi da verificare",
                    }
                )

    proposals = [
        {
            "proposal_id": proposal.id,
            "step_id": proposal.step_id,
            "tool_name": proposal.tool_name,
            "title": proposal.title,
            "risk_level": proposal.risk_level,
            "impact": proposal.impact,
            "status": proposal.status,
        }
        for proposal in run.proposals
    ]
    summary = {
        "workflow_code": run.workflow_code,
        "run_id": run.id,
        "riepilogo_operativo": [
            f"{len(read_rows)} letture governate completate o valutate.",
            f"{len(proposals)} proposte operative in coda approvazione.",
            f"{len(blocked_rows)} passaggi bloccati o non completati.",
        ],
        "letture": read_rows,
        "priorita": priorities,
        "proposte_operabili": proposals,
        "warning": list(run.plan.warnings or []),
        "blocchi": blocked_rows,
        "confidence": run.confidence,
        "risk_level": run.risk_level,
    }
    return redact_value(summary)
