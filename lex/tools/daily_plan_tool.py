"""Tool Lex in sola lettura sul piano del giorno (Lex Oggi).

Legge ESCLUSIVAMENTE lo snapshot materializzato dal repository Daily Plan:
nessun collettore, nessuna scansione, nessun LLM. Serve alla regia agentica
per proporre attività specifiche (non generiche) con priorità, scadenza,
carattere bloccante/perentorio, affidabilità e copertura delle fonti.
"""

from __future__ import annotations

from typing import Any

from .base import BaseLexTool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _get_service():
    try:
        from web.services.daily_plan_runtime import service_for_current_request

        return service_for_current_request()
    except Exception:
        return None


def _item_row(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "titolo": item.title,
        "priorita": item.priority,
        "stato": item.status,
        "settore": item.sector,
        "tipo_azione": item.action_kind,
        "motivo": item.reason,
        "spiegazione_priorita": item.priority_reason,
        "due_at": item.due_at,
        "blocking": bool(item.blocking),
        "peremptory": bool(item.peremptory),
        "confidence": round(float(item.confidence or 0.0), 2),
        "review_required": bool(item.review_required),
        "fascicolo_id": item.fascicolo_id,
        "fascicolo": item.fascicolo_label,
        "cliente": item.cliente_label,
        "assigned_user": item.assigned_user_id,
        "assigned_label": item.assigned_lawyer_label,
        "fascia_proposta": item.scheduled_start,
        "in_backlog": bool(item.in_backlog),
        "evidenze": len(item.evidence),
        "href": item.href,
    }


class DailyPlanTool(BaseLexTool):
    tool_name = "daily_plan"

    def run(self, **kwargs) -> dict[str, Any]:
        """Legge il piano del giorno materializzato.

        Parametri:
        - date: data del piano (default oggi, Europe/Rome)
        - user_id: piano personale; vuoto = coda studio "Da assegnare"
        - priorita: filtra per priorità (es. "P0")
        - limit: max attività restituite (default 25); il risultato riporta
          returned_count/total_matching/truncated/coverage_complete
        """
        service = _get_service()
        if service is None:
            return {
                "error": "store_unavailable",
                "items": [],
                "total": 0,
                "returned_count": 0,
                "total_matching": 0,
                "truncated": False,
                "coverage_complete": False,
            }

        target_date = _clean(kwargs.get("date")) or service.clock.today().isoformat()
        user_id = _clean(kwargs.get("user_id"))
        priorita = _clean(kwargs.get("priorita")).upper()
        limit = max(int(kwargs.get("limit") or 25), 1)

        plan = service.read_plan(user_id=user_id, target_date=target_date)
        if plan is None:
            return {
                "items": [],
                "total": 0,
                "returned_count": 0,
                "total_matching": 0,
                "truncated": False,
                "coverage_complete": False,
                "stato": "non_generato",
                "date": target_date,
                "warnings": [
                    "Il piano del giorno non è ancora stato generato per questa data."
                ],
            }

        matching = [
            item
            for item in plan.work_items
            if not priorita or item.priority == priorita
        ]
        items = [_item_row(i) for i in matching[:limit]]
        truncated = len(matching) > len(items)
        return {
            "items": items,
            "total": len(items),
            "returned_count": len(items),
            "total_matching": len(matching),
            "truncated": truncated,
            "coverage_complete": plan.coverage_complete and not truncated,
            "coverage": [c.to_dict() for c in plan.coverage],
            "summary": dict(plan.summary),
            "warnings": list(plan.warnings),
            "plan_version": plan.plan_version,
            "date": plan.target_date,
            "stato": "pronto",
        }
