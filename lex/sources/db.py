from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .extractors import extract_text, split_chunks
from .classifier import detect_topics
from .models import DocumentCandidate, SourceConfig


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "lex_sources_sqlite.sql"


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def init_db(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA_PATH.resolve().read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()


def upsert_source(db_path: str | Path, source: SourceConfig) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO official_sources(id, name, connector, enabled, priority, type, refresh, base_url, settings_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,
              connector=excluded.connector,
              enabled=excluded.enabled,
              priority=excluded.priority,
              type=excluded.type,
              refresh=excluded.refresh,
              base_url=excluded.base_url,
              settings_json=excluded.settings_json,
              updated_at=CURRENT_TIMESTAMP
            """,
            (source.id, source.name, source.connector, int(source.enabled), source.priority, source.type, source.refresh, source.base_url, json.dumps(source.settings, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()


def start_run(db_path: str | Path, source_id: str) -> int:
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute("INSERT INTO official_sync_runs(source_id, started_at, status) VALUES (?, ?, ?)", (source_id, now_iso(), "running"))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def finish_run(db_path: str | Path, run_id: int, status: str, message: str = "", found: int = 0, saved: int = 0) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "UPDATE official_sync_runs SET finished_at=?, status=?, message=?, documents_found=?, documents_saved=? WHERE id=?",
            (now_iso(), status, message, found, saved, run_id),
        )
        con.commit()
    finally:
        con.close()


def record_error(db_path: str | Path, source_id: str, run_id: int | None, message: str, *, url: str = "", error_type: str = "sync") -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO official_source_errors(source_id, run_id, url, error_type, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_id, run_id, url, error_type, message),
        )
        con.commit()
    finally:
        con.close()


def save_document(db_path: str | Path, doc: DocumentCandidate, raw_path: Path, text_dir: Path) -> int | None:
    raw_bytes = raw_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    text_dir.mkdir(parents=True, exist_ok=True)
    text = extract_text(raw_path, doc.content_type)
    detected_topics, score = detect_topics((doc.title or "") + " " + text[:20000])
    topics = sorted(set(doc.topics + detected_topics))
    text_path = text_dir / f"{digest}.txt"
    text_path.write_text(text, encoding="utf-8", errors="ignore")

    con = sqlite3.connect(db_path)
    try:
        try:
            cur = con.execute(
                """
                INSERT INTO official_documents(source_id, source_name, original_url, title, document_type, content_type,
                                               filename, raw_path, text_path, hash_sha256, published_at, acquired_at,
                                               materia, text_content, index_status, license, topics_json, relevance_score, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.source_id,
                    doc.metadata.get("fonte") or doc.source_id,
                    doc.url,
                    doc.title,
                    doc.metadata.get("tipo_documento") or doc.metadata.get("tipo_atto") or doc.content_type,
                    doc.content_type,
                    doc.filename or raw_path.name,
                    str(raw_path),
                    str(text_path),
                    digest,
                    doc.published_at,
                    now_iso(),
                    topics[0] if topics else "",
                    text,
                    "indicizzato",
                    doc.metadata.get("licenza") or "",
                    json.dumps(topics, ensure_ascii=False),
                    score,
                    json.dumps(doc.metadata, ensure_ascii=False),
                ),
            )
            document_id = int(cur.lastrowid)
        except sqlite3.IntegrityError:
            con.rollback()
            return None

        chunks = split_chunks(text)
        for idx, chunk in enumerate(chunks):
            con.execute(
                """
                INSERT INTO official_chunks(document_id, source_id, chunk_index, title, text, materia, token_estimate, topics_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (document_id, doc.source_id, idx, doc.title, chunk, topics[0] if topics else "", max(1, len(chunk) // 4), json.dumps(topics, ensure_ascii=False), json.dumps(doc.metadata, ensure_ascii=False)),
            )
        con.commit()
        return document_id
    finally:
        con.close()


def export_chunks_jsonl(db_path: str | Path, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT c.id AS chunk_id, c.source_id, c.chunk_index, c.title, c.text, c.materia, c.topics_json,
                   d.original_url AS url, d.published_at, d.acquired_at, d.hash_sha256, d.metadata_json
            FROM official_chunks c
            JOIN official_documents d ON d.id = c.document_id
            ORDER BY c.id ASC
            """
        ).fetchall()
        with output.open("w", encoding="utf-8") as f:
            for row in rows:
                item: dict[str, Any] = dict(row)
                try:
                    item["topics"] = json.loads(item.pop("topics_json") or "[]")
                except Exception:
                    item["topics"] = []
                try:
                    item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
                except Exception:
                    item["metadata"] = {}
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return output
    finally:
        con.close()
