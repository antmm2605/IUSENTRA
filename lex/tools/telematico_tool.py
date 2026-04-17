"""Tool Lex per interrogare depositi telematici (PCT / PDP / PAT)."""

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


def _serialize_esito(esito: Any) -> dict[str, Any]:
    if esito is None:
        return {}
    stato = getattr(esito, "stato", None)
    return {
        "id_deposito": getattr(esito, "id_deposito", ""),
        "tipo_atto": getattr(esito, "tipo_atto", ""),
        "stato": getattr(stato, "value", "") if stato is not None else str(stato or ""),
        "data_invio": getattr(esito, "data_invio", ""),
        "data_accettazione_pec": getattr(esito, "data_accettazione_pec", ""),
        "data_esito": getattr(esito, "data_esito", ""),
        "messaggio": getattr(esito, "messaggio", ""),
        "canale": getattr(esito, "canale", "") or getattr(esito, "portale", ""),
    }


class TelematicoTool(BaseLexTool):
    tool_name = "telematico"

    def run(self, **kwargs) -> dict[str, Any]:
        store = _get_fascicoli_store()
        if store is None:
            return {"error": "store_unavailable", "items": []}

        target_id = _clean(kwargs.get("fascicolo_id") or kwargs.get("pratica_id"))
        filtro_stato = _clean(kwargs.get("stato")).upper()
        limit = max(int(kwargs.get("limit") or 10), 1)

        fascicoli_target: list[Any] = []
        if target_id:
            try:
                fasc = store.get(target_id)
                if fasc:
                    fascicoli_target.append(fasc)
            except Exception:
                pass
        else:
            try:
                fascicoli_target = list(store.tutti())
            except Exception:
                try:
                    fascicoli_target = list(store.lista())
                except Exception:
                    fascicoli_target = []

        items: list[dict[str, Any]] = []
        for fasc in fascicoli_target:
            esiti = getattr(fasc, "esiti_deposito", None) or getattr(fasc, "depositi", None) or []
            for esito in list(esiti):
                row = _serialize_esito(esito)
                if not row:
                    continue
                if filtro_stato and filtro_stato not in str(row.get("stato", "")).upper():
                    continue
                row["fascicolo_id"] = getattr(fasc, "id", "")
                row["fascicolo_numero"] = getattr(fasc, "numero", "")
                row["fascicolo_titolo"] = getattr(fasc, "titolo", "")
                items.append(row)
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break

        return {"items": items, "total": len(items), "fascicolo_id": target_id}
