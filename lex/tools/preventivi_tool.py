"""Tool Lex per interrogare preventivi e conferimenti di incarico.

Legge i dati reali di ``pct.preventivi.GestionePreventivi`` in sola
lettura (nessuna scrittura, nessuna emissione): serve al presidio
economico del piano del giorno e alle risposte operative di Lex.
"""

from __future__ import annotations

from typing import Any

from .base import BaseLexTool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _enum_val(obj: Any) -> str:
    return getattr(obj, "value", "") if obj is not None else ""


def _get_preventivi_store():
    try:
        from web.helpers import get_preventivi_readonly

        return get_preventivi_readonly()
    except Exception:
        return None


def _totale(preventivo: Any) -> float:
    try:
        return round(float(getattr(preventivo, "totale", 0.0) or 0.0), 2)
    except Exception:
        return 0.0


def _ser_preventivo(p: Any) -> dict[str, Any]:
    return {
        "id": getattr(p, "id", ""),
        "numero": getattr(p, "numero", ""),
        "id_cliente": getattr(p, "id_cliente", ""),
        "id_fascicolo": getattr(p, "id_fascicolo", "") or "",
        "data_emissione": getattr(p, "data_emissione", ""),
        "data_scadenza": getattr(p, "data_scadenza", "") or "",
        "oggetto": getattr(p, "oggetto", ""),
        "stato": _enum_val(getattr(p, "stato", None)),
        "totale": _totale(p),
        "versione": getattr(p, "versione", 1),
        "inviato_cliente_il": getattr(p, "inviato_cliente_il", "") or "",
        "accettato_il": getattr(p, "accettato_il", "") or "",
    }


def _ser_conferimento(c: Any) -> dict[str, Any]:
    return {
        "id": getattr(c, "id", ""),
        "numero": getattr(c, "numero", ""),
        "id_preventivo": getattr(c, "id_preventivo", "") or "",
        "id_cliente": getattr(c, "id_cliente", ""),
        "id_fascicolo": getattr(c, "id_fascicolo", "") or "",
        "data_incarico": getattr(c, "data_incarico", ""),
        "oggetto": getattr(c, "oggetto", ""),
        "stato": _enum_val(getattr(c, "stato", None)),
        "firma_cliente_richiesta": bool(getattr(c, "firma_cliente_richiesta", False)),
        "firma_cliente_eseguita": bool(getattr(c, "firma_cliente_eseguita", False)),
    }


class PreventiviTool(BaseLexTool):
    tool_name = "preventivi"

    def run(self, **kwargs) -> dict[str, Any]:
        """Interroga preventivi e conferimenti di incarico (sola lettura).

        Parametri:
        - cliente_id: filtra per cliente
        - fascicolo_id / pratica_id: filtra per fascicolo
        - stato: filtra per stato preventivo (es. "BOZZA", "INVIATO", "ACCETTATO")
        - include_conferimenti: include i conferimenti di incarico (default True)
        - limit: max elementi per lista (default 15); il risultato riporta
          returned_count/total_matching/truncated/coverage_complete
        """
        store = _get_preventivi_store()
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

        cliente_id = _clean(kwargs.get("cliente_id"))
        fascicolo_id = _clean(kwargs.get("fascicolo_id") or kwargs.get("pratica_id"))
        stato_filtro = _clean(kwargs.get("stato")).upper()
        include_conferimenti = kwargs.get("include_conferimenti")
        include_conferimenti = True if include_conferimenti is None else bool(include_conferimenti)
        limit = max(int(kwargs.get("limit") or 15), 1)

        try:
            preventivi = list(store.tutti_preventivi())
        except Exception:
            preventivi = []

        matching: list[dict[str, Any]] = []
        for p in preventivi:
            if cliente_id and _clean(getattr(p, "id_cliente", "")) != cliente_id:
                continue
            if fascicolo_id and _clean(getattr(p, "id_fascicolo", "")) != fascicolo_id:
                continue
            if stato_filtro and _enum_val(getattr(p, "stato", None)).upper() != stato_filtro:
                continue
            matching.append(_ser_preventivo(p))

        items = matching[:limit]
        truncated = len(matching) > len(items)
        out: dict[str, Any] = {
            "items": items,
            "total": len(items),
            "returned_count": len(items),
            "total_matching": len(matching),
            "truncated": truncated,
            "coverage_complete": not truncated,
        }

        if include_conferimenti:
            try:
                conferimenti = list(store.tutti_conferimenti())
            except Exception:
                conferimenti = []
            conf_matching: list[dict[str, Any]] = []
            for c in conferimenti:
                if cliente_id and _clean(getattr(c, "id_cliente", "")) != cliente_id:
                    continue
                if fascicolo_id and _clean(getattr(c, "id_fascicolo", "")) != fascicolo_id:
                    continue
                conf_matching.append(_ser_conferimento(c))
            out["conferimenti"] = conf_matching[:limit]
            out["conferimenti_total_matching"] = len(conf_matching)
            out["conferimenti_truncated"] = len(conf_matching) > limit

        return out
