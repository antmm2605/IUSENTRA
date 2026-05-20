"""Repository PostgreSQL per la coverage pipeline e i draft spec v2."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping

try:
    import psycopg2
    import psycopg2.extras
    _HAS_PSYCOPG2 = True
except ImportError:
    psycopg2 = None  # type: ignore[assignment]
    _HAS_PSYCOPG2 = False

from pct.legal_platform_seed import LEGAL_PLATFORM_SEED
from pct.legal_coverage_review_audit import build_review_diff
from pct.legal_coverage_sqlite_repository import assert_no_procedure_lifecycle_sql_bypass


TAXONOMY_SCHEMA_SQL = Path(__file__).with_name("sql") / "20260417_legal_taxonomy_operational_tables.sql"
COVERAGE_SCHEMA_SQL = Path(__file__).with_name("sql") / "20260417_legal_coverage_pipeline.sql"


@dataclass(frozen=True)
class CoverageDbConfig:
    dsn: str = ""
    host: str = "localhost"
    port: int = 5432
    dbname: str = "iusentra"
    user: str = "postgres"
    password: str = "postgres"
    explicit: bool = False

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None = None) -> "CoverageDbConfig":
        cfg = dict(mapping or {})
        explicit = any(
            value not in (None, "")
            for value in (
                cfg.get("LEGAL_COVERAGE_DB_URL"),
                cfg.get("PCT_LEGAL_COVERAGE_DB_URL"),
                cfg.get("LEGAL_COVERAGE_DB_HOST"),
                cfg.get("PCT_LEGAL_COVERAGE_DB_HOST"),
                cfg.get("LEGAL_COVERAGE_DB_NAME"),
                cfg.get("PCT_LEGAL_COVERAGE_DB_NAME"),
                os.getenv("LEGAL_COVERAGE_DB_URL"),
                os.getenv("PCT_LEGAL_COVERAGE_DB_URL"),
                os.getenv("LEGAL_COVERAGE_DB_HOST"),
                os.getenv("PCT_LEGAL_COVERAGE_DB_HOST"),
                os.getenv("LEGAL_COVERAGE_DB_NAME"),
                os.getenv("PCT_LEGAL_COVERAGE_DB_NAME"),
            )
        )
        return cls(
            dsn=str(
                cfg.get("LEGAL_COVERAGE_DB_URL")
                or cfg.get("PCT_LEGAL_COVERAGE_DB_URL")
                or os.getenv("LEGAL_COVERAGE_DB_URL")
                or os.getenv("PCT_LEGAL_COVERAGE_DB_URL")
                or ""
            ).strip(),
            host=str(
                cfg.get("LEGAL_COVERAGE_DB_HOST")
                or cfg.get("PCT_LEGAL_COVERAGE_DB_HOST")
                or os.getenv("LEGAL_COVERAGE_DB_HOST")
                or os.getenv("PCT_LEGAL_COVERAGE_DB_HOST")
                or "localhost"
            ).strip(),
            port=int(
                cfg.get("LEGAL_COVERAGE_DB_PORT")
                or cfg.get("PCT_LEGAL_COVERAGE_DB_PORT")
                or os.getenv("LEGAL_COVERAGE_DB_PORT")
                or os.getenv("PCT_LEGAL_COVERAGE_DB_PORT")
                or 5432
            ),
            dbname=str(
                cfg.get("LEGAL_COVERAGE_DB_NAME")
                or cfg.get("PCT_LEGAL_COVERAGE_DB_NAME")
                or os.getenv("LEGAL_COVERAGE_DB_NAME")
                or os.getenv("PCT_LEGAL_COVERAGE_DB_NAME")
                or "iusentra"
            ).strip(),
            user=str(
                cfg.get("LEGAL_COVERAGE_DB_USER")
                or cfg.get("PCT_LEGAL_COVERAGE_DB_USER")
                or os.getenv("LEGAL_COVERAGE_DB_USER")
                or os.getenv("PCT_LEGAL_COVERAGE_DB_USER")
                or "postgres"
            ).strip(),
            password=str(
                cfg.get("LEGAL_COVERAGE_DB_PASSWORD")
                or cfg.get("PCT_LEGAL_COVERAGE_DB_PASSWORD")
                or os.getenv("LEGAL_COVERAGE_DB_PASSWORD")
                or os.getenv("PCT_LEGAL_COVERAGE_DB_PASSWORD")
                or "postgres"
            ),
            explicit=explicit,
        )

    @property
    def configured(self) -> bool:
        return bool(self.explicit)


class PostgresCoverageRepository:
    """Accesso PostgreSQL alla pipeline di coverage e review."""

    def __init__(self, config: CoverageDbConfig):
        self.config = config

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if not _HAS_PSYCOPG2:
            raise RuntimeError(
                "psycopg2 non disponibile: installa psycopg2-binary per usare la funzionalità PostgreSQL."
            )
        kwargs: dict[str, Any] = {"cursor_factory": psycopg2.extras.RealDictCursor}
        if self.config.dsn:
            conn = psycopg2.connect(self.config.dsn, **kwargs)
        else:
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.dbname,
                user=self.config.user,
                password=self.config.password,
                **kwargs,
            )
        try:
            yield conn
        finally:
            conn.close()

    def _fetch_all(self, conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
        return [dict(row) for row in rows]

    def _fetch_one(self, conn: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return dict(row) if row else None

    def _execute(self, conn: Any, sql: str, params: tuple[Any, ...] = ()) -> None:
        with conn.cursor() as cur:
            cur.execute(sql, params)

    def _execute_script(self, conn: Any, path: Path) -> None:
        self._execute(conn, path.read_text(encoding="utf-8"))

    def table_exists(self, conn: Any, table_name: str) -> bool:
        row = self._fetch_one(conn, "SELECT to_regclass(%s) AS table_name", (table_name,))
        return bool((row or {}).get("table_name"))

    def column_exists(self, conn: Any, table_name: str, column_name: str) -> bool:
        row = self._fetch_one(
            conn,
            """
            SELECT 1 AS ok
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return bool(row)

    def _ensure_review_columns(self, conn: Any) -> None:
        columns = {
            "draft_spec_original_json": "JSONB",
            "review_reason": "TEXT",
            "review_signature": "VARCHAR(255)",
            "review_diff_json": "JSONB NOT NULL DEFAULT '{}'::jsonb",
            "last_review_action": "VARCHAR(32)",
        }
        for column_name, sql_type in columns.items():
            if not self.column_exists(conn, "generated_procedure_drafts", column_name):
                self._execute(
                    conn,
                    f"ALTER TABLE generated_procedure_drafts ADD COLUMN {column_name} {sql_type}",
                )
        self._execute(
            conn,
            """
            UPDATE generated_procedure_drafts
            SET draft_spec_original_json = COALESCE(draft_spec_original_json, spec_json),
                review_diff_json = COALESCE(review_diff_json, '{}'::jsonb)
            """,
        )

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            self._execute_script(conn, TAXONOMY_SCHEMA_SQL)
            self._execute_script(conn, COVERAGE_SCHEMA_SQL)
            self._ensure_review_columns(conn)
            conn.commit()

    def ping(self) -> bool:
        try:
            with self.connect() as conn:
                self._fetch_one(conn, "SELECT 1 AS ok")
            return True
        except Exception:
            return False

    def list_known_subbranches(self) -> list[str]:
        known = {str(row["subbranch_code"]) for row in LEGAL_PLATFORM_SEED}
        with self.connect() as conn:
            if self.table_exists(conn, "legal_subbranch_profiles"):
                rows = self._fetch_all(conn, "SELECT subbranch_code FROM legal_subbranch_profiles")
                known.update(str(row["subbranch_code"]) for row in rows if row.get("subbranch_code"))
            if self.table_exists(conn, "legal_procedures"):
                rows = self._fetch_all(conn, "SELECT DISTINCT subbranch_code FROM legal_procedures")
                known.update(str(row["subbranch_code"]) for row in rows if row.get("subbranch_code"))
        return sorted(known)

    def get_subbranch_metadata(self, subbranch_code: str) -> dict[str, Any]:
        seed_rows = [row for row in LEGAL_PLATFORM_SEED if row["subbranch_code"] == subbranch_code]
        seed_first = seed_rows[0] if seed_rows else {}
        telematic = any(str(row.get("channel_code") or "").upper() in {"PCT_CIVILE", "PDP_PENALE", "PAT_AMMINISTRATIVO", "PTT_TRIBUTARIO", "PORTALE_MINISTERIALE", "SPORTELLO_PA", "PEC_ONLY"} for row in seed_rows)
        metadata = {
            "subbranch_code": subbranch_code,
            "operational_priority": int(seed_first.get("operational_priority") or 50),
            "preset_available": subbranch_code in {"CONSUMATORI_GARANZIE_E_RECESSO", "SUCCESSIONI_DICHIARAZIONE_DI_SUCCESSIONE"},
            "telematic": telematic,
            "specialist_without_preset": bool(seed_rows) and not telematic and str(seed_first.get("complexity_level") or "").upper() in {"HIGH", "SPECIALIST"},
        }
        with self.connect() as conn:
            if self.table_exists(conn, "legal_subbranch_profiles"):
                row = self._fetch_one(
                    conn,
                    """
                    SELECT operational_priority, is_telematic, requires_human_review
                    FROM legal_subbranch_profiles
                    WHERE subbranch_code = %s
                    """,
                    (subbranch_code,),
                )
                if row:
                    metadata["operational_priority"] = int(row.get("operational_priority") or metadata["operational_priority"])
                    metadata["telematic"] = bool(row.get("is_telematic"))
        return metadata

    def get_subbranch_block_state(self, subbranch_code: str) -> dict[str, Any]:
        counts = {
            "profile": 0,
            "procedure": 0,
            "variant": 0,
            "phases": 0,
            "acts": 0,
            "documents": 0,
            "norms": 0,
            "checklists": 0,
            "requirements": 0,
            "outcomes": 0,
            "rules": 0,
            "templates": 0,
        }
        with self.connect() as conn:
            if self.table_exists(conn, "legal_subbranch_profiles"):
                row = self._fetch_one(
                    conn,
                    "SELECT COUNT(*) AS total FROM legal_subbranch_profiles WHERE subbranch_code = %s",
                    (subbranch_code,),
                )
                counts["profile"] = int((row or {}).get("total") or 0)

            if not self.table_exists(conn, "legal_procedures"):
                return counts

            procedure_rows = self._fetch_all(
                conn,
                """
                SELECT code
                FROM legal_procedures
                WHERE subbranch_code = %s AND is_active = TRUE
                ORDER BY code
                """,
                (subbranch_code,),
            )
            procedure_codes = [str(row["code"]) for row in procedure_rows if row.get("code")]
            counts["procedure"] = len(procedure_codes)
            if not procedure_codes:
                return counts

            placeholders = ", ".join(["%s"] * len(procedure_codes))
            params = tuple(procedure_codes)
            table_map = {
                "variant": "legal_procedure_variants",
                "phases": "legal_procedure_phase_map",
                "acts": "legal_procedure_acts",
                "documents": "legal_procedure_document_map",
                "norms": "legal_procedure_norms",
                "checklists": "legal_procedure_checklists",
                "requirements": "legal_procedure_requirements",
                "outcomes": "legal_procedure_outcomes",
                "rules": "legal_procedure_rules",
                "templates": "legal_templates",
            }

            for block, table_name in table_map.items():
                if not self.table_exists(conn, table_name):
                    counts[block] = 0
                    continue
                active_filter = " AND is_active = TRUE" if table_name in {"legal_templates", "legal_procedure_rules"} else ""
                row = self._fetch_one(
                    conn,
                    f"SELECT COUNT(*) AS total FROM {table_name} WHERE procedure_code IN ({placeholders}){active_filter}",
                    params,
                )
                counts[block] = int((row or {}).get("total") or 0)
        return counts

    def replace_snapshots(self, snapshots: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            self._execute(conn, "DELETE FROM coverage_snapshots")
            for snapshot in snapshots:
                self._execute(
                    conn,
                    """
                    INSERT INTO coverage_snapshots (
                        subbranch_code,
                        coverage_score,
                        coverage_status,
                        missing_blocks_json,
                        procedure_count
                    ) VALUES (%s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        snapshot["subbranch_code"],
                        snapshot["coverage_score"],
                        snapshot["coverage_status"],
                        json.dumps(snapshot["missing_blocks"], ensure_ascii=False),
                        snapshot["procedure_count"],
                    ),
                )
            conn.commit()

    def list_latest_snapshots(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                """
                SELECT DISTINCT ON (subbranch_code)
                    id,
                    subbranch_code,
                    coverage_score,
                    coverage_status,
                    missing_blocks_json,
                    procedure_count,
                    generated_at
                FROM coverage_snapshots
                ORDER BY subbranch_code, generated_at DESC
                """,
            )

    def replace_gap_queue(self, gaps: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            self._execute(conn, "DELETE FROM coverage_gap_queue WHERE status IN ('OPEN', 'IN_PROGRESS', 'GENERATED')")
            for gap in gaps:
                self._execute(
                    conn,
                    """
                    INSERT INTO coverage_gap_queue (
                        subbranch_code,
                        gap_type,
                        priority_score,
                        gap_payload_json,
                        status
                    ) VALUES (%s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        gap["subbranch_code"],
                        gap["gap_type"],
                        gap["priority_score"],
                        json.dumps(gap["gap_payload"], ensure_ascii=False),
                        gap.get("status", "OPEN"),
                    ),
                )
            conn.commit()

    def list_open_gaps(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                """
                SELECT id, subbranch_code, gap_type, priority_score, gap_payload_json, status, created_at
                FROM coverage_gap_queue
                WHERE status = 'OPEN'
                ORDER BY priority_score DESC, created_at ASC
                LIMIT %s
                """,
                (limit,),
            )

    def set_gap_status(self, gap_id: int, status: str) -> None:
        with self.connect() as conn:
            self._execute(
                conn,
                """
                UPDATE coverage_gap_queue
                SET status = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (status, gap_id),
            )
            conn.commit()

    def get_policy(self, subbranch_code: str, complexity_level: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetch_one(
                conn,
                """
                SELECT *
                FROM coverage_policies
                WHERE (subbranch_code = %s OR subbranch_code IS NULL)
                  AND (complexity_level = %s OR complexity_level IS NULL)
                ORDER BY
                    CASE WHEN subbranch_code = %s THEN 0 ELSE 1 END,
                    CASE WHEN complexity_level = %s THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (subbranch_code, complexity_level, subbranch_code, complexity_level),
            )
        return row or {
            "auto_publish_allowed": False,
            "min_score_to_skip_generation": 100,
            "require_human_review": True,
        }

    def create_draft(self, payload: dict[str, Any]) -> int:
        with self.connect() as conn:
            row = self._fetch_one(
                conn,
                """
                INSERT INTO generated_procedure_drafts (
                    subbranch_code,
                    procedure_code,
                    draft_source,
                    prompt_used,
                    retrieval_examples_json,
                    spec_json,
                    draft_spec_original_json,
                    validation_report_json,
                    status,
                    risk_level,
                    auto_publish_eligible,
                    review_diff_json,
                    last_review_action
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s::jsonb, %s)
                RETURNING id
                """,
                (
                    payload["subbranch_code"],
                    payload.get("procedure_code"),
                    payload.get("draft_source", "AI"),
                    payload.get("prompt_used"),
                    json.dumps(payload.get("retrieval_examples") or [], ensure_ascii=False),
                    json.dumps(payload["spec_json"], ensure_ascii=False),
                    json.dumps(payload["spec_json"], ensure_ascii=False),
                    json.dumps(payload.get("validation_report_json") or {}, ensure_ascii=False),
                    payload.get("status", "generated"),
                    payload.get("risk_level", "MEDIUM"),
                    bool(payload.get("auto_publish_eligible")),
                    json.dumps({}, ensure_ascii=False),
                    "generated",
                ),
            )
            conn.commit()
        return int((row or {})["id"])

    def list_drafts(self, *, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        wanted = statuses or ("generated", "validated", "needs_review", "approved")
        placeholders = ", ".join(["%s"] * len(wanted))
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                f"""
                SELECT id, subbranch_code, procedure_code, status, risk_level,
                       auto_publish_eligible, created_at, reviewed_at,
                       review_reason, review_signature, last_review_action
                FROM generated_procedure_drafts
                WHERE status IN ({placeholders})
                ORDER BY auto_publish_eligible DESC, created_at ASC
                """,
                tuple(wanted),
            )

    def get_draft(self, draft_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            return self._fetch_one(
                conn,
                """
                SELECT id, subbranch_code, procedure_code, draft_source, prompt_used,
                       retrieval_examples_json, spec_json, draft_spec_original_json, validation_report_json,
                       status, risk_level, auto_publish_eligible, created_at,
                       reviewed_at, reviewer, review_reason, review_signature,
                       review_diff_json, last_review_action, published_at
                FROM generated_procedure_drafts
                WHERE id = %s
                """,
                (draft_id,),
            )

    def _record_review_event(
        self,
        conn: Any,
        *,
        draft_id: int,
        action: str,
        reviewer: str = "",
        review_reason: str = "",
        review_signature: str = "",
        before_spec: dict[str, Any] | None = None,
        after_spec: dict[str, Any] | None = None,
        diff_payload: dict[str, Any] | None = None,
    ) -> None:
        self._execute(
            conn,
            """
            INSERT INTO coverage_review_audit_log (
                draft_id,
                review_action,
                reviewer,
                reviewer_signature,
                review_reason,
                spec_before_json,
                spec_after_json,
                diff_json
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                draft_id,
                action,
                reviewer or None,
                review_signature or None,
                review_reason or None,
                json.dumps(before_spec or {}, ensure_ascii=False),
                json.dumps(after_spec or {}, ensure_ascii=False),
                json.dumps(diff_payload or {}, ensure_ascii=False),
            ),
        )

    def update_draft_spec(
        self,
        draft_id: int,
        spec_json: dict[str, Any],
        validation: dict[str, Any],
        status: str,
        *,
        reviewer: str = "",
        review_signature: str = "",
    ) -> None:
        with self.connect() as conn:
            current = self._fetch_one(
                conn,
                """
                SELECT spec_json, draft_spec_original_json, review_reason
                FROM generated_procedure_drafts
                WHERE id = %s
                """,
                (draft_id,),
            ) or {}
            original_spec = dict(current.get("draft_spec_original_json") or current.get("spec_json") or {})
            current_spec = dict(current.get("spec_json") or {})
            diff_payload = build_review_diff(original_spec, spec_json)
            self._execute(
                conn,
                """
                UPDATE generated_procedure_drafts
                SET spec_json = %s::jsonb,
                    validation_report_json = %s::jsonb,
                    status = %s,
                    review_diff_json = %s::jsonb,
                    last_review_action = 'saved',
                    review_signature = COALESCE(%s, review_signature)
                WHERE id = %s
                """,
                (
                    json.dumps(spec_json, ensure_ascii=False),
                    json.dumps(validation, ensure_ascii=False),
                    status,
                    json.dumps(diff_payload, ensure_ascii=False),
                    review_signature or None,
                    draft_id,
                ),
            )
            self._record_review_event(
                conn,
                draft_id=draft_id,
                action="saved",
                reviewer=reviewer,
                review_signature=review_signature,
                review_reason=str(current.get("review_reason") or "").strip(),
                before_spec=current_spec,
                after_spec=spec_json,
                diff_payload=build_review_diff(current_spec, spec_json),
            )
            conn.commit()

    def set_draft_status(
        self,
        draft_id: int,
        status: str,
        reviewer: str = "",
        *,
        review_reason: str = "",
        review_signature: str = "",
    ) -> None:
        with self.connect() as conn:
            current = self._fetch_one(
                conn,
                """
                SELECT spec_json, draft_spec_original_json
                FROM generated_procedure_drafts
                WHERE id = %s
                """,
                (draft_id,),
            ) or {}
            current_spec = dict(current.get("spec_json") or {})
            original_spec = dict(current.get("draft_spec_original_json") or current_spec)
            diff_payload = build_review_diff(original_spec, current_spec)
            self._execute(
                conn,
                """
                UPDATE generated_procedure_drafts
                SET status = %s,
                    reviewer = %s,
                    review_reason = %s,
                    review_signature = %s,
                    review_diff_json = %s::jsonb,
                    last_review_action = %s,
                    reviewed_at = NOW()
                WHERE id = %s
                """,
                (
                    status,
                    reviewer or None,
                    review_reason or None,
                    review_signature or None,
                    json.dumps(diff_payload, ensure_ascii=False),
                    status,
                    draft_id,
                ),
            )
            self._record_review_event(
                conn,
                draft_id=draft_id,
                action=status,
                reviewer=reviewer,
                review_reason=review_reason,
                review_signature=review_signature,
                before_spec=current_spec,
                after_spec=current_spec,
                diff_payload=diff_payload,
            )
            conn.commit()

    def list_publishable_drafts(self, *, limit: int = 20, auto_only: bool = False) -> list[dict[str, Any]]:
        where = "status = 'approved'"
        if auto_only:
            where += " AND auto_publish_eligible = TRUE"
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                f"""
                SELECT id, subbranch_code, procedure_code, spec_json, validation_report_json,
                       auto_publish_eligible, created_at, reviewed_at,
                       review_reason, review_signature, review_diff_json
                FROM generated_procedure_drafts
                WHERE {where}
                ORDER BY reviewed_at ASC NULLS LAST, created_at ASC
                LIMIT %s
                """,
                (limit,),
            )

    def apply_generated_sql(self, sql_payload: str) -> None:
        assert_no_procedure_lifecycle_sql_bypass(sql_payload)
        with self.connect() as conn:
            self._execute(conn, sql_payload)
            conn.commit()

    def mark_published(self, draft_id: int, subbranch_code: str, procedure_code: str, sql_payload: str, mode: str) -> int:
        with self.connect() as conn:
            current = self._fetch_one(
                conn,
                """
                SELECT reviewer, review_reason, review_signature, spec_json, draft_spec_original_json, review_diff_json
                FROM generated_procedure_drafts
                WHERE id = %s
                """,
                (draft_id,),
            ) or {}
            row = self._fetch_one(
                conn,
                """
                INSERT INTO published_procedure_history (
                    draft_id,
                    procedure_code,
                    subbranch_code,
                    sql_payload,
                    published_mode
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (draft_id, procedure_code, subbranch_code, sql_payload, mode),
            )
            self._execute(
                conn,
                """
                UPDATE generated_procedure_drafts
                SET status = 'published',
                    last_review_action = 'published',
                    published_at = NOW()
                WHERE id = %s
                """,
                (draft_id,),
            )
            self._record_review_event(
                conn,
                draft_id=draft_id,
                action="published",
                reviewer=str(current.get("reviewer") or ""),
                review_reason=str(current.get("review_reason") or ""),
                review_signature=str(current.get("review_signature") or ""),
                before_spec=dict(current.get("spec_json") or {}),
                after_spec=dict(current.get("spec_json") or {}),
                diff_payload=dict(current.get("review_diff_json") or {}) or build_review_diff(
                    dict(current.get("draft_spec_original_json") or current.get("spec_json") or {}),
                    dict(current.get("spec_json") or {}),
                ),
            )
            conn.commit()
        return int((row or {})["id"])

    def record_learning_event(self, history_id: int, subbranch_code: str, procedure_code: str, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            self._execute(
                conn,
                """
                INSERT INTO coverage_learning_events (
                    history_id,
                    subbranch_code,
                    procedure_code,
                    signal_type,
                    signal_payload_json
                ) VALUES (%s, %s, %s, 'PUBLISHED_SPEC', %s::jsonb)
                """,
                (
                    history_id,
                    subbranch_code,
                    procedure_code,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()

    def list_learning_examples(self, subbranch_code: str, *, limit: int = 4) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if not self.table_exists(conn, "coverage_learning_events"):
                return []
            return self._fetch_all(
                conn,
                """
                SELECT procedure_code, signal_payload_json, created_at
                FROM coverage_learning_events
                WHERE subbranch_code = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (subbranch_code, limit),
            )

    def list_procedure_examples(self, subbranch_code: str, *, limit: int = 5) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if not self.table_exists(conn, "legal_procedures"):
                return []
            rows = self._fetch_all(
                conn,
                """
                SELECT code, subbranch_code, channel_code, act_type_code,
                       norm_source_code, name, description, complexity_level
                FROM legal_procedures
                WHERE subbranch_code = %s AND is_active = TRUE
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (subbranch_code, limit),
            )
        return rows

    def list_published_history(self, *, limit: int = 12) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                """
                SELECT id, draft_id, procedure_code, subbranch_code, published_mode, published_at, sql_payload
                FROM published_procedure_history
                ORDER BY published_at DESC
                LIMIT %s
                """,
                (limit,),
            )

    def list_review_history(self, draft_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if not self.table_exists(conn, "coverage_review_audit_log"):
                return []
            return self._fetch_all(
                conn,
                """
                SELECT id, draft_id, review_action, reviewer, reviewer_signature,
                       review_reason, diff_json, created_at
                FROM coverage_review_audit_log
                WHERE draft_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (draft_id, limit),
            )

    def count_learning_events(self) -> int:
        with self.connect() as conn:
            row = self._fetch_one(conn, "SELECT COUNT(*) AS total FROM coverage_learning_events")
        return int((row or {}).get("total") or 0)
