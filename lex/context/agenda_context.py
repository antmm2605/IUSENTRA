"""Contesto agenda per Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_agenda, get_fascicoli


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _agenda_target_ids(pratica_id: str) -> set[str]:
    target = _clean_spaces(pratica_id)
    if not target:
        return set()
    values = {target.lower()}
    try:
        fascicolo = get_fascicoli().get(target)
    except Exception:
        fascicolo = None
    if fascicolo is None:
        return values
    for candidate in (
        getattr(fascicolo, "id", ""),
        getattr(fascicolo, "id_cliente", ""),
        getattr(fascicolo, "numero", ""),
        getattr(fascicolo, "numero_rg", ""),
        getattr(fascicolo, "rg_completo", ""),
    ):
        clean = _clean_spaces(candidate).lower()
        if clean:
            values.add(clean)
    return values


def load_agenda_context(*, pratica_id: str = "", limit: int = 6) -> list[dict[str, Any]]:
    target_ids = _agenda_target_ids(pratica_id)
    rows: list[dict[str, Any]] = []
    for appuntamento in get_agenda().tutti()[:100]:
        appointment_keys = {
            _clean_spaces(getattr(appuntamento, "procedimento", "")).lower(),
            _clean_spaces(getattr(appuntamento, "id_cliente", "")).lower(),
        }
        appointment_keys.discard("")
        if target_ids and target_ids.isdisjoint(appointment_keys):
            continue
        rows.append(
            {
                "id": appuntamento.id,
                "titolo": appuntamento.titolo,
                "tipo": getattr(appuntamento.tipo, "value", ""),
                "data_ora": appuntamento.data_ora,
                "stato": getattr(appuntamento.stato, "value", ""),
                "luogo": appuntamento.luogo,
                "procedimento": appuntamento.procedimento,
                "tribunale": appuntamento.tribunale,
                "id_cliente": getattr(appuntamento, "id_cliente", ""),
                "cliente": getattr(appuntamento, "cliente", ""),
                "note": getattr(appuntamento, "note", ""),
            }
        )
        if len(rows) >= max(int(limit or 0), 1):
            break
    return rows
