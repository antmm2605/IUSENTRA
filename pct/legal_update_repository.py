from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from pct.postgres_runtime_support import PostgresRepositoryBackend

SCHEMA_LEGAL_UPDATE_PIPELINE = Path(__file__).with_name("sql") / "20260418_legal_update_pipeline.sql"
POSTGRES_SCHEMA_LEGAL_UPDATE_PIPELINE = (
    Path(__file__).with_name("sql") / "20260419_legal_update_pipeline_postgres.sql"
)

DEFAULT_MATTERS: tuple[dict[str, Any], ...] = (
    {"name": "Diritto civile", "slug": "diritto_civile", "parent_slug": "", "level": 1, "sort_order": 10},
    {"name": "Diritto penale", "slug": "diritto_penale", "parent_slug": "", "level": 1, "sort_order": 20},
    {"name": "Diritto del lavoro", "slug": "diritto_lavoro", "parent_slug": "", "level": 1, "sort_order": 30},
    {"name": "Diritto tributario", "slug": "diritto_tributario", "parent_slug": "", "level": 1, "sort_order": 40},
    {"name": "Diritto amministrativo", "slug": "diritto_amministrativo", "parent_slug": "", "level": 1, "sort_order": 50},
    {"name": "Diritto societario", "slug": "diritto_societario", "parent_slug": "", "level": 1, "sort_order": 60},
    {"name": "Crisi d'impresa", "slug": "diritto_fallimentare_crisi_impresa", "parent_slug": "", "level": 1, "sort_order": 70},
    {"name": "Diritto di famiglia", "slug": "diritto_famiglia", "parent_slug": "", "level": 1, "sort_order": 80},
    {"name": "Diritto immobiliare", "slug": "diritto_immobiliare", "parent_slug": "", "level": 1, "sort_order": 90},
    {"name": "Privacy e protezione dati", "slug": "privacy_protezione_dati", "parent_slug": "", "level": 1, "sort_order": 100},
    {"name": "Appalti e contratti pubblici", "slug": "appalti_contratti_pubblici", "parent_slug": "", "level": 1, "sort_order": 110},
    {"name": "Diritto UE", "slug": "diritto_ue", "parent_slug": "", "level": 1, "sort_order": 120},
    {"name": "Previdenza e assistenza", "slug": "previdenza_assistenza", "parent_slug": "", "level": 1, "sort_order": 130},
    {"name": "Consumatori", "slug": "consumatori", "parent_slug": "", "level": 1, "sort_order": 140},
    {"name": "Ambiente ed energia", "slug": "ambiente_energia", "parent_slug": "", "level": 1, "sort_order": 150},
    {"name": "Sanita", "slug": "sanita", "parent_slug": "", "level": 1, "sort_order": 160},
    {"name": "Edilizia e urbanistica", "slug": "edilizia_urbanistica", "parent_slug": "", "level": 1, "sort_order": 170},
    {"name": "Trasporti", "slug": "trasporti", "parent_slug": "", "level": 1, "sort_order": 180},
    {"name": "Scuola e universita", "slug": "scuola_universita", "parent_slug": "", "level": 1, "sort_order": 190},
    {"name": "Pubblico impiego", "slug": "pubblico_impiego", "parent_slug": "", "level": 1, "sort_order": 200},
    {"name": "Contratti", "slug": "contratti", "parent_slug": "diritto_civile", "level": 2, "sort_order": 210},
    {"name": "Responsabilita civile", "slug": "responsabilita_civile", "parent_slug": "diritto_civile", "level": 2, "sort_order": 220},
    {"name": "Locazioni", "slug": "locazioni", "parent_slug": "diritto_immobiliare", "level": 2, "sort_order": 230},
    {"name": "Licenziamenti", "slug": "licenziamenti", "parent_slug": "diritto_lavoro", "level": 2, "sort_order": 240},
    {"name": "Sicurezza sul lavoro", "slug": "sicurezza_sul_lavoro", "parent_slug": "diritto_lavoro", "level": 2, "sort_order": 250},
    {"name": "IVA", "slug": "iva", "parent_slug": "diritto_tributario", "level": 2, "sort_order": 260},
    {"name": "Accertamento", "slug": "accertamento", "parent_slug": "diritto_tributario", "level": 2, "sort_order": 270},
    {"name": "Riscossione", "slug": "riscossione", "parent_slug": "diritto_tributario", "level": 2, "sort_order": 280},
    {"name": "Processo amministrativo", "slug": "processo_amministrativo", "parent_slug": "diritto_amministrativo", "level": 2, "sort_order": 290},
    {"name": "GDPR", "slug": "gdpr", "parent_slug": "privacy_protezione_dati", "level": 2, "sort_order": 300},
    {"name": "Data breach", "slug": "data_breach", "parent_slug": "privacy_protezione_dati", "level": 2, "sort_order": 310},
    {"name": "Appalti sotto soglia", "slug": "appalti_sotto_soglia", "parent_slug": "appalti_contratti_pubblici", "level": 2, "sort_order": 320},
    {"name": "Appalti sopra soglia", "slug": "appalti_sopra_soglia", "parent_slug": "appalti_contratti_pubblici", "level": 2, "sort_order": 330},
    {"name": "Concordato", "slug": "concordato", "parent_slug": "diritto_fallimentare_crisi_impresa", "level": 2, "sort_order": 340},
    {"name": "Composizione negoziata", "slug": "composizione_negoziata", "parent_slug": "diritto_fallimentare_crisi_impresa", "level": 2, "sort_order": 350},
    {"name": "Esecuzione penale", "slug": "esecuzione_penale", "parent_slug": "diritto_penale", "level": 2, "sort_order": 360},
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_token(value: Any) -> str:
    return _clean_spaces(value).lower()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_load(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _slugify(value: str) -> str:
    text = _normalize_token(value)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "record"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _sha1(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()


def derive_legal_updates_db_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_updates.db"))


def derive_legal_updates_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_updates_repository.json"))


@dataclass(frozen=True)
class LegalUpdateDbConfig:
    db_path: str
    json_path: str

    @classmethod
    def from_anchor(cls, intelligence_db_path: str) -> "LegalUpdateDbConfig":
        return cls(
            db_path=derive_legal_updates_db_path(intelligence_db_path),
            json_path=derive_legal_updates_json_path(intelligence_db_path),
        )


class LegalUpdateRepository:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str = "",
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.json_path = str(json_path or "").strip()
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(
            postgres_schema_path or POSTGRES_SCHEMA_LEGAL_UPDATE_PIPELINE
        )
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self.audit_table = "legal_update_audit_log" if self.postgres_dsn else "audit_log"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()
        self.seed_matters()

    def _connect(self):
        if self._postgres_backend is not None:
            return self._postgres_backend.connection()
        target = Path(self.db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        schema = (
            self.postgres_schema_path.read_text(encoding="utf-8")
            if self._postgres_backend is not None
            else SCHEMA_LEGAL_UPDATE_PIPELINE.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def _set_meta(self, conn: Any, key: str, value: Any) -> None:
        conn.execute(
            """
            INSERT INTO legal_update_meta (meta_key, meta_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value = excluded.meta_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (_clean_spaces(key), _clean_spaces(value)),
        )

    def _insert_and_get_id(self, conn: Any, sql: str, params: tuple[Any, ...]) -> int:
        statement = str(sql or "").strip().rstrip(";")
        if self._postgres_backend is not None:
            row = conn.execute(f"{statement} RETURNING id", params).fetchone()
            if row is None:
                raise RuntimeError("Inserimento PostgreSQL senza id restituito.")
            if isinstance(row, dict):
                return int(row.get("id") or next(iter(row.values()), 0) or 0)
            return int((row or [0])[0] or 0)
        cursor = conn.execute(statement, params)
        return int(cursor.lastrowid)

    def _decode_row(self, row: sqlite3.Row | None, *, json_fields: Iterable[str] = ()) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = dict(row)
        for field in json_fields:
            payload[field] = _json_load(payload.get(field), [] if field.endswith("_json") and "entities" not in field and "payload" not in field else {})
        return payload

    def _matter_id(self, conn: Any, slug: str) -> int | None:
        if not slug:
            return None
        row = conn.execute("SELECT id FROM matters WHERE slug = ?", (_normalize_token(slug),)).fetchone()
        return int(row["id"]) if row else None

    def seed_matters(self) -> None:
        with self._connect() as conn:
            for row in DEFAULT_MATTERS:
                parent_id = self._matter_id(conn, str(row.get("parent_slug") or ""))
                conn.execute(
                    """
                    INSERT INTO matters (name, slug, parent_id, level, sort_order, enabled)
                    VALUES (?, ?, ?, ?, ?, 1)
                    ON CONFLICT(slug) DO UPDATE SET
                        name = excluded.name,
                        parent_id = excluded.parent_id,
                        level = excluded.level,
                        sort_order = excluded.sort_order,
                        enabled = 1
                    """,
                    (
                        row["name"],
                        _normalize_token(row["slug"]),
                        parent_id,
                        int(row["level"]),
                        int(row["sort_order"]),
                    ),
                )
            conn.commit()

    def list_matters(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.name, m.slug, m.parent_id, m.level, m.sort_order, m.enabled,
                       p.slug AS parent_slug
                FROM matters m
                LEFT JOIN matters p ON p.id = m.parent_id
                WHERE m.enabled = 1
                ORDER BY m.sort_order, m.name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_sources(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._connect() as conn:
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO sources (
                        name, code, category, base_url, source_type, trust_class,
                        is_official, enabled, polling_minutes, parser_type, notes,
                        last_check_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(code) DO UPDATE SET
                        name = excluded.name,
                        category = excluded.category,
                        base_url = excluded.base_url,
                        source_type = excluded.source_type,
                        trust_class = excluded.trust_class,
                        is_official = excluded.is_official,
                        enabled = excluded.enabled,
                        polling_minutes = excluded.polling_minutes,
                        parser_type = excluded.parser_type,
                        notes = excluded.notes,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        _clean_spaces(row.get("name")),
                        _normalize_token(row.get("code")),
                        _normalize_token(row.get("category")),
                        _clean_spaces(row.get("base_url")),
                        _normalize_token(row.get("source_type") or "web"),
                        _normalize_token(row.get("trust_class") or "a").upper(),
                        1 if row.get("is_official", True) else 0,
                        1 if row.get("enabled", True) else 0,
                        int(row.get("polling_minutes") or 240),
                        _normalize_token(row.get("parser_type") or "html"),
                        _clean_spaces(row.get("notes")),
                        _clean_spaces(row.get("last_check_at")),
                    ),
                )
            conn.commit()
        return self.list_sources(enabled_only=False)

    def list_sources(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM sources"
        params: tuple[Any, ...] = ()
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY is_official DESC, category, name"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["is_official"] = bool(payload.get("is_official"))
            payload["enabled"] = bool(payload.get("enabled"))
            result.append(payload)
        return result

    def get_source_by_code(self, code: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE code = ?", (_normalize_token(code),)).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["is_official"] = bool(payload.get("is_official"))
        payload["enabled"] = bool(payload.get("enabled"))
        return payload

    def get_source_by_id(self, source_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (int(source_id),)).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["is_official"] = bool(payload.get("is_official"))
        payload["enabled"] = bool(payload.get("enabled"))
        return payload

    def save_raw_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        external_id = _clean_spaces(payload.get("external_id")) or _sha1(
            f"{payload.get('source_id')}|{payload.get('source_url')}|{payload.get('title')}"
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM source_documents_raw WHERE source_id = ? AND external_id = ?",
                (int(payload["source_id"]), external_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE source_documents_raw
                    SET source_url = ?, title = ?, published_at = ?, raw_html = ?, raw_text = ?,
                        raw_pdf_path = ?, content_hash = ?, fetch_status = ?, http_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        _clean_spaces(payload.get("source_url")),
                        _clean_spaces(payload.get("title")),
                        _clean_spaces(payload.get("published_at")),
                        str(payload.get("raw_html") or ""),
                        str(payload.get("raw_text") or ""),
                        _clean_spaces(payload.get("raw_pdf_path")),
                        _clean_spaces(payload.get("content_hash")),
                        _normalize_token(payload.get("fetch_status") or "fetched"),
                        int(payload.get("http_status") or 0),
                        int(existing["id"]),
                    ),
                )
                raw_id = int(existing["id"])
            else:
                raw_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO source_documents_raw (
                        source_id, external_id, source_url, title, published_at, raw_html, raw_text,
                        raw_pdf_path, content_hash, fetch_status, http_status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(payload["source_id"]),
                        external_id,
                        _clean_spaces(payload.get("source_url")),
                        _clean_spaces(payload.get("title")),
                        _clean_spaces(payload.get("published_at")),
                        str(payload.get("raw_html") or ""),
                        str(payload.get("raw_text") or ""),
                        _clean_spaces(payload.get("raw_pdf_path")),
                        _clean_spaces(payload.get("content_hash")),
                        _normalize_token(payload.get("fetch_status") or "fetched"),
                        int(payload.get("http_status") or 0),
                    ),
                )
            conn.execute(
                "UPDATE sources SET last_check_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (_now_iso(), int(payload["source_id"])),
            )
            conn.commit()
        return self.get_raw_document(raw_id) or {}

    def get_raw_document(self, raw_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.*, s.code AS source_code, s.name AS source_name, s.category AS source_category
                FROM source_documents_raw r
                JOIN sources s ON s.id = r.source_id
                WHERE r.id = ?
                """,
                (int(raw_document_id),),
            ).fetchone()
        return dict(row) if row else None

    def get_raw_document_by_external(self, source_id: int, external_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_documents_raw WHERE source_id = ? AND external_id = ?",
                (int(source_id), _clean_spaces(external_id)),
            ).fetchone()
        return dict(row) if row else None

    def list_raw_documents(
        self,
        *,
        source_code: str = "",
        classification_type: str = "",
        status: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if source_code:
            clauses.append("s.code = ?")
            params.append(_normalize_token(source_code))
        if classification_type:
            clauses.append("a.classification_type = ?")
            params.append(_normalize_token(classification_type).upper())
        if status:
            clauses.append("q.status = ?")
            params.append(_normalize_token(status))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT r.id, r.source_id, r.external_id, r.source_url, r.title, r.published_at,
                       r.fetch_status, r.http_status, r.content_hash, r.created_at, r.updated_at,
                       s.code AS source_code, s.name AS source_name, s.category AS source_category,
                       n.id AS normalized_document_id, n.body_short, n.document_date,
                       a.id AS analysis_id, a.classification_type, a.confidence_score, a.proposed_action,
                       q.id AS review_id, q.status AS review_status, q.priority AS review_priority
                FROM source_documents_raw r
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN source_documents_normalized n ON n.raw_document_id = r.id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = n.id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                {where}
                ORDER BY COALESCE(NULLIF(r.published_at, ''), r.created_at) DESC, r.id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_staging_document(self, raw_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.id, r.source_id, r.external_id, r.source_url, r.title, r.published_at,
                       r.raw_html, r.raw_text, r.raw_pdf_path, r.content_hash, r.fetch_status,
                       r.http_status, r.created_at, r.updated_at,
                       s.code AS source_code, s.name AS source_name, s.category AS source_category,
                       s.trust_class, s.is_official,
                       n.id AS normalized_document_id, n.title AS normalized_title, n.body_text, n.body_short,
                       n.language, n.issuer, n.document_date, n.document_type_guess, n.attachments_json,
                       a.id AS analysis_id, a.classification_type, a.confidence_score, a.impact_level,
                       a.norm_type, a.norm_number, a.norm_year, a.decision_number, a.decision_year,
                       a.court_name, a.effective_date, a.summary_short, a.summary_long, a.what_changes,
                       a.extracted_entities_json, a.proposed_action, a.target_entity_type, a.target_entity_id,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       q.id AS review_id, q.status AS review_status, q.priority AS review_priority,
                       q.review_notes, q.reviewed_by, q.reviewed_at, q.proposal_payload_json
                FROM source_documents_raw r
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN source_documents_normalized n ON n.raw_document_id = r.id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = n.id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                WHERE r.id = ?
                """,
                (int(raw_document_id),),
            ).fetchone()
        return self._decode_row(
            row,
            json_fields=("attachments_json", "extracted_entities_json", "proposal_payload_json"),
        )

    def save_normalized_document(self, raw_document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM source_documents_normalized WHERE raw_document_id = ?",
                (int(raw_document_id),),
            ).fetchone()
            params = (
                int(raw_document_id),
                _clean_spaces(payload.get("title")),
                str(payload.get("body_text") or ""),
                _clean_spaces(payload.get("body_short")),
                _normalize_token(payload.get("language") or "it"),
                _clean_spaces(payload.get("issuer")),
                _clean_spaces(payload.get("document_date")),
                _normalize_token(payload.get("document_type_guess")),
                _json_dump(payload.get("attachments_json") or []),
                _clean_spaces(payload.get("normalized_hash")),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE source_documents_normalized
                    SET title = ?, body_text = ?, body_short = ?, language = ?, issuer = ?,
                        document_date = ?, document_type_guess = ?, attachments_json = ?,
                        normalized_hash = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE raw_document_id = ?
                    """,
                    params[1:] + (int(raw_document_id),),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO source_documents_normalized (
                        raw_document_id, title, body_text, body_short, language, issuer,
                        document_date, document_type_guess, attachments_json, normalized_hash,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
            conn.commit()
        return self.get_normalized_by_raw(raw_document_id) or {}

    def get_normalized_by_raw(self, raw_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, r.source_id, r.source_url, r.external_id, r.published_at, r.title AS raw_title
                FROM source_documents_normalized n
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                WHERE n.raw_document_id = ?
                """,
                (int(raw_document_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("attachments_json",))

    def save_analysis(self, normalized_document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM ai_documents_analysis WHERE normalized_document_id = ?",
                (int(normalized_document_id),),
            ).fetchone()
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            params = (
                int(normalized_document_id),
                _normalize_token(payload.get("classification_type") or "INCERTO").upper(),
                float(payload.get("confidence_score") or 0),
                _normalize_token(payload.get("impact_level") or "medio"),
                matter_id,
                submatter_id,
                _clean_spaces(payload.get("issuer")),
                _clean_spaces(payload.get("norm_number")),
                _clean_spaces(payload.get("norm_year")),
                _normalize_token(payload.get("norm_type")),
                _clean_spaces(payload.get("decision_number")),
                _clean_spaces(payload.get("decision_year")),
                _clean_spaces(payload.get("court_name")),
                _clean_spaces(payload.get("effective_date")),
                _clean_spaces(payload.get("summary_short")),
                str(payload.get("summary_long") or ""),
                str(payload.get("what_changes") or ""),
                _json_dump(payload.get("extracted_entities_json") or {}),
                _normalize_token(payload.get("proposed_action") or "needs_review").upper(),
                _normalize_token(payload.get("target_entity_type") or ""),
                payload.get("target_entity_id"),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE ai_documents_analysis
                    SET classification_type = ?, confidence_score = ?, impact_level = ?, matter_id = ?,
                        submatter_id = ?, issuer = ?, norm_number = ?, norm_year = ?, norm_type = ?,
                        decision_number = ?, decision_year = ?, court_name = ?, effective_date = ?,
                        summary_short = ?, summary_long = ?, what_changes = ?, extracted_entities_json = ?,
                        proposed_action = ?, target_entity_type = ?, target_entity_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE normalized_document_id = ?
                    """,
                    params[1:] + (int(normalized_document_id),),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ai_documents_analysis (
                        normalized_document_id, classification_type, confidence_score, impact_level,
                        matter_id, submatter_id, issuer, norm_number, norm_year, norm_type,
                        decision_number, decision_year, court_name, effective_date, summary_short,
                        summary_long, what_changes, extracted_entities_json, proposed_action,
                        target_entity_type, target_entity_id, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
            conn.commit()
        return self.get_analysis_by_normalized(normalized_document_id) or {}

    def get_analysis_by_normalized(self, normalized_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT a.*,
                       m.slug AS matter_slug,
                       m.name AS matter_name,
                       sm.slug AS submatter_slug,
                       sm.name AS submatter_name
                FROM ai_documents_analysis a
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                WHERE a.normalized_document_id = ?
                """,
                (int(normalized_document_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("extracted_entities_json",))

    def list_analyses(
        self,
        *,
        classification_type: str = "",
        matter_slug: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if classification_type:
            clauses.append("a.classification_type = ?")
            params.append(_normalize_token(classification_type).upper())
        if matter_slug:
            clauses.append("m.slug = ?")
            params.append(_normalize_token(matter_slug))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT a.*,
                       n.title, n.document_date, n.issuer, n.body_short,
                       r.id AS raw_document_id, r.source_url, r.published_at,
                       s.code AS source_code, s.name AS source_name,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       q.id AS review_id, q.status AS review_status
                FROM ai_documents_analysis a
                JOIN source_documents_normalized n ON n.id = a.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                {where}
                ORDER BY a.updated_at DESC, a.id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._decode_row(row, json_fields=("extracted_entities_json",)) or {} for row in rows]

    def get_analysis(self, analysis_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT a.*,
                       n.id AS normalized_document_id, n.title, n.document_date, n.issuer, n.body_text, n.body_short,
                       r.id AS raw_document_id, r.source_url, r.published_at,
                       s.code AS source_code, s.name AS source_name, s.category AS source_category,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       q.id AS review_id, q.status AS review_status, q.priority AS review_priority
                FROM ai_documents_analysis a
                JOIN source_documents_normalized n ON n.id = a.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                WHERE a.id = ?
                """,
                (int(analysis_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("extracted_entities_json",))

    def find_normative_match(self, norm_type: str, norm_number: str, norm_year: str, issuer: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM normative
                WHERE norm_type = ? AND norm_number = ? AND norm_year = ? AND issuer = ?
                """,
                (
                    _normalize_token(norm_type),
                    _clean_spaces(norm_number),
                    _clean_spaces(norm_year),
                    _clean_spaces(issuer),
                ),
            ).fetchone()
        return dict(row) if row else None

    def find_jurisprudence_match(self, court_name: str, decision_number: str, decision_year: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM jurisprudence
                WHERE court_name = ? AND decision_number = ? AND decision_year = ?
                """,
                (
                    _clean_spaces(court_name),
                    _clean_spaces(decision_number),
                    _clean_spaces(decision_year),
                ),
            ).fetchone()
        return dict(row) if row else None

    def find_prassi_match(self, issuing_body: str, act_type: str, act_number: str, act_year: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM prassi
                WHERE issuing_body = ? AND act_type = ? AND act_number = ? AND act_year = ?
                """,
                (
                    _clean_spaces(issuing_body),
                    _normalize_token(act_type),
                    _clean_spaces(act_number),
                    _clean_spaces(act_year),
                ),
            ).fetchone()
        return dict(row) if row else None

    def upsert_review_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, status FROM review_queue WHERE analysis_id = ?",
                (int(payload["analysis_id"]),),
            ).fetchone()
            params = (
                int(payload["normalized_document_id"]),
                int(payload["analysis_id"]),
                _normalize_token(payload.get("proposal_type") or ""),
                _normalize_token(payload.get("proposed_action") or "").upper(),
                _normalize_token(payload.get("target_entity_type") or ""),
                payload.get("target_entity_id"),
                _json_dump(payload.get("proposal_payload_json") or {}),
                _normalize_token(payload.get("status") or "pending"),
                int(payload.get("priority") or 50),
                _clean_spaces(payload.get("assigned_to")),
                _clean_spaces(payload.get("review_notes")),
                _clean_spaces(payload.get("reviewed_by")),
                _clean_spaces(payload.get("reviewed_at")),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE review_queue
                    SET proposal_type = ?, proposed_action = ?, target_entity_type = ?, target_entity_id = ?,
                        proposal_payload_json = ?, status = ?, priority = ?, assigned_to = ?,
                        review_notes = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE analysis_id = ?
                    """,
                    params[2:] + (int(payload["analysis_id"]),),
                )
                review_id = int(existing["id"])
            else:
                review_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO review_queue (
                        normalized_document_id, analysis_id, proposal_type, proposed_action,
                        target_entity_type, target_entity_id, proposal_payload_json, status,
                        priority, assigned_to, review_notes, reviewed_by, reviewed_at,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
            conn.commit()
        return self.get_review_item(review_id) or {}

    def list_review_queue(self, *, statuses: tuple[str, ...] = (), limit: int = 100) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if statuses:
            where = "WHERE q.status IN ({})".format(",".join("?" for _ in statuses))
            params.extend(_normalize_token(status) for status in statuses)
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT q.*, a.classification_type, a.confidence_score, a.summary_short,
                       a.proposed_action AS analysis_proposed_action,
                       n.title, n.document_date, s.name AS source_name, s.code AS source_code,
                       m.name AS matter_name, sm.name AS submatter_name
                FROM review_queue q
                JOIN ai_documents_analysis a ON a.id = q.analysis_id
                JOIN source_documents_normalized n ON n.id = q.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                {where}
                ORDER BY q.status = 'pending' DESC, q.priority DESC, q.created_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._decode_row(row, json_fields=("proposal_payload_json",)) or {} for row in rows]

    def get_review_item(self, review_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT q.*,
                       a.classification_type, a.confidence_score, a.impact_level, a.summary_short,
                       a.summary_long, a.what_changes, a.proposed_action AS analysis_proposed_action, a.target_entity_type,
                       a.target_entity_id, a.extracted_entities_json, a.issuer AS analysis_issuer,
                       a.norm_type, a.norm_number, a.norm_year, a.decision_number, a.decision_year,
                       a.court_name, a.effective_date,
                       n.title, n.body_short, n.body_text, n.document_date, n.issuer,
                       r.source_url, r.published_at, r.external_id,
                       s.name AS source_name, s.code AS source_code, s.category AS source_category,
                       s.trust_class, s.is_official,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM review_queue q
                JOIN ai_documents_analysis a ON a.id = q.analysis_id
                JOIN source_documents_normalized n ON n.id = q.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                WHERE q.id = ?
                """,
                (int(review_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("proposal_payload_json", "extracted_entities_json"))

    def set_review_status(
        self,
        review_id: int,
        status: str,
        *,
        reviewer: str = "",
        notes: str = "",
        assigned_to: str = "",
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_queue
                SET status = ?, reviewed_by = ?, reviewed_at = ?, review_notes = ?,
                    assigned_to = CASE WHEN ? <> '' THEN ? ELSE assigned_to END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    _normalize_token(status),
                    _clean_spaces(reviewer),
                    _now_iso(),
                    _clean_spaces(notes),
                    _clean_spaces(assigned_to),
                    _clean_spaces(assigned_to),
                    int(review_id),
                ),
            )
            conn.commit()
        return self.get_review_item(review_id)

    def assign_review(self, review_id: int, *, assigned_to: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_queue
                SET assigned_to = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (_clean_spaces(assigned_to), int(review_id)),
            )
            conn.commit()
        return self.get_review_item(review_id)

    def record_audit(self, entity_type: str, entity_id: int | None, action: str, old_data: Any, new_data: Any, performed_by: str) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.audit_table} (
                    entity_type, entity_id, action, old_data_json, new_data_json, performed_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    _normalize_token(entity_type),
                    entity_id,
                    _normalize_token(action),
                    _json_dump(old_data or {}),
                    _json_dump(new_data or {}),
                    _clean_spaces(performed_by),
                ),
            )
            conn.commit()

    def create_or_update_normative(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            existing = conn.execute(
                """
                SELECT * FROM normative
                WHERE norm_type = ? AND norm_number = ? AND norm_year = ? AND issuer = ?
                """,
                (
                    _normalize_token(payload.get("norm_type")),
                    _clean_spaces(payload.get("norm_number")),
                    _clean_spaces(payload.get("norm_year")),
                    _clean_spaces(payload.get("issuer")),
                ),
            ).fetchone()
            version_group_id = _slugify(
                f"{payload.get('norm_type')}-{payload.get('norm_number')}-{payload.get('norm_year')}-{payload.get('issuer')}"
            )
            source_document_id = payload.get("source_document_id")
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE normative
                    SET title = ?, slug = ?, publication_date = ?, effective_date = ?, status = ?,
                        matter_id = ?, submatter_id = ?, source_url = ?, source_document_id = ?,
                        text_official = ?, text_current = ?, summary = ?, notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        _clean_spaces(payload.get("title")),
                        _slugify(str(payload.get("slug") or payload.get("title"))),
                        _clean_spaces(payload.get("publication_date")),
                        _clean_spaces(payload.get("effective_date")),
                        _normalize_token(payload.get("status") or "vigente"),
                        matter_id,
                        submatter_id,
                        _clean_spaces(payload.get("source_url")),
                        source_document_id,
                        str(payload.get("text_official") or ""),
                        str(payload.get("text_current") or payload.get("text_official") or ""),
                        str(payload.get("summary") or ""),
                        str(payload.get("notes") or ""),
                        int(existing["id"]),
                    ),
                )
                normative_id = int(existing["id"])
                action = "update"
            else:
                normative_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO normative (
                        title, slug, norm_type, norm_number, norm_year, issuer, publication_date,
                        effective_date, status, matter_id, submatter_id, source_url, source_document_id,
                        text_official, text_current, summary, notes, version_group_id, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        _clean_spaces(payload.get("title")),
                        _slugify(str(payload.get("slug") or payload.get("title"))),
                        _normalize_token(payload.get("norm_type")),
                        _clean_spaces(payload.get("norm_number")),
                        _clean_spaces(payload.get("norm_year")),
                        _clean_spaces(payload.get("issuer")),
                        _clean_spaces(payload.get("publication_date")),
                        _clean_spaces(payload.get("effective_date")),
                        _normalize_token(payload.get("status") or "vigente"),
                        matter_id,
                        submatter_id,
                        _clean_spaces(payload.get("source_url")),
                        source_document_id,
                        str(payload.get("text_official") or ""),
                        str(payload.get("text_current") or payload.get("text_official") or ""),
                        str(payload.get("summary") or ""),
                        str(payload.get("notes") or ""),
                        version_group_id,
                    ),
                )
                old_payload = {}
                action = "create"
            conn.execute(
                """
                INSERT INTO normative_versions (
                    normative_id, version_label, valid_from, valid_to, text_version, source_url, source_document_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    normative_id,
                    _clean_spaces(payload.get("version_label") or payload.get("publication_date") or "versione iniziale"),
                    _clean_spaces(payload.get("effective_date") or payload.get("publication_date")),
                    _clean_spaces(payload.get("valid_to")),
                    str(payload.get("text_current") or payload.get("text_official") or ""),
                    _clean_spaces(payload.get("source_url")),
                    source_document_id,
                ),
            )
            conn.commit()
        created = self.get_normative(normative_id) or {}
        self.record_audit("normative", normative_id, action, old_payload, created, performed_by)
        return created

    def get_normative(self, normative_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM normative WHERE id = ?", (int(normative_id),)).fetchone()
        return dict(row) if row else None

    def create_or_update_jurisprudence(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            existing = conn.execute(
                """
                SELECT * FROM jurisprudence
                WHERE court_name = ? AND decision_number = ? AND decision_year = ?
                """,
                (
                    _clean_spaces(payload.get("court_name")),
                    _clean_spaces(payload.get("decision_number")),
                    _clean_spaces(payload.get("decision_year")),
                ),
            ).fetchone()
            params = (
                _clean_spaces(payload.get("title")),
                _slugify(str(payload.get("slug") or payload.get("title"))),
                _clean_spaces(payload.get("court_name")),
                _clean_spaces(payload.get("section_name")),
                _clean_spaces(payload.get("decision_number")),
                _clean_spaces(payload.get("decision_year")),
                _clean_spaces(payload.get("decision_date")),
                _clean_spaces(payload.get("publication_date")),
                matter_id,
                submatter_id,
                str(payload.get("principle_of_law") or ""),
                str(payload.get("summary") or ""),
                str(payload.get("full_text") or ""),
                _clean_spaces(payload.get("source_url")),
                payload.get("source_document_id"),
                payload.get("related_normative_id"),
            )
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE jurisprudence
                    SET title = ?, slug = ?, court_name = ?, section_name = ?, decision_number = ?,
                        decision_year = ?, decision_date = ?, publication_date = ?, matter_id = ?,
                        submatter_id = ?, principle_of_law = ?, summary = ?, full_text = ?, source_url = ?,
                        source_document_id = ?, related_normative_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    params + (int(existing["id"]),),
                )
                entity_id = int(existing["id"])
                action = "update"
            else:
                entity_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO jurisprudence (
                        title, slug, court_name, section_name, decision_number, decision_year,
                        decision_date, publication_date, matter_id, submatter_id, principle_of_law,
                        summary, full_text, source_url, source_document_id, related_normative_id,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
                old_payload = {}
                action = "create"
            conn.commit()
        created = self.get_jurisprudence(entity_id) or {}
        self.record_audit("jurisprudence", entity_id, action, old_payload, created, performed_by)
        return created

    def get_jurisprudence(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jurisprudence WHERE id = ?", (int(entity_id),)).fetchone()
        return dict(row) if row else None

    def create_or_update_prassi(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            existing = conn.execute(
                """
                SELECT * FROM prassi
                WHERE issuing_body = ? AND act_type = ? AND act_number = ? AND act_year = ?
                """,
                (
                    _clean_spaces(payload.get("issuing_body")),
                    _normalize_token(payload.get("act_type")),
                    _clean_spaces(payload.get("act_number")),
                    _clean_spaces(payload.get("act_year")),
                ),
            ).fetchone()
            params = (
                _clean_spaces(payload.get("title")),
                _slugify(str(payload.get("slug") or payload.get("title"))),
                _clean_spaces(payload.get("issuing_body")),
                _normalize_token(payload.get("act_type")),
                _clean_spaces(payload.get("act_number")),
                _clean_spaces(payload.get("act_year")),
                _clean_spaces(payload.get("act_date")),
                matter_id,
                submatter_id,
                str(payload.get("summary") or ""),
                str(payload.get("full_text") or ""),
                _clean_spaces(payload.get("source_url")),
                payload.get("source_document_id"),
            )
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE prassi
                    SET title = ?, slug = ?, issuing_body = ?, act_type = ?, act_number = ?, act_year = ?,
                        act_date = ?, matter_id = ?, submatter_id = ?, summary = ?, full_text = ?,
                        source_url = ?, source_document_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    params + (int(existing["id"]),),
                )
                entity_id = int(existing["id"])
                action = "update"
            else:
                entity_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO prassi (
                        title, slug, issuing_body, act_type, act_number, act_year, act_date,
                        matter_id, submatter_id, summary, full_text, source_url, source_document_id,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
                old_payload = {}
                action = "create"
            conn.commit()
        created = self.get_prassi(entity_id) or {}
        self.record_audit("prassi", entity_id, action, old_payload, created, performed_by)
        return created

    def get_prassi(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM prassi WHERE id = ?", (int(entity_id),)).fetchone()
        return dict(row) if row else None

    def create_or_update_news(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        slug = _slugify(str(payload.get("slug") or payload.get("title")))
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            existing = conn.execute(
                """
                SELECT * FROM news
                WHERE slug = ? OR (source_document_id = ? AND news_type = ?)
                """,
                (
                    slug,
                    payload.get("source_document_id"),
                    _normalize_token(payload.get("news_type") or "focus"),
                ),
            ).fetchone()
            params = (
                _clean_spaces(payload.get("title")),
                slug,
                str(payload.get("short_summary") or ""),
                str(payload.get("content") or ""),
                _normalize_token(payload.get("news_type") or "focus"),
                matter_id,
                submatter_id,
                payload.get("related_normative_id"),
                payload.get("related_jurisprudence_id"),
                payload.get("related_prassi_id"),
                _clean_spaces(payload.get("source_url")),
                payload.get("source_document_id"),
                1 if payload.get("is_auto_generated", True) else 0,
                _normalize_token(payload.get("publication_status") or "published"),
                _clean_spaces(payload.get("published_at") or _now_iso()),
            )
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE news
                    SET title = ?, slug = ?, short_summary = ?, content = ?, news_type = ?,
                        matter_id = ?, submatter_id = ?, related_normative_id = ?, related_jurisprudence_id = ?,
                        related_prassi_id = ?, source_url = ?, source_document_id = ?, is_auto_generated = ?,
                        publication_status = ?, published_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    params + (int(existing["id"]),),
                )
                entity_id = int(existing["id"])
                action = "update"
            else:
                entity_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO news (
                        title, slug, short_summary, content, news_type, matter_id, submatter_id,
                        related_normative_id, related_jurisprudence_id, related_prassi_id, source_url,
                        source_document_id, is_auto_generated, publication_status, published_at,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
                old_payload = {}
                action = "create"
            conn.commit()
        created = self.get_news(entity_id) or {}
        self.record_audit("news", entity_id, action, old_payload, created, performed_by)
        return created

    def get_news(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE n.id = ?
                """,
                (int(entity_id),),
            ).fetchone()
        return dict(row) if row else None

    def get_news_by_slug(self, slug: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE n.slug = ? AND n.publication_status = 'published'
                """,
                (_slugify(slug),),
            ).fetchone()
        return dict(row) if row else None

    def get_news_detail(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE n.id = ?
                """,
                (int(entity_id),),
            ).fetchone()
        return dict(row) if row else None

    def list_news(
        self,
        *,
        matter_slug: str = "",
        news_type: str = "",
        limit: int = 50,
        include_drafts: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if not include_drafts:
            clauses.append("n.publication_status = 'published'")
        if matter_slug:
            clauses.append("m.slug = ?")
            params.append(_normalize_token(matter_slug))
        if news_type:
            clauses.append("n.news_type = ?")
            params.append(_normalize_token(news_type))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                {where}
                ORDER BY COALESCE(NULLIF(n.published_at, ''), n.created_at) DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_published_normative(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT n.*, m.name AS matter_name, sm.name AS submatter_name
                FROM normative n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                ORDER BY COALESCE(NULLIF(n.effective_date, ''), n.publication_date, n.created_at) DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_normative_versions(self, normative_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM normative_versions
                WHERE normative_id = ?
                ORDER BY COALESCE(NULLIF(valid_from, ''), created_at) DESC, id DESC
                """,
                (int(normative_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_published_jurisprudence(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT j.*, m.name AS matter_name, sm.name AS submatter_name
                FROM jurisprudence j
                LEFT JOIN matters m ON m.id = j.matter_id
                LEFT JOIN matters sm ON sm.id = j.submatter_id
                ORDER BY COALESCE(NULLIF(j.publication_date, ''), j.decision_date, j.created_at) DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_published_prassi(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.*, m.name AS matter_name, sm.name AS submatter_name
                FROM prassi p
                LEFT JOIN matters m ON m.id = p.matter_id
                LEFT JOIN matters sm ON sm.id = p.submatter_id
                ORDER BY COALESCE(NULLIF(p.act_date, ''), p.created_at) DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_audit(self, *, entity_type: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if entity_type:
            clauses.append("entity_type = ?")
            params.append(_normalize_token(entity_type))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM {self.audit_table}
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._decode_row(row, json_fields=("old_data_json", "new_data_json")) or {} for row in rows]

    def dashboard_snapshot(self) -> dict[str, Any]:
        with self._connect() as conn:
            counts = {
                "sources": int(conn.execute("SELECT COUNT(*) FROM sources WHERE enabled = 1").fetchone()[0]),
                "raw_documents": int(conn.execute("SELECT COUNT(*) FROM source_documents_raw").fetchone()[0]),
                "normalized_documents": int(conn.execute("SELECT COUNT(*) FROM source_documents_normalized").fetchone()[0]),
                "analyses": int(conn.execute("SELECT COUNT(*) FROM ai_documents_analysis").fetchone()[0]),
                "review_pending": int(conn.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'pending'").fetchone()[0]),
                "review_approved": int(conn.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'approved'").fetchone()[0]),
                "published_news": int(conn.execute("SELECT COUNT(*) FROM news WHERE publication_status = 'published'").fetchone()[0]),
                "published_normative": int(conn.execute("SELECT COUNT(*) FROM normative").fetchone()[0]),
                "published_jurisprudence": int(conn.execute("SELECT COUNT(*) FROM jurisprudence").fetchone()[0]),
                "published_prassi": int(conn.execute("SELECT COUNT(*) FROM prassi").fetchone()[0]),
            }
            latest_audit = conn.execute(
                f"SELECT created_at, action, entity_type, entity_id, performed_by FROM {self.audit_table} ORDER BY id DESC LIMIT 12"
            ).fetchall()
        return {
            "headline": counts,
            "sources": self.list_sources(enabled_only=False),
            "review_queue": self.list_review_queue(limit=20),
            "news": self.list_news(limit=8, include_drafts=False),
            "normative": self.list_published_normative(limit=8),
            "jurisprudence": self.list_published_jurisprudence(limit=8),
            "prassi": self.list_published_prassi(limit=8),
            "audit": [dict(row) for row in latest_audit],
        }

    def export_repository_json(self) -> str:
        if not self.json_path:
            return ""
        target = Path(self.json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.dashboard_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)
