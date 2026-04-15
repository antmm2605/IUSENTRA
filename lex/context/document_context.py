"""Contesto documentale di Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_fascicoli


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_document_context(*, pratica_id: str = "", fascicolo_id: str = "", limit: int = 8) -> list[dict[str, Any]]:
    target_id = _clean_spaces(pratica_id) or _clean_spaces(fascicolo_id)
    if not target_id:
        return []
    fascicolo = get_fascicoli().get(target_id)
    if not fascicolo:
        return []
    rows: list[dict[str, Any]] = []
    for doc in list(fascicolo.documenti or [])[: max(int(limit or 0), 1)]:
        rows.append(
            {
                "id": doc.id,
                "nome": doc.nome,
                "tipo": getattr(doc.tipo, "value", ""),
                "firmato": bool(getattr(doc, "firmato_digitalmente", False)),
                "data_documento": doc.data_documento,
                "data_caricamento": doc.data_caricamento,
                "note": doc.note,
                "id_deposito_pct": doc.id_deposito_pct,
            }
        )
    return rows
