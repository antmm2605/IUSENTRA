"""Tool Lex per interrogare dati di fascicolo."""

from __future__ import annotations

from typing import Any

from .base import BaseLexTool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _get_fascicoli_store():
    try:
        from web.helpers import get_fascicoli

        return get_fascicoli()
    except Exception:
        return None


def _serialize(fascicolo: Any) -> dict[str, Any]:
    stato = getattr(fascicolo, "stato", None)
    tipo = getattr(fascicolo, "tipo", None)
    return {
        "id": getattr(fascicolo, "id", ""),
        "numero": getattr(fascicolo, "numero", ""),
        "titolo": getattr(fascicolo, "titolo", ""),
        "cliente": getattr(fascicolo, "nome_cliente", ""),
        "controparte": getattr(fascicolo, "controparte", ""),
        "oggetto": getattr(fascicolo, "oggetto", ""),
        "tribunale": getattr(fascicolo, "tribunale", ""),
        "rg": getattr(fascicolo, "rg", "") or getattr(fascicolo, "numero_rg", ""),
        "stato": getattr(stato, "value", "") if stato is not None else "",
        "tipo": getattr(tipo, "value", "") if tipo is not None else "",
        "data_prossima_udienza": getattr(fascicolo, "data_prossima_udienza", ""),
        "documenti_count": len(list(getattr(fascicolo, "documenti", []) or [])),
        "attivita_count": len(list(getattr(fascicolo, "attivita", []) or [])),
    }


class FascicoloTool(BaseLexTool):
    tool_name = "fascicolo"

    def run(self, **kwargs) -> dict[str, Any]:
        store = _get_fascicoli_store()
        if store is None:
            return {"error": "store_unavailable", "items": []}

        target_id = _clean(kwargs.get("fascicolo_id") or kwargs.get("id") or kwargs.get("pratica_id"))
        if target_id:
            try:
                fascicolo = store.get(target_id)
            except Exception:
                fascicolo = None
            if not fascicolo:
                return {"found": False, "id": target_id, "items": []}
            return {"found": True, "fascicolo": _serialize(fascicolo), "items": [_serialize(fascicolo)]}

        query = _clean(kwargs.get("q") or kwargs.get("query")).lower()
        limit = max(int(kwargs.get("limit") or 10), 1)
        try:
            tutti = list(store.tutti())
        except Exception:
            try:
                tutti = list(store.lista())
            except Exception:
                tutti = []

        items: list[dict[str, Any]] = []
        for fasc in tutti:
            if query:
                hay = " ".join(
                    str(getattr(fasc, attr, "") or "")
                    for attr in ("numero", "titolo", "nome_cliente", "controparte", "oggetto")
                ).lower()
                if query not in hay:
                    continue
            items.append(_serialize(fasc))
            if len(items) >= limit:
                break

        return {"items": items, "total": len(items), "query": query}
