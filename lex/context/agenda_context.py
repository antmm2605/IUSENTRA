"""Contesto agenda per Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_agenda


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_agenda_context(*, pratica_id: str = "", limit: int = 6) -> list[dict[str, Any]]:
    target_id = _clean_spaces(pratica_id)
    rows: list[dict[str, Any]] = []
    for appuntamento in get_agenda().tutti()[:100]:
        if target_id and target_id not in {_clean_spaces(appuntamento.procedimento), _clean_spaces(appuntamento.id_cliente)}:
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
            }
        )
        if len(rows) >= max(int(limit or 0), 1):
            break
    return rows
