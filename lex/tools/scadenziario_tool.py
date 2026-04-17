"""Tool Lex per interrogare lo scadenziario."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .base import BaseLexTool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _get_scadenziario_store():
    try:
        from web.helpers import get_scadenziario

        return get_scadenziario()
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
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[: len(fmt)], fmt).date()
        except Exception:
            continue
    return None


def _serialize(scadenza: Any) -> dict[str, Any]:
    tipo = getattr(scadenza, "tipo", None)
    stato = getattr(scadenza, "stato", None)
    priorita = getattr(scadenza, "priorita", None)
    data_val = _to_date(getattr(scadenza, "data", ""))
    giorni = None
    if data_val is not None:
        try:
            giorni = (data_val - date.today()).days
        except Exception:
            giorni = None
    return {
        "id": getattr(scadenza, "id", ""),
        "titolo": getattr(scadenza, "titolo", ""),
        "data": getattr(scadenza, "data", ""),
        "giorni_al_termine": giorni,
        "tipo": getattr(tipo, "value", "") if tipo is not None else "",
        "stato": getattr(stato, "value", "") if stato is not None else "",
        "priorita": getattr(priorita, "value", "") if priorita is not None else "",
        "id_fascicolo": getattr(scadenza, "id_fascicolo", ""),
        "note": getattr(scadenza, "note", ""),
    }


class ScadenziarioTool(BaseLexTool):
    tool_name = "scadenziario"

    def run(self, **kwargs) -> dict[str, Any]:
        store = _get_scadenziario_store()
        if store is None:
            return {"error": "store_unavailable", "items": []}

        target_fasc = _clean(kwargs.get("fascicolo_id") or kwargs.get("pratica_id"))
        giorni_entro = kwargs.get("giorni")
        only_aperte = bool(kwargs.get("solo_aperte"))
        limit = max(int(kwargs.get("limit") or 15), 1)
        today = date.today()

        try:
            tutte = list(store.tutte())
        except Exception:
            try:
                tutte = list(store.tutti())
            except Exception:
                tutte = []

        items: list[dict[str, Any]] = []
        for sc in tutte:
            if target_fasc and _clean(getattr(sc, "id_fascicolo", "")) != target_fasc:
                continue
            if only_aperte:
                stato_val = str(getattr(getattr(sc, "stato", None), "value", "") or "").lower()
                if stato_val in {"completata", "chiusa", "annullata"}:
                    continue
            if giorni_entro is not None:
                data_val = _to_date(getattr(sc, "data", ""))
                if data_val is None:
                    continue
                try:
                    delta = (data_val - today).days
                    if delta < 0 or delta > int(giorni_entro):
                        continue
                except Exception:
                    continue
            items.append(_serialize(sc))
            if len(items) >= limit:
                break

        items.sort(key=lambda x: (x.get("giorni_al_termine") is None, x.get("giorni_al_termine") or 0))
        return {"items": items, "total": len(items)}
