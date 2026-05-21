from __future__ import annotations

import json
import os
import re
import sqlite3
from html import unescape
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

DEFAULT_OFFICIAL_DB = Path("data/fonti_ufficiali/lex_sources.sqlite")
DEFAULT_NORMATTIVA_DB = Path("data/normativa/normattiva.sqlite")
DEFAULT_OFFICIAL_JSONL = Path("data/fonti_ufficiali/index/lex_sources_chunks.jsonl")
DEFAULT_NORMATTIVA_JSONL = Path("data/normativa/index/normattiva_chunks.jsonl")
CONTAINER_OFFICIAL_DB = Path("/data/fonti_ufficiali/lex_sources.sqlite")
CONTAINER_NORMATTIVA_DB = Path("/data/normativa/normattiva.sqlite")
CONTAINER_OFFICIAL_JSONL = Path("/data/fonti_ufficiali/index/lex_sources_chunks.jsonl")
CONTAINER_NORMATTIVA_JSONL = Path("/data/normativa/index/normattiva_chunks.jsonl")
DEFAULT_NORMATTIVA_RAW = Path("data/normativa/raw")
CONTAINER_NORMATTIVA_RAW = Path("/data/normativa/raw")
_COUNT_TABLES = {
    "normative_documents": "normative_documents",
    "normative_articles": "normative_articles",
    "normative_chunks": "normative_chunks",
    "official_documents": "official_documents",
    "official_chunks": "official_chunks",
    "official_sources": "official_sources",
}
_COUNT_WHERE = {
    "": "",
    "source_id = 'gazzetta_ufficiale'": " WHERE source_id = 'gazzetta_ufficiale'",
}

ARTICLE_QUERY_RE = re.compile(
    r"\b(?:art\.?|articolo)\s*(?P<number>\d{1,4})(?:[\s.-]+(?P<suffix>bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\b",
    flags=re.I,
)
RAW_ARTICLE_RE = re.compile(
    r"\bArt\.\s*(?P<number>\d{1,4})(?:[\s.-]+(?P<suffix>bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\s*[.)-]",
    flags=re.I,
)
SEARCH_STOPWORDS = {
    "a",
    "al",
    "alla",
    "alle",
    "art",
    "articolo",
    "cod",
    "codice",
    "commi",
    "comma",
    "con",
    "da",
    "del",
    "della",
    "di",
    "e",
    "il",
    "in",
    "la",
    "lo",
    "per",
    "sul",
    "testo",
}
CODE_TARGETS: dict[str, dict[str, Any]] = {
    "codice_civile": {
        "label": "Codice civile",
        "numero": "262",
        "data_atto": "1942-03-16",
        "file_markers": ("19420316_262", "042U0262"),
        "aliases": ("codice civile", "c.c.", "cc"),
    },
    "codice_procedura_civile": {
        "label": "Codice di procedura civile",
        "numero": "1443",
        "data_atto": "1940-10-28",
        "file_markers": ("19401028_1443", "040U1443"),
        "aliases": ("codice procedura civile", "codice di procedura civile", "c.p.c.", "cpc"),
    },
    "codice_penale": {
        "label": "Codice penale",
        "numero": "1398",
        "data_atto": "1930-10-19",
        "file_markers": ("19301019_1398", "030U1398"),
        "aliases": ("codice penale", "c.p.", "cp"),
    },
    "codice_procedura_penale": {
        "label": "Codice di procedura penale",
        "numero": "447",
        "data_atto": "1988-09-22",
        "file_markers": ("19880922_447", "088G0492"),
        "aliases": ("codice procedura penale", "codice di procedura penale", "c.p.p.", "cpp"),
    },
    "codice_processo_amministrativo": {
        "label": "Codice del processo amministrativo",
        "numero": "104",
        "data_atto": "2010-07-02",
        "file_markers": ("20100702_104", "010G0127"),
        "aliases": ("codice processo amministrativo", "codice del processo amministrativo", "c.p.a.", "cpa"),
    },
    "codice_strada": {
        "label": "Codice della strada",
        "numero": "285",
        "data_atto": "1992-04-30",
        "file_markers": ("19920430_285", "092G0306"),
        "aliases": ("codice strada", "codice della strada", "c.d.s.", "cds", "cod. str."),
    },
}


