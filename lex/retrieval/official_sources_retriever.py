from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_OFFICIAL_DB = Path("data/fonti_ufficiali/lex_sources.sqlite")
DEFAULT_NORMATTIVA_DB = Path("data/normativa/normattiva.sqlite")
DEFAULT_OFFICIAL_JSONL = Path("data/fonti_ufficiali/index/lex_sources_chunks.jsonl")
DEFAULT_NORMATTIVA_JSONL = Path("data/normativa/index/normattiva_chunks.jsonl")


def search_official_sources(
    query: str,
    materia: str | None = None,
    source: str | None = None,
    limit: int = 10,
    *,
    db_path: str | Path = DEFAULT_OFFICIAL_DB,
    jsonl_path: str | Path = DEFAULT_OFFICIAL_JSONL,
) -> list[dict[str, Any]]:
    db_results = _search_official_db(Path(db_path), query, materia=materia, source=source, limit=limit)
    if db_results:
        return db_results[:limit]
    return _search_jsonl(Path(jsonl_path), query, materia=materia, source=source, limit=limit, default_source="fonti ufficiali")


def search_normattiva(
    query: str,
    materia: str | None = None,
    vigenza: str | None = None,
    limit: int = 10,
    *,
    db_path: str | Path = DEFAULT_NORMATTIVA_DB,
    jsonl_path: str | Path = DEFAULT_NORMATTIVA_JSONL,
) -> list[dict[str, Any]]:
    db_results = _search_normattiva_db(Path(db_path), query, materia=materia, vigenza=vigenza, limit=limit)
    if db_results:
        return db_results[:limit]
    return _search_jsonl(Path(jsonl_path), query, materia=materia, source="Normattiva", limit=limit, default_source="Normattiva")


def search_gazzetta(
    query: str,
    days: int = 30,
    limit: int = 10,
    *,
    db_path: str | Path = DEFAULT_OFFICIAL_DB,
    jsonl_path: str | Path = DEFAULT_OFFICIAL_JSONL,
) -> list[dict[str, Any]]:
    results = search_official_sources(
        query,
        source="gazzetta_ufficiale",
        limit=max(limit, 1),
        db_path=db_path,
        jsonl_path=jsonl_path,
    )
    return results[:limit]


def get_source_document(
    document_id: int | str,
    *,
    db_path: str | Path = DEFAULT_OFFICIAL_DB,
    normattiva_db_path: str | Path = DEFAULT_NORMATTIVA_DB,
) -> dict[str, Any] | None:
    path = Path(db_path)
    if not path.exists():
        return _get_normattiva_document(document_id, Path(normattiva_db_path))
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT id, source_id, source_name, original_url, title, document_type, published_at,
                   materia, raw_path, text_path, hash_sha256, acquired_at, index_status,
                   license, metadata_json
            FROM official_documents
            WHERE id = ?
            """,
            (str(document_id),),
        ).fetchone()
        if row:
            return _row_to_document(row)
    finally:
        con.close()
    return _get_normattiva_document(document_id, Path(normattiva_db_path))


def get_chunk_context(
    chunk_id: int | str,
    *,
    db_path: str | Path = DEFAULT_OFFICIAL_DB,
    normattiva_db_path: str | Path = DEFAULT_NORMATTIVA_DB,
) -> dict[str, Any] | None:
    path = Path(db_path)
    if not path.exists():
        return _get_normattiva_chunk(chunk_id, Path(normattiva_db_path))
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT c.id AS chunk_id, c.document_id, c.source_id, c.chunk_index, c.title, c.text,
                   c.materia, c.reliability_level, c.metadata_json, d.original_url, d.published_at,
                   d.acquired_at, d.hash_sha256, d.source_name
            FROM official_chunks c
            JOIN official_documents d ON d.id = c.document_id
            WHERE c.id = ?
            """,
            (str(chunk_id),),
        ).fetchone()
        if row:
            return _row_to_chunk(row)
    finally:
        con.close()
    return _get_normattiva_chunk(chunk_id, Path(normattiva_db_path))


def _get_normattiva_document(document_id: int | str, path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT id, titolo, data_atto, data_pubblicazione, urn, zip_path, xml_entry,
                   xml_sha256, topics, imported_at, tipo_atto, numero, vigenza
            FROM normative_documents
            WHERE id = ?
            """,
            (str(document_id),),
        ).fetchone()
        if not row:
            return None
        return {
            "document_id": row["id"],
            "fonte": "Normattiva",
            "titolo": row["titolo"],
            "data": row["data_atto"] or row["data_pubblicazione"],
            "url_origine": row["urn"] or row["zip_path"],
            "path_origine": row["zip_path"],
            "materia": (_loads(row["topics"], [""]) or [""])[0],
            "tipo_documento": row["tipo_atto"],
            "numero": row["numero"],
            "vigenza": row["vigenza"],
            "hash_sha256": row["xml_sha256"],
            "livello_affidabilita": "ufficiale",
            "data_acquisizione": row["imported_at"],
        }
    finally:
        con.close()


def _get_normattiva_chunk(chunk_id: int | str, path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT c.id AS chunk_id, c.chunk_key, c.chunk_text, c.metadata_json, d.id AS document_id,
                   d.titolo, d.data_atto, d.data_pubblicazione, d.urn, d.vigenza, d.zip_path,
                   d.xml_entry, d.xml_sha256, d.imported_at
            FROM normative_chunks c
            JOIN normative_documents d ON d.id = c.document_id
            WHERE c.id = ? OR c.chunk_key = ?
            """,
            (str(chunk_id), str(chunk_id)),
        ).fetchone()
        return _row_to_normattiva_chunk(row) if row else None
    finally:
        con.close()


