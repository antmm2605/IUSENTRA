"""Tool Lex per consultare agenda e appuntamenti."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .base import BaseLexTool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _get_agenda_store():
    try:
        from web.helpers import get_agenda

        return get_agenda()
    except Exception:
        return None


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = _clean(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[: len(fmt)], fmt).date()
        except Exception:
            continue
    return None


def _serialize(appuntamento: Any) -> dict[str, Any]:
    tipo = getattr(appuntamento, "tipo", None)
    stato = getattr(appuntamento, "stato", None)
    return {
        "id": getattr(appuntamento, "id", ""),
        "titolo": getattr(appuntamento, "titolo", ""),
        "tipo": getattr(tipo, "value", "") if tipo is not None else "",
        "data_ora": getattr(appuntamento, "data_ora", ""),
        "stato": getattr(stato, "value", "") if stato is not None else "",
        "luogo": getattr(appuntamento, "luogo", ""),
        "procedimento": getattr(appuntamento, "procedimento", ""),
        "tribunale": getattr(appuntamento, "tribunale", ""),
        "id_cliente": getattr(appuntamento, "id_cliente", ""),
        "note": getattr(appuntamento, "note", ""),
    }


class AgendaTool(BaseLexTool):
    tool_name = "agenda"

    def run(self, **kwargs) -> dict[str, Any]:
        store = _get_agenda_store()
        if store is None:
            return {"error": "store_unavailable", "items": []}

        target_fasc = _clean(kwargs.get("fascicolo_id") or kwargs.get("pratica_id"))
        target_cli = _clean(kwargs.get("cliente_id"))
        limit = max(int(kwargs.get("limit") or 10), 1)
        date_from = _to_date(kwargs.get("da") or kwargs.get("from"))
        date_to = _to_date(kwargs.get("a") or kwargs.get("to"))
        only_future = bool(kwargs.get("futuri"))
        today = date.today()

        try:
            tutti = list(store.tutti())
        except Exception:
            tutti = []

        items: list[dict[str, Any]] = []
        for ap in tutti:
            if target_fasc and _clean(getattr(ap, "procedimento", "")) != target_fasc:
                continue
            if target_cli and _clean(getattr(ap, "id_cliente", "")) != target_cli:
                continue
            data_val = _to_date(getattr(ap, "data_ora", ""))
            if only_future and data_val and data_val < today:
                continue
            if date_from and data_val and data_val < date_from:
                continue
            if date_to and data_val and data_val > date_to:
                continue
            items.append(_serialize(ap))
            if len(items) >= limit:
                break

        return {"items": items, "total": len(items)}
