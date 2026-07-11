"""Tool Lex per consultare agenda e appuntamenti."""

from __future__ import annotations

from datetime import date, datetime, timedelta
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
    for sample, fmt in (
        (raw[:19], "%Y-%m-%dT%H:%M:%S"),
        (raw[:16], "%Y-%m-%dT%H:%M"),
        (raw[:10], "%Y-%m-%d"),
        (raw[:10], "%d/%m/%Y"),
    ):
        try:
            return datetime.strptime(sample, fmt).date()
        except Exception:
            continue
    return None


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = _clean(value)
    if not raw:
        return None
    for sample, fmt in (
        (raw[:19], "%Y-%m-%dT%H:%M:%S"),
        (raw[:16], "%Y-%m-%dT%H:%M"),
        (raw[:10], "%Y-%m-%d"),
    ):
        try:
            return datetime.strptime(sample, fmt)
        except Exception:
            continue
    return None


def _serialize(appuntamento: Any) -> dict[str, Any]:
    tipo = getattr(appuntamento, "tipo", None)
    stato = getattr(appuntamento, "stato", None)
    data_raw = getattr(appuntamento, "data_ora", "") or getattr(appuntamento, "data_inizio", "")
    durata = getattr(appuntamento, "durata_minuti", 0) or 0
    try:
        durata = max(int(durata), 0)
    except Exception:
        durata = 0
    data_fine = ""
    inizio_dt = _to_datetime(data_raw)
    if inizio_dt is not None and durata:
        try:
            data_fine = (inizio_dt + timedelta(minutes=durata)).isoformat()
        except Exception:
            data_fine = ""
    reminder = getattr(appuntamento, "reminder_minuti", None)
    try:
        reminder = int(reminder) if reminder is not None else None
    except Exception:
        reminder = None
    return {
        "id": getattr(appuntamento, "id", ""),
        "titolo": getattr(appuntamento, "titolo", ""),
        "tipo": getattr(tipo, "value", "") if tipo is not None else "",
        "data_ora": data_raw,
        "data_inizio": data_raw,
        "data_fine": data_fine,
        "durata_minuti": durata,
        "avvocato": getattr(appuntamento, "avvocato", ""),
        "reminder_minuti": reminder,
        "stato": getattr(stato, "value", "") if stato is not None else "",
        "luogo": getattr(appuntamento, "luogo", ""),
        "procedimento": getattr(appuntamento, "procedimento", ""),
        "id_fascicolo": getattr(appuntamento, "id_fascicolo", "") or "",
        "tribunale": getattr(appuntamento, "tribunale", ""),
        "id_cliente": getattr(appuntamento, "id_cliente", ""),
        "note": getattr(appuntamento, "note", ""),
    }


class AgendaTool(BaseLexTool):
    tool_name = "agenda"

    def run(self, **kwargs) -> dict[str, Any]:
        store = _get_agenda_store()
        if store is None:
            return {
                "error": "store_unavailable",
                "items": [],
                "total": 0,
                "returned_count": 0,
                "total_matching": 0,
                "truncated": False,
                "coverage_complete": False,
            }

        target_fasc = _clean(kwargs.get("fascicolo_id") or kwargs.get("pratica_id"))
        target_cli = _clean(kwargs.get("cliente_id"))
        limit = max(int(kwargs.get("limit") or 10), 1)
        date_from = _to_date(kwargs.get("da") or kwargs.get("from"))
        date_to = _to_date(kwargs.get("a") or kwargs.get("to"))
        giorni_entro = kwargs.get("giorni")
        only_future = bool(kwargs.get("futuri"))
        today = date.today()
        if giorni_entro is not None:
            try:
                days = max(int(giorni_entro), 0)
                date_from = date_from or today
                date_to = date_to or (today + timedelta(days=days))
            except Exception:
                pass

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
            data_val = _to_date(getattr(ap, "data_ora", "") or getattr(ap, "data_inizio", ""))
            if (date_from or date_to or giorni_entro is not None) and data_val is None:
                continue
            if only_future and data_val and data_val < today:
                continue
            if date_from and data_val and data_val < date_from:
                continue
            if date_to and data_val and data_val > date_to:
                continue
            items.append(_serialize(ap))

        items.sort(key=lambda item: (_to_date(item.get("data_ora") or item.get("data_inizio")) or date.max))
        total_matching = len(items)
        items = items[:limit]
        truncated = total_matching > len(items)
        return {
            "items": items,
            "total": len(items),
            "returned_count": len(items),
            "total_matching": total_matching,
            "truncated": truncated,
            "coverage_complete": not truncated,
        }
