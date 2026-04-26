"""Repository SQLite tenant-aware per la Ricerca Studio."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import GlobalSearchDocument, GlobalSearchResult
from .normalizer import normalize_search_text, safe_metadata
from .permissions import can_view_result
from .ranking import compute_score
from .schema import SQLITE_FTS_SCHEMA, SQLITE_SCHEMA
from .snippets import make_snippet


class GlobalSearchRepository:
    """Indice centrale: non interroga i domini durante la ricerca."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.fts_enabled = False
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._conn:
            self._conn.executescript(SQLITE_SCHEMA)
            try:
                self._conn.executescript(SQLITE_FTS_SCHEMA)
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False

    def close(self) -> None:
        self._conn.close()

    def clear_tenant(self, tenant_id: str) -> int:
        rows = self._conn.execute(
            "SELECT id FROM global_search_index WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchall()
        ids = [int(row["id"]) for row in rows]
        with self._conn:
            if self.fts_enabled and ids:
                self._conn.executemany(
                    "DELETE FROM global_search_index_fts WHERE rowid = ?",
                    [(row_id,) for row_id in ids],
                )
            cur = self._conn.execute(
                "DELETE FROM global_search_index WHERE tenant_id = ?",
                (tenant_id,),
            )
        return int(cur.rowcount or 0)

    def upsert_document(self, doc: GlobalSearchDocument) -> int:
        metadata = safe_metadata(doc.metadata)
        indexed_at = datetime.now().isoformat(timespec="seconds")
        search_text = normalize_search_text(doc.search_text)
        with self._conn:
            old = self._conn.execute(
                """
                SELECT id FROM global_search_index
                WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?
                """,
                (doc.tenant_id, doc.entity_type, doc.entity_id),
            ).fetchone()
            if old and self.fts_enabled:
                self._conn.execute(
                    "DELETE FROM global_search_index_fts WHERE rowid = ?",
                    (int(old["id"]),),
                )
            self._conn.execute(
                """
                INSERT INTO global_search_index
                (tenant_id, entity_type, entity_id, title, subtitle, body, keywords,
                 metadata_json, client_id, fascicolo_id, pratica_id, source_module,
                 source_url, visibility, permission_scope, created_at, updated_at,
                 indexed_at, search_text)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id, entity_type, entity_id) DO UPDATE SET
                    title = excluded.title,
                    subtitle = excluded.subtitle,
                    body = excluded.body,
                    keywords = excluded.keywords,
                    metadata_json = excluded.metadata_json,
                    client_id = excluded.client_id,
                    fascicolo_id = excluded.fascicolo_id,
                    pratica_id = excluded.pratica_id,
                    source_module = excluded.source_module,
                    source_url = excluded.source_url,
                    visibility = excluded.visibility,
                    permission_scope = excluded.permission_scope,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    indexed_at = excluded.indexed_at,
                    search_text = excluded.search_text
                """,
                (
                    doc.tenant_id,
                    doc.entity_type,
                    doc.entity_id,
                    doc.title,
                    doc.subtitle,
                    doc.body,
                    doc.keywords,
                    json.dumps(metadata, ensure_ascii=False),
                    doc.client_id,
                    doc.fascicolo_id,
                    doc.pratica_id,
                    doc.source_module,
                    doc.source_url,
                    doc.visibility,
                    doc.permission_scope,
                    doc.created_at,
                    doc.updated_at,
                    indexed_at,
                    search_text,
                ),
            )
            row = self._conn.execute(
                """
                SELECT id FROM global_search_index
                WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?
                """,
                (doc.tenant_id, doc.entity_type, doc.entity_id),
            ).fetchone()
            row_id = int(row["id"])
            if self.fts_enabled:
                self._conn.execute(
                    """
                    INSERT INTO global_search_index_fts
                    (rowid, title, subtitle, body, keywords, search_text)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (row_id, doc.title, doc.subtitle, doc.body, doc.keywords, search_text),
                )
        return row_id

    def upsert_many(self, documents: list[GlobalSearchDocument]) -> int:
        count = 0
        for doc in documents:
            self.upsert_document(doc)
            count += 1
        return count

    def remove_entity(self, tenant_id: str, entity_type: str, entity_id: str) -> int:
        row = self._conn.execute(
            """
            SELECT id FROM global_search_index
            WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?
            """,
            (tenant_id, entity_type, entity_id),
        ).fetchone()
        with self._conn:
            if row and self.fts_enabled:
                self._conn.execute(
                    "DELETE FROM global_search_index_fts WHERE rowid = ?",
                    (int(row["id"]),),
                )
            cur = self._conn.execute(
                """
                DELETE FROM global_search_index
                WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?
                """,
                (tenant_id, entity_type, entity_id),
            )
        return int(cur.rowcount or 0)

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 20,
        user: Any = None,
    ) -> list[GlobalSearchResult]:
        query = (query or "").strip()
        if not query:
            return []
        limit = max(1, min(int(limit or 20), 100))
        rows = self._search_fts(tenant_id, query, entity_types, limit * 3)
        if not rows:
            rows = self._search_like(tenant_id, query, entity_types, limit * 3)

        results: list[GlobalSearchResult] = []
        for row in rows:
            data = self._row_to_dict(row)
            if not can_view_result(user, data):
                continue
            base_score = float(data.pop("_base_rank", 0.0) or 0.0)
            score = compute_score(data, query, base_score)
            snippet = make_snippet(
                " ".join([data.get("title", ""), data.get("subtitle", ""), data.get("body", ""), data.get("keywords", "")]),
                query,
            )
            results.append(
                GlobalSearchResult(
                    id=int(data["id"]),
                    tenant_id=data["tenant_id"],
                    entity_type=data["entity_type"],
                    entity_id=data["entity_id"],
                    title=data["title"],
                    subtitle=data["subtitle"],
                    snippet=snippet,
                    score=score,
                    source_module=data["source_module"],
                    source_url=data["source_url"],
                    client_id=data["client_id"],
                    fascicolo_id=data["fascicolo_id"],
                    metadata=data["metadata"],
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    def suggest(self, *, tenant_id: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
        return [
            {
                "label": result.title,
                "type": result.entity_type,
                "url": result.source_url,
                "subtitle": result.subtitle,
            }
            for result in self.search(tenant_id=tenant_id, query=query, limit=limit)
        ]

    def stats(self, tenant_id: str) -> dict[str, Any]:
        rows = self._conn.execute(
            """
            SELECT entity_type, COUNT(*) AS total
            FROM global_search_index
            WHERE tenant_id = ?
            GROUP BY entity_type
            ORDER BY entity_type
            """,
            (tenant_id,),
        ).fetchall()
        per_type = {row["entity_type"]: int(row["total"]) for row in rows}
        return {
            "tenant_id": tenant_id,
            "total": sum(per_type.values()),
            "per_type": per_type,
            "fts_enabled": self.fts_enabled,
        }

    def audit(self, tenant_id: str, action: str, details: dict[str, Any] | None = None) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO global_search_audit(tenant_id, action, details_json, created_at)
                VALUES (?,?,?,?)
                """,
                (
                    tenant_id,
                    action,
                    json.dumps(safe_metadata(details or {}), ensure_ascii=False),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def _search_fts(
        self,
        tenant_id: str,
        query: str,
        entity_types: list[str] | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        if not self.fts_enabled:
            return []
        fts_query = self._fts_query(query)
        params: list[Any] = [fts_query, tenant_id]
        type_sql = ""
        if entity_types:
            type_sql = "AND i.entity_type IN ({})".format(",".join("?" for _ in entity_types))
            params.extend(entity_types)
        params.append(limit)
        sql = f"""
            SELECT i.*, bm25(global_search_index_fts) AS _base_rank
            FROM global_search_index_fts f
            JOIN global_search_index i ON i.id = f.rowid
            WHERE global_search_index_fts MATCH ?
              AND i.tenant_id = ?
              {type_sql}
            ORDER BY _base_rank
            LIMIT ?
        """
        try:
            return self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []

    def _search_like(
        self,
        tenant_id: str,
        query: str,
        entity_types: list[str] | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        tokens = [t for t in normalize_search_text(query).split() if t]
        if not tokens:
            return []
        where = ["tenant_id = ?"]
        params: list[Any] = [tenant_id]
        for token in tokens:
            like = f"%{token}%"
            where.append("(search_text LIKE ? OR title LIKE ? OR subtitle LIKE ? OR keywords LIKE ?)")
            params.extend([like, like, like, like])
        if entity_types:
            where.append("entity_type IN ({})".format(",".join("?" for _ in entity_types)))
            params.extend(entity_types)
        params.append(limit)
        sql = f"""
            SELECT *, 50.0 AS _base_rank
            FROM global_search_index
            WHERE {' AND '.join(where)}
            ORDER BY updated_at DESC, indexed_at DESC
            LIMIT ?
        """
        return self._conn.execute(sql, params).fetchall()

    @staticmethod
    def _fts_query(query: str) -> str:
        tokens = [token.replace('"', "").replace("'", "") for token in normalize_search_text(query).split() if token]
        if not tokens:
            return '""'
        return " ".join(f"{token}*" for token in tokens)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            metadata = json.loads(data.get("metadata_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        data["metadata"] = metadata if isinstance(metadata, dict) else {}
        return data
