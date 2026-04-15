"""Retrieval fascicoli per Lex."""

from __future__ import annotations

from typing import Any

from lex.schemas import LexSource
from web.helpers import get_fascicoli


def search_fascicolo_sources(pratica_id: str, message: str, context: dict[str, Any]) -> list[LexSource]:
    rows: list[LexSource] = []
    if pratica_id:
        fascicolo = get_fascicoli().get(pratica_id)
        if fascicolo:
            excerpt = (
                f"Fascicolo {fascicolo.numero}: {fascicolo.titolo}. "
                f"Cliente {fascicolo.nome_cliente}. Oggetto {fascicolo.oggetto or 'n.d.'}."
            )
            rows.append(
                LexSource(
                    source_type="fascicolo",
                    source_id=fascicolo.id,
                    title=fascicolo.titolo or fascicolo.numero,
                    excerpt=excerpt,
                    score=1.0,
                    metadata={"numero": fascicolo.numero, "cliente": fascicolo.nome_cliente},
                )
            )
    for row in list((context.get("structured_context") or {}).get("documenti") or [])[:3]:
        rows.append(
            LexSource(
                source_type="documento_fascicolo",
                source_id=str(row.get("id") or ""),
                title=str(row.get("nome") or "Documento"),
                excerpt=f"Documento {row.get('nome') or 'n.d.'} di tipo {row.get('tipo') or 'n.d.'}.",
                score=0.55,
                metadata={"tipo": row.get("tipo") or ""},
            )
        )
    return rows
