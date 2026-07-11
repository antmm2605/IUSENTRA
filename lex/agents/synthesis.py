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


def _item_level(item: dict[str, Any]) -> str:
    """Priorità reale dell'attività (mai dal solo numero di elementi)."""
    priority = str(item.get("priorita") or item.get("priority") or "").upper()
    if priority in {"P0", "P1"} or item.get("peremptory") or item.get("blocking"):
        return "alta"
    if priority == "P2":
        return "media"
    return "bassa"


def _structured_priorities(step_key: str, output: Any) -> list[dict[str, Any]]:
    """Priorità dagli item strutturati (priority/due_at/blocking/peremptory).

    Usata quando un tool (es. daily_plan) restituisce attività già valutate
    dal motore deterministico: la sintesi rispetta quella valutazione invece
    di contare gli elementi.
    """
    if not isinstance(output, dict):
        return []
    items = output.get("items")
    if not isinstance(items, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        has_structure = any(
            key in item for key in ("priorita", "priority", "peremptory", "blocking")
        )
        if not has_structure:
            return []
        title = str(item.get("titolo") or item.get("title") or "").strip()
        if not title:
            continue
        row: dict[str, Any] = {
            "level": _item_level(item),
            "source_step": step_key,
            "title": title,
            "priority": str(item.get("priorita") or item.get("priority") or ""),
        }
        if item.get("due_at"):
            row["due_at"] = str(item.get("due_at"))
        if item.get("blocking"):
            row["blocking"] = True
        if item.get("peremptory"):
            row["peremptory"] = True
        if item.get("confidence") is not None:
            row["confidence"] = item.get("confidence")
        if item.get("assigned_user") or item.get("assigned_label"):
            row["assigned_user"] = str(
                item.get("assigned_label") or item.get("assigned_user") or ""
            )
        if item.get("review_required"):
            row["review_required"] = True
        rows.append(row)
    rows.sort(key=lambda r: ({"alta": 0, "media": 1, "bassa": 2}[r["level"]], r.get("due_at") or "9999"))
    return rows[:12]


def _coverage_warnings(output: Any) -> list[str]:
    if not isinstance(output, dict):
        return []
    warnings = [str(w) for w in (output.get("warnings") or []) if str(w).strip()]
    if output.get("coverage_complete") is False:
        warnings.append(
            "Copertura fonti incompleta: il quadro potrebbe non includere tutto."
        )
    if output.get("truncated"):
        warnings.append("Elenco parziale: alcuni elementi non sono stati mostrati.")
    return warnings


def build_run_result(run: AgentRun) -> dict[str, Any]:
    evidence = dict(run.evidence_json or {})
    read_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    priorities: list[dict[str, Any]] = []
    coverage_warnings: list[str] = []

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
            coverage_warnings.extend(_coverage_warnings(output))
            structured = _structured_priorities(step.step_key, output)
            if structured:
                # priorità dai dati reali dell'attività (priority/due/blocking/
                # peremptory), non dal numero di elementi
                priorities.extend(structured)
                continue
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
        "warning": list(run.plan.warnings or []) + list(dict.fromkeys(coverage_warnings)),
        "blocchi": blocked_rows,
        "confidence": run.confidence,
        "risk_level": run.risk_level,
    }
    return redact_value(summary)
