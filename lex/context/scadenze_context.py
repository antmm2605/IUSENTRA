"""Contesto scadenze per Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_scadenziario


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_scadenze_context(*, pratica_id: str = "", limit: int = 6) -> list[dict[str, Any]]:
    target_id = _clean_spaces(pratica_id)
    rows: list[dict[str, Any]] = []
    for scadenza in get_scadenziario().tutte()[:100]:
        if target_id and _clean_spaces(getattr(scadenza, "id_fascicolo", "")) != target_id:
            continue
        rows.append(
            {
                "id": scadenza.id,
                "titolo": scadenza.titolo,
                "data": scadenza.data,
                "tipo": getattr(scadenza.tipo, "value", ""),
                "stato": getattr(scadenza.stato, "value", ""),
                "priorita": getattr(scadenza.priorita, "value", ""),
                "id_fascicolo": getattr(scadenza, "id_fascicolo", ""),
            }
        )
        if len(rows) >= max(int(limit or 0), 1):
            break
    return rows
