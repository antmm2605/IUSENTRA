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


def _serialize(scadenza: Any) -> dict[str, Any]:
    tipo = getattr(scadenza, "tipo", None)
    stato = getattr(scadenza, "stato", None)
    priorita = getattr(scadenza, "priorita", None)
    data_raw = getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "data", "")
    data_val = _to_date(data_raw)
    giorni = None
    if data_val is not None:
        try:
            giorni = (data_val - date.today()).days
        except Exception:
            giorni = None
    return {
        "id": getattr(scadenza, "id", ""),
        "titolo": getattr(scadenza, "titolo", ""),
        "data": data_raw,
        "data_scadenza": data_raw,
        "giorni_al_termine": giorni,
        "tipo": getattr(tipo, "value", "") if tipo is not None else "",
        "stato": getattr(stato, "value", "") if stato is not None else "",
        "priorita": getattr(priorita, "value", "") if priorita is not None else "",
        "id_fascicolo": getattr(scadenza, "id_fascicolo", ""),
        "perentorio": bool(getattr(scadenza, "perentorio", False)),
        "id_utente_responsabile": getattr(scadenza, "id_utente_responsabile", ""),
        "note": getattr(scadenza, "note", ""),
    }


class ScadenziarioTool(BaseLexTool):
    tool_name = "scadenziario"

    def run(self, **kwargs) -> dict[str, Any]:
        """Interroga lo scadenziario.

        Parametri:
        - fascicolo_id / pratica_id: filtra per fascicolo
        - giorni: finestra futura in giorni (le scadenze già scadute ma ancora
          aperte restano incluse, salvo ``include_scadute=False``)
        - solo_aperte: esclude completate/chiuse/annullate
        - include_scadute: default True — non eliminare i termini arretrati
        - limit: max elementi restituiti (default 15); il risultato riporta
          sempre returned_count/total_matching/truncated/coverage_complete
        """
        store = _get_scadenziario_store()
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
        giorni_entro = kwargs.get("giorni")
        only_aperte = bool(kwargs.get("solo_aperte"))
        include_scadute = kwargs.get("include_scadute")
        include_scadute = True if include_scadute is None else bool(include_scadute)
        limit = max(int(kwargs.get("limit") or 15), 1)
        today = date.today()

        try:
            tutte = list(store.tutte())
        except Exception:
            try:
                tutte = list(store.tutti())
            except Exception:
                tutte = []

        matching: list[dict[str, Any]] = []
        for sc in tutte:
            if target_fasc and _clean(getattr(sc, "id_fascicolo", "")) != target_fasc:
                continue
            if only_aperte:
                stato_val = str(getattr(getattr(sc, "stato", None), "value", "") or "").lower()
                if stato_val in {"completata", "chiusa", "annullata"}:
                    continue
            if giorni_entro is not None:
                data_val = _to_date(getattr(sc, "data_scadenza", "") or getattr(sc, "data", ""))
                if data_val is None:
                    continue
                try:
                    delta = (data_val - today).days
                    if delta > int(giorni_entro):
                        continue
                    if delta < 0 and not include_scadute:
                        continue
                except Exception:
                    continue
            matching.append(_serialize(sc))

        matching.sort(key=lambda x: (x.get("giorni_al_termine") is None, x.get("giorni_al_termine") or 0))
        items = matching[:limit]
        truncated = len(matching) > len(items)
        return {
            "items": items,
            "total": len(items),
            "returned_count": len(items),
            "total_matching": len(matching),
            "truncated": truncated,
            "coverage_complete": not truncated,
        }