def _search_official_db(path: Path, query: str, materia: str | None, source: str | None, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    q = f"%{query.strip()}%"
    clauses = ["(c.text LIKE ? OR c.title LIKE ? OR d.title LIKE ?)"]
    params: list[Any] = [q, q, q]
    if materia:
        clauses.append("(c.materia = ? OR d.materia = ? OR d.topics_json LIKE ?)")
        params.extend([materia, materia, f"%{materia}%"])
    if source:
        clauses.append("(c.source_id = ? OR d.source_id = ? OR d.source_name LIKE ?)")
        params.extend([source, source, f"%{source}%"])
    params.append(max(1, int(limit)))

    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            f"""
            SELECT c.id AS chunk_id, c.document_id, c.source_id, c.chunk_index, c.title, c.text,
                   c.materia, c.reliability_level, c.metadata_json, d.original_url, d.published_at,
                   d.acquired_at, d.hash_sha256, d.source_name
            FROM official_chunks c
            JOIN official_documents d ON d.id = c.document_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.published_at DESC, c.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_row_to_chunk(row) for row in rows]
    finally:
        con.close()


def _search_normattiva_db(path: Path, query: str, materia: str | None, vigenza: str | None, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    q = f"%{query.strip()}%"
    clauses = ["(c.chunk_text LIKE ? OR d.titolo LIKE ?)"]
    params: list[Any] = [q, q]
    if materia:
        clauses.append("(d.topics LIKE ? OR c.metadata_json LIKE ?)")
        params.extend([f"%{materia}%", f"%{materia}%"])
    if vigenza:
        clauses.append("d.vigenza = ?")
        params.append(vigenza.upper())
    params.append(max(1, int(limit)))

    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            f"""
            SELECT c.id AS chunk_id, c.chunk_key, c.chunk_text, c.metadata_json, d.id AS document_id,
                   d.titolo, d.data_atto, d.data_pubblicazione, d.urn, d.vigenza, d.zip_path,
                   d.xml_entry, d.xml_sha256, d.imported_at
            FROM normative_chunks c
            JOIN normative_documents d ON d.id = c.document_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.data_atto DESC, c.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_row_to_normattiva_chunk(row) for row in rows]
    finally:
        con.close()


def _search_jsonl(path: Path, query: str, materia: str | None, source: str | None, limit: int, default_source: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    needle = query.strip().lower()
    results: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(results) >= limit:
                break
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = str(item.get("text") or "")
            metadata = dict(item.get("metadata") or {})
            haystack = " ".join([text, json.dumps(metadata, ensure_ascii=False)]).lower()
            if needle and needle not in haystack:
                continue
            topics = item.get("topics") or metadata.get("topics") or []
            if materia and materia not in topics and materia.lower() not in haystack:
                continue
            src = str(item.get("source_id") or metadata.get("source") or default_source)
            if source and source.lower() not in src.lower() and source.lower() not in haystack:
                continue
            results.append({
                "fonte": src,
                "titolo": item.get("title") or metadata.get("titolo") or metadata.get("source") or default_source,
                "data": item.get("published_at") or metadata.get("data_atto") or metadata.get("data_pubblicazione"),
                "url_origine": item.get("url") or metadata.get("urn") or metadata.get("zip_path"),
                "chunk_id": item.get("chunk_id") or item.get("id"),
                "testo": text,
                "materia": materia or (topics[0] if topics else ""),
                "livello_affidabilita": "ufficiale",
                "data_acquisizione": item.get("acquired_at") or metadata.get("imported_at"),
                "metadata": metadata,
            })
    return results


def _row_to_document(row: sqlite3.Row) -> dict[str, Any]:
    metadata = _loads(row["metadata_json"], {})
    return {
        "document_id": row["id"],
        "fonte": row["source_name"] or row["source_id"],
        "titolo": row["title"],
        "data": row["published_at"],
        "url_origine": row["original_url"],
        "path_origine": row["raw_path"],
        "materia": row["materia"],
        "tipo_documento": row["document_type"],
        "hash_sha256": row["hash_sha256"],
        "livello_affidabilita": "ufficiale",
        "data_acquisizione": row["acquired_at"],
        "licenza": row["license"],
        "stato_indicizzazione": row["index_status"],
        "metadata": metadata,
    }


def _row_to_chunk(row: sqlite3.Row) -> dict[str, Any]:
    metadata = _loads(row["metadata_json"], {})
    return {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "fonte": row["source_name"] or row["source_id"],
        "titolo": row["title"],
        "data": row["published_at"],
        "url_origine": row["original_url"],
        "chunk": row["chunk_index"],
        "testo": row["text"],
        "materia": row["materia"],
        "livello_affidabilita": row["reliability_level"] or "ufficiale",
        "data_acquisizione": row["acquired_at"],
        "hash_sha256": row["hash_sha256"],
        "metadata": metadata,
    }


def _row_to_normattiva_chunk(row: sqlite3.Row) -> dict[str, Any]:
    metadata = _loads(row["metadata_json"], {})
    return {
        "chunk_id": row["chunk_key"] or row["chunk_id"],
        "document_id": row["document_id"],
        "fonte": "Normattiva",
        "titolo": row["titolo"],
        "data": row["data_atto"] or row["data_pubblicazione"],
        "url_origine": row["urn"] or row["zip_path"],
        "articolo_o_chunk": metadata.get("article_number") or row["chunk_id"],
        "testo": row["chunk_text"],
        "materia": (metadata.get("topics") or [""])[0] if isinstance(metadata.get("topics"), list) else "",
        "vigenza": row["vigenza"],
        "livello_affidabilita": "ufficiale",
        "data_acquisizione": row["imported_at"],
        "hash_sha256": row["xml_sha256"],
        "metadata": metadata,
    }


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback
