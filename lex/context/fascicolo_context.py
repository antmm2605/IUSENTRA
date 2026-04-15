"""Contesto fascicolo per Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_fascicoli


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_fascicolo_context(*, pratica_id: str = "", fascicolo_id: str = "") -> dict[str, Any]:
    target_id = _clean_spaces(pratica_id) or _clean_spaces(fascicolo_id)
    if not target_id:
        return {}
    fascicolo = get_fascicoli().get(target_id)
    if not fascicolo:
        return {}
    return {
        "id": fascicolo.id,
        "numero": fascicolo.numero,
        "titolo": fascicolo.titolo,
        "cliente": fascicolo.nome_cliente,
        "controparte": fascicolo.controparte,
        "oggetto": fascicolo.oggetto,
        "tribunale": fascicolo.tribunale,
        "stato": getattr(fascicolo.stato, "value", ""),
        "tipo": getattr(fascicolo.tipo, "value", ""),
        "data_prossima_udienza": fascicolo.data_prossima_udienza,
        "documenti_count": len(list(fascicolo.documenti or [])),
        "attivita_count": len(list(fascicolo.attivita or [])),
    }
