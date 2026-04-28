"""Repository documentale per dati migrati da JSON."""

from __future__ import annotations

from typing import Any

from core.database import sqlite_connection


def search_json_documents(database_url: str, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    with sqlite_connection(database_url) as conn:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.source_path,
                d.record_key,
                d.title,
                snippet(json_documents_fts, 2, '<mark>', '</mark>', '...', 12) AS snippet
            FROM json_documents_fts
            JOIN json_documents d ON d.id = json_documents_fts.id
            WHERE json_documents_fts MATCH ?
            LIMIT ?
            """,
            (query, max(1, int(limit))),
        ).fetchall()
    return [dict(row) for row in rows]
