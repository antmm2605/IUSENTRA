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

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            self._execute_script(conn, TAXONOMY_SCHEMA_SQL)
            self._execute_script(conn, COVERAGE_SCHEMA_SQL)
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
                    validation_report_json,
                    status,
                    risk_level,
                    auto_publish_eligible
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                RETURNING id
                """,
                (
                    payload["subbranch_code"],
                    payload.get("procedure_code"),
                    payload.get("draft_source", "AI"),
                    payload.get("prompt_used"),
                    json.dumps(payload.get("retrieval_examples") or [], ensure_ascii=False),
                    json.dumps(payload["spec_json"], ensure_ascii=False),
                    json.dumps(payload.get("validation_report_json") or {}, ensure_ascii=False),
                    payload.get("status", "generated"),
                    payload.get("risk_level", "MEDIUM"),
                    bool(payload.get("auto_publish_eligible")),
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
                       auto_publish_eligible, created_at, reviewed_at
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
                       retrieval_examples_json, spec_json, validation_report_json,
                       status, risk_level, auto_publish_eligible, created_at,
                       reviewed_at, reviewer, published_at
                FROM generated_procedure_drafts
                WHERE id = %s
                """,
                (draft_id,),
            )

    def update_draft_spec(self, draft_id: int, spec_json: dict[str, Any], validation: dict[str, Any], status: str) -> None:
        with self.connect() as conn:
            self._execute(
                conn,
                """
                UPDATE generated_procedure_drafts
                SET spec_json = %s::jsonb,
                    validation_report_json = %s::jsonb,
                    status = %s
                WHERE id = %s
                """,
                (
                    json.dumps(spec_json, ensure_ascii=False),
                    json.dumps(validation, ensure_ascii=False),
                    status,
                    draft_id,
                ),
            )
            conn.commit()

    def set_draft_status(self, draft_id: int, status: str, reviewer: str = "") -> None:
        with self.connect() as conn:
            self._execute(
                conn,
                """
                UPDATE generated_procedure_drafts
                SET status = %s,
                    reviewer = %s,
                    reviewed_at = NOW()
                WHERE id = %s
                """,
                (status, reviewer or None, draft_id),
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
                       auto_publish_eligible, created_at, reviewed_at
                FROM generated_procedure_drafts
                WHERE {where}
                ORDER BY reviewed_at ASC NULLS LAST, created_at ASC
                LIMIT %s
                """,
                (limit,),
            )

    def apply_generated_sql(self, sql_payload: str) -> None:
        with self.connect() as conn:
            self._execute(conn, sql_payload)
            conn.commit()

    def mark_published(self, draft_id: int, subbranch_code: str, procedure_code: str, sql_payload: str, mode: str) -> int:
        with self.connect() as conn:
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
                    published_at = NOW()
                WHERE id = %s
                """,
                (draft_id,),
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
                SELECT id, draft_id, procedure_code, subbranch_code, published_mode, published_at
                FROM published_procedure_history
                ORDER BY published_at DESC
                LIMIT %s
                """,
                (limit,),
            )

    def count_learning_events(self) -> int:
        with self.connect() as conn:
            row = self._fetch_one(conn, "SELECT COUNT(*) AS total FROM coverage_learning_events")
        return int((row or {}).get("total") or 0)
