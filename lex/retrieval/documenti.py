"""Retrieval documentale per Lex."""

from __future__ import annotations

from typing import Any

from lex.schemas import LexSource


def search_document_sources(pratica_id: str, message: str, context: dict[str, Any]) -> list[LexSource]:
    rows: list[LexSource] = []
    for row in list((context.get("structured_context") or {}).get("documenti") or [])[:5]:
        rows.append(
            LexSource(
                source_type="documento",
                source_id=str(row.get("id") or ""),
                title=str(row.get("nome") or "Documento"),
                excerpt=(
                    f"Documento {row.get('nome') or 'n.d.'}; "
                    f"firmato: {'si' if row.get('firmato') else 'no'}; "
                    f"data documento: {row.get('data_documento') or 'n.d.'}."
                ),
                score=0.5,
                metadata={"data_documento": row.get("data_documento") or ""},
            )
        )
    return rows