def _resolve_runtime_path(
    explicit: str | Path | None,
    *,
    env_names: tuple[str, ...],
    container_path: Path,
    repo_path: Path,
) -> Path:
    if explicit is not None:
        return Path(explicit)
    for env_name in env_names:
        value = str(os.getenv(env_name, "") or "").strip()
        if value:
            return Path(value)
    if container_path.exists():
        return container_path
    return repo_path


def search_official_sources(
    query: str,
    materia: str | None = None,
    source: str | None = None,
    limit: int = 10,
    *,
    db_path: str | Path | None = None,
    jsonl_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    db_target = _resolve_runtime_path(
        db_path,
        env_names=("PCT_LEX_OFFICIAL_DB", "PCT_OFFICIAL_SOURCES_DB", "PCT_LEX_SOURCES_DB"),
        container_path=CONTAINER_OFFICIAL_DB,
        repo_path=DEFAULT_OFFICIAL_DB,
    )
    jsonl_target = _resolve_runtime_path(
        jsonl_path,
        env_names=("PCT_LEX_OFFICIAL_JSONL", "PCT_OFFICIAL_SOURCES_JSONL", "PCT_LEX_SOURCES_JSONL"),
        container_path=CONTAINER_OFFICIAL_JSONL,
        repo_path=DEFAULT_OFFICIAL_JSONL,
    )
    db_results = _search_official_db(db_target, query, materia=materia, source=source, limit=limit)
    if db_results:
        return db_results[:limit]
    return _search_jsonl(jsonl_target, query, materia=materia, source=source, limit=limit, default_source="fonti ufficiali")


def search_normattiva(
    query: str,
    materia: str | None = None,
    vigenza: str | None = None,
    limit: int = 10,
    *,
    db_path: str | Path | None = None,
    jsonl_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    db_target = _resolve_runtime_path(
        db_path,
        env_names=("PCT_NORMATTIVA_DB", "PCT_LEX_NORMATTIVA_DB"),
        container_path=CONTAINER_NORMATTIVA_DB,
        repo_path=DEFAULT_NORMATTIVA_DB,
    )
    jsonl_target = _resolve_runtime_path(
        jsonl_path,
        env_names=("PCT_NORMATTIVA_JSONL", "PCT_LEX_NORMATTIVA_JSONL"),
        container_path=CONTAINER_NORMATTIVA_JSONL,
        repo_path=DEFAULT_NORMATTIVA_JSONL,
    )
    db_results = _search_normattiva_db(db_target, query, materia=materia, vigenza=vigenza, limit=limit)
    if db_results:
        return db_results[:limit]
    return _search_jsonl(jsonl_target, query, materia=materia, source="Normattiva", limit=limit, default_source="Normattiva")


def search_gazzetta(
    query: str,
    days: int = 30,
    limit: int = 10,
    *,
    db_path: str | Path | None = None,
    jsonl_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    results = search_official_sources(
        query,
        source="gazzetta_ufficiale",
        limit=max(limit * 6, limit, 1),
        db_path=db_path,
        jsonl_path=jsonl_path,
    )
    return _dedupe_results(results, limit=limit, keys=("document_id", "url_origine", "titolo"))


def official_archive_snapshot(
    *,
    official_db_path: str | Path | None = None,
    normattiva_db_path: str | Path | None = None,
) -> dict[str, Any]:
    official_path = _resolve_runtime_path(
        official_db_path,
        env_names=("PCT_LEX_OFFICIAL_DB", "PCT_OFFICIAL_SOURCES_DB", "PCT_LEX_SOURCES_DB"),
        container_path=CONTAINER_OFFICIAL_DB,
        repo_path=DEFAULT_OFFICIAL_DB,
    )
    normattiva_path = _resolve_runtime_path(
        normattiva_db_path,
        env_names=("PCT_NORMATTIVA_DB", "PCT_LEX_NORMATTIVA_DB"),
        container_path=CONTAINER_NORMATTIVA_DB,
        repo_path=DEFAULT_NORMATTIVA_DB,
    )
    return {
        "normattiva": _sqlite_counts(
            normattiva_path,
            {
                "documents": "normative_documents",
                "articles": "normative_articles",
                "chunks": "normative_chunks",
            },
        ),
        "gazzetta": _sqlite_counts(
            official_path,
            {
                "documents": "official_documents",
                "chunks": "official_chunks",
                "sources": "official_sources",
            },
            where={"documents": "source_id = 'gazzetta_ufficiale'", "chunks": "source_id = 'gazzetta_ufficiale'"},
        ),
        "paths": {
            "normattiva_db": str(normattiva_path),
            "official_db": str(official_path),
        },
    }


def get_source_document(
    document_id: int | str,
    *,
    db_path: str | Path | None = None,
    normattiva_db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    path = _resolve_runtime_path(
        db_path,
        env_names=("PCT_LEX_OFFICIAL_DB", "PCT_OFFICIAL_SOURCES_DB", "PCT_LEX_SOURCES_DB"),
        container_path=CONTAINER_OFFICIAL_DB,
        repo_path=DEFAULT_OFFICIAL_DB,
    )
    normattiva_path = _resolve_runtime_path(
        normattiva_db_path,
        env_names=("PCT_NORMATTIVA_DB", "PCT_LEX_NORMATTIVA_DB"),
        container_path=CONTAINER_NORMATTIVA_DB,
        repo_path=DEFAULT_NORMATTIVA_DB,
    )
    if not path.exists():
        return _get_normattiva_document(document_id, normattiva_path)
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
    return _get_normattiva_document(document_id, normattiva_path)


def get_chunk_context(
    chunk_id: int | str,
    *,
    db_path: str | Path | None = None,
    normattiva_db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    path = _resolve_runtime_path(
        db_path,
        env_names=("PCT_LEX_OFFICIAL_DB", "PCT_OFFICIAL_SOURCES_DB", "PCT_LEX_SOURCES_DB"),
        container_path=CONTAINER_OFFICIAL_DB,
        repo_path=DEFAULT_OFFICIAL_DB,
    )
    normattiva_path = _resolve_runtime_path(
        normattiva_db_path,
        env_names=("PCT_NORMATTIVA_DB", "PCT_LEX_NORMATTIVA_DB"),
        container_path=CONTAINER_NORMATTIVA_DB,
        repo_path=DEFAULT_NORMATTIVA_DB,
    )
    if not path.exists():
        return _get_normattiva_chunk(chunk_id, normattiva_path)
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
    return _get_normattiva_chunk(chunk_id, normattiva_path)


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
    params: list[Any] = []
    terms = _search_terms(query)
    if not terms and query.strip():
        terms = [query.strip().lower()]
    fixed_terms = terms[:8]
    for slot in range(8):
        term = fixed_terms[slot] if slot < len(fixed_terms) else ""
        pattern = f"%{term.lower()}%" if term else ""
        params.extend([1 if term else 0, pattern, pattern, pattern, pattern])
    materia_value = str(materia or "").strip()
    source_value = str(source or "").strip()
    params.extend([materia_value, materia_value, materia_value, f"%{materia_value}%"])
    params.extend([source_value, source_value, source_value, f"%{source_value}%"])
    params.append(max(1, int(limit)))

    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT c.id AS chunk_id, c.document_id, c.source_id, c.chunk_index, c.title, c.text,
                   c.materia, c.reliability_level, c.metadata_json, d.original_url, d.published_at,
                   d.acquired_at, d.hash_sha256, d.source_name
            FROM official_chunks c
            JOIN official_documents d ON d.id = c.document_id
            WHERE
                (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.text, '')) LIKE ? OR LOWER(COALESCE(c.title, '')) LIKE ? OR LOWER(COALESCE(d.title, '')) LIKE ? OR LOWER(COALESCE(d.original_url, '')) LIKE ?)
                AND (? = '' OR c.materia = ? OR d.materia = ? OR d.topics_json LIKE ?)
                AND (? = '' OR c.source_id = ? OR d.source_id = ? OR d.source_name LIKE ?)
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
    code_key = _detect_code_target(query)
    article_ref = _extract_article_reference(query)
    terms = _search_terms(query, drop_code_terms=bool(code_key))
    params: list[Any] = []
    if not terms and query.strip():
        terms = [query.strip().lower()]
    fixed_terms = terms[:8]
    for slot in range(8):
        term = fixed_terms[slot] if slot < len(fixed_terms) else ""
        pattern = f"%{term.lower()}%" if term else ""
        params.extend([1 if term else 0, pattern, pattern, pattern, pattern, pattern, pattern, pattern])
    if code_key:
        target = CODE_TARGETS[code_key]
        code_numero = target["numero"]
        code_data = target["data_atto"]
    else:
        code_numero = ""
        code_data = ""
    params.extend([code_numero, code_numero, code_data])
    article_patterns = _article_like_patterns(article_ref or "")[:4] if article_ref else []
    for slot in range(4):
        pattern = article_patterns[slot] if slot < len(article_patterns) else ""
        params.extend([1 if pattern else 0, pattern, pattern, pattern, pattern])
    materia_value = str(materia or "").strip()
    vigenza_value = str(vigenza or "").strip().upper()
    params.extend([materia_value, f"%{materia_value}%", f"%{materia_value}%"])
    params.extend([vigenza_value, vigenza_value])
    params.append(max(1, int(limit)))

    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT c.id AS chunk_id, c.chunk_key, c.chunk_text, c.metadata_json, d.id AS document_id,
                   d.titolo, d.data_atto, d.data_pubblicazione, d.urn, d.vigenza, d.zip_path,
                   d.xml_entry, d.xml_sha256, d.imported_at
            FROM normative_chunks c
            JOIN normative_documents d ON d.id = c.document_id
            LEFT JOIN normative_articles a ON a.id = c.article_id
            WHERE
                (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = 0 OR LOWER(COALESCE(c.chunk_text, '')) LIKE ? OR LOWER(COALESCE(d.titolo, '')) LIKE ? OR LOWER(COALESCE(d.tipo_atto, '')) LIKE ? OR LOWER(COALESCE(d.numero, '')) LIKE ? OR LOWER(COALESCE(a.article_number, '')) LIKE ? OR LOWER(COALESCE(a.article_title, '')) LIKE ? OR LOWER(COALESCE(c.metadata_json, '')) LIKE ?)
                AND (? = '' OR (d.numero = ? AND d.data_atto = ?))
                AND (? = 0 OR a.article_number LIKE ? OR a.article_title LIKE ? OR c.chunk_text LIKE ? OR c.metadata_json LIKE ?)
                AND (? = 0 OR a.article_number LIKE ? OR a.article_title LIKE ? OR c.chunk_text LIKE ? OR c.metadata_json LIKE ?)
                AND (? = 0 OR a.article_number LIKE ? OR a.article_title LIKE ? OR c.chunk_text LIKE ? OR c.metadata_json LIKE ?)
                AND (? = 0 OR a.article_number LIKE ? OR a.article_title LIKE ? OR c.chunk_text LIKE ? OR c.metadata_json LIKE ?)
                AND (? = '' OR d.topics LIKE ? OR c.metadata_json LIKE ?)
                AND (? = '' OR d.vigenza = ?)
            ORDER BY d.data_atto DESC, c.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        results = [_row_to_normattiva_chunk(row) for row in rows]
    finally:
        con.close()
    if results:
        return results
    if code_key:
        return _search_normattiva_raw_code_articles(path, query, code_key=code_key, article_ref=article_ref, limit=limit)
    return []


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


def _sqlite_counts(path: Path, tables: dict[str, str], *, where: dict[str, str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"available": path.exists(), "path": str(path)}
    if not path.exists():
        for key in tables:
            payload[key] = 0
        return payload
    con = sqlite3.connect(path)
    try:
        for key, table in tables.items():
            table_name = _COUNT_TABLES.get(table)
            if not table_name:
                payload[key] = 0
                continue
            clause = _COUNT_WHERE.get(str((where or {}).get(key) or ""), "")
            try:
                payload[key] = int(con.execute("SELECT COUNT(*) FROM " + table_name + clause).fetchone()[0] or 0)
            except sqlite3.Error:
                payload[key] = 0
        return payload
    finally:
        con.close()


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


def _search_terms(query: str, *, drop_code_terms: bool = False) -> list[str]:
    normalized = _normalize_search_text(query)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    stopwords = set(SEARCH_STOPWORDS)
    if drop_code_terms:
        stopwords.update({"civile", "penale", "procedura", "processo", "amministrativo", "strada"})
    terms: list[str] = []
    for token in tokens:
        if token in stopwords:
            continue
        if len(token) < 2 and not token.isdigit():
            continue
        if token not in terms:
            terms.append(token)
    return terms[:8]


def _normalize_search_text(value: str) -> str:
    text = str(value or "").lower()
    text = text.replace("c.p.p.", "cpp")
    text = text.replace("c.p.c.", "cpc")
    text = text.replace("c.p.a.", "cpa")
    text = text.replace("c.d.s.", "cds")
    text = text.replace("c.c.", "cc")
    text = text.replace("c.p.", "cp")
    text = re.sub(r"[-/.,;:()\\[\\]{}]+", " ", text)
    return " ".join(text.split())


def _detect_code_target(query: str) -> str | None:
    normalized = f" {_normalize_search_text(query)} "
    ordered = [
        "codice_procedura_penale",
        "codice_procedura_civile",
        "codice_processo_amministrativo",
        "codice_strada",
        "codice_civile",
        "codice_penale",
    ]
    for key in ordered:
        aliases = CODE_TARGETS[key]["aliases"]
        for alias in aliases:
            alias_norm = _normalize_search_text(alias)
            if f" {alias_norm} " in normalized:
                return key
    return None


def _extract_article_reference(query: str) -> str | None:
    match = ARTICLE_QUERY_RE.search(query or "")
    if not match:
        return None
    number = match.group("number")
    suffix = (match.group("suffix") or "").lower().strip()
    return f"{number}{f' {suffix}' if suffix else ''}"


def _article_like_patterns(article_ref: str) -> list[str]:
    ref = " ".join(str(article_ref or "").lower().replace("-", " ").split())
    if not ref:
        return []
    dashed = ref.replace(" ", "-")
    return list(
        dict.fromkeys(
            [
                f"%Art. {ref}.%",
                f"%Art. {ref} -%",
                f"%Art. {dashed}.%",
                f"%Art. {dashed} -%",
            ]
        )
    )


def _dedupe_results(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = "|".join(str(row.get(name) or "").strip() for name in keys)
        if not key.strip("|"):
            key = json.dumps(row, ensure_ascii=False, sort_keys=True)[:500]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


def _normattiva_raw_dir_from_db(db_path: Path) -> Path:
    env_value = str(os.getenv("PCT_NORMATTIVA_RAW_DIR", "") or "").strip()
    if env_value:
        return Path(env_value)
    if db_path.is_absolute() and str(db_path).replace("\\", "/").startswith("/data/normativa"):
        return CONTAINER_NORMATTIVA_RAW
    if db_path.parent.name == "normativa":
        return db_path.parent / "raw"
    return db_path.parent / "raw"


def _search_normattiva_raw_code_articles(
    db_path: Path,
    query: str,
    *,
    code_key: str,
    article_ref: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    raw_dir = _normattiva_raw_dir_from_db(db_path)
    if not raw_dir.exists():
        return []
    target = CODE_TARGETS[code_key]
    results: list[dict[str, Any]] = []
    for zip_path in sorted(raw_dir.glob("Codici*.zip")):
        try:
            with ZipFile(zip_path) as archive:
                for entry in archive.namelist():
                    if not _raw_entry_matches_code(entry, target):
                        continue
                    xml_text = archive.read(entry).decode("utf-8", errors="replace")
                    plain_text = _xml_to_plain_text(xml_text)
                    excerpt = _article_excerpt_from_text(plain_text, article_ref) if article_ref else _short_plain_text(plain_text)
                    if not excerpt:
                        continue
                    title = _raw_xml_value(xml_text, "titoloDoc") or target["label"]
                    data_atto = _raw_xml_attr(xml_text, "dataDoc", "norm") or str(target.get("data_atto") or "")
                    data_atto = _norm_raw_date(data_atto)
                    results.append(
                        {
                            "chunk_id": f"normattiva-raw:{code_key}:{article_ref or 'documento'}",
                            "document_id": f"normattiva-raw:{code_key}",
                            "fonte": "Normattiva",
                            "titolo": title,
                            "data": data_atto,
                            "url_origine": str(zip_path),
                            "path_origine": str(zip_path),
                            "articolo_o_chunk": f"Art. {article_ref}" if article_ref else "documento",
                            "testo": excerpt,
                            "materia": "Normativa",
                            "vigenza": "ORIGINALE",
                            "livello_affidabilita": "ufficiale",
                            "data_acquisizione": "",
                            "hash_sha256": "",
                            "metadata": {
                                "source": "Normattiva Open Data",
                                "source_path": str(zip_path),
                                "xml_entry": entry,
                                "code_key": code_key,
                                "article_reference": article_ref,
                                "no_invented_link": True,
                            },
                        }
                    )
                    if len(results) >= limit:
                        return results
        except (BadZipFile, OSError):
            continue
    return results


def _raw_entry_matches_code(entry: str, target: dict[str, Any]) -> bool:
    normalized = entry.lower()
    return any(str(marker).lower() in normalized for marker in target.get("file_markers", ()))


def _xml_to_plain_text(xml_text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", xml_text)
    text = unescape(text)
    return " ".join(text.split())


def _article_excerpt_from_text(text: str, article_ref: str | None) -> str:
    if not article_ref:
        return ""
    normalized_ref = " ".join(article_ref.replace("-", " ").split())
    wanted_parts = normalized_ref.split()
    wanted_number = wanted_parts[0]
    wanted_suffix = wanted_parts[1] if len(wanted_parts) > 1 else ""
    matches = list(RAW_ARTICLE_RE.finditer(text))
    for index, match in enumerate(matches):
        number = (match.group("number") or "").strip()
        suffix = (match.group("suffix") or "").strip().lower()
        if number != wanted_number or suffix != wanted_suffix:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else min(len(text), match.start() + 1800)
        return _short_plain_text(text[match.start() : end], limit=1800)
    return ""


def _short_plain_text(text: str, *, limit: int = 1800) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned[:limit].rstrip()


def _raw_xml_value(xml_text: str, tag: str) -> str:
    match = re.search(rf"<{re.escape(tag)}[^>]*>(.*?)</{re.escape(tag)}>", xml_text, flags=re.I | re.S)
    return _short_plain_text(unescape(re.sub(r"<[^>]+>", " ", match.group(1)))) if match else ""


def _raw_xml_attr(xml_text: str, tag: str, attr: str) -> str:
    match = re.search(rf"<{re.escape(tag)}[^>]*\b{re.escape(attr)}=[\"']([^\"']+)[\"']", xml_text, flags=re.I)
    return match.group(1) if match else ""


def _norm_raw_date(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return value
