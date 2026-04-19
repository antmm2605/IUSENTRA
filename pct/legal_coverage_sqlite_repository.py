"""Repository SQLite per coverage pipeline, review draft e publish SQL."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator

from pct.legal_platform_seed import LEGAL_PLATFORM_SEED
from pct.legal_coverage_review_audit import build_review_diff


TAXONOMY_SCHEMA_SQL = Path(__file__).with_name("sql") / "20260417_legal_taxonomy_operational_tables.sql"
COVERAGE_SCHEMA_SQL = Path(__file__).with_name("sql") / "20260417_legal_coverage_pipeline.sql"


@dataclass(frozen=True)
class CoverageSqliteConfig:
    path: str

    @property
    def configured(self) -> bool:
        return bool(str(self.path or "").strip())


def _sqliteify_schema(sql: str) -> str:
    text = str(sql or "")
    replacements = (
        ("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("BIGINT NOT NULL REFERENCES generated_procedure_drafts(id)", "INTEGER NOT NULL REFERENCES generated_procedure_drafts(id)"),
        ("BIGINT REFERENCES published_procedure_history(id)", "INTEGER REFERENCES published_procedure_history(id)"),
        ("TIMESTAMPTZ NOT NULL DEFAULT NOW()", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ("TIMESTAMPTZ", "TEXT"),
        ("TIMESTAMP NOT NULL DEFAULT NOW()", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("TIMESTAMP DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ("TIMESTAMP", "TEXT"),
        ("JSONB NOT NULL DEFAULT '[]'::jsonb", "TEXT NOT NULL DEFAULT '[]'"),
        ("JSONB NOT NULL DEFAULT '{}'::jsonb", "TEXT NOT NULL DEFAULT '{}'"),
        ("JSONB", "TEXT"),
        ("::jsonb", ""),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    text = re.sub(r"\bVARCHAR\(\d+\)", "TEXT", text)
    return text


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _decode_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        if isinstance(default, list):
            return []
        if isinstance(default, dict):
            return {}
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        if isinstance(default, list):
            return []
        if isinstance(default, dict):
            return {}
        return default


class SQLiteCoverageRepository:
    """Accesso SQLite tenant-aware alla coverage pipeline."""

    def __init__(self, config: CoverageSqliteConfig):
        self.config = config
        self.db_path = Path(str(config.path or "")).resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.config.configured:
            raise RuntimeError("Percorso SQLite coverage non configurato.")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            conn.close()

    def _fetch_all(self, conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [_row_to_dict(row) or {} for row in conn.execute(sql, params).fetchall()]

    def _fetch_one(self, conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        return _row_to_dict(conn.execute(sql, params).fetchone())

    def table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = self._fetch_one(
            conn,
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return bool((row or {}).get("name"))

    def column_exists(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = self._fetch_all(conn, f"PRAGMA table_info({table_name})")
        return any(str(row.get("name") or "") == column_name for row in rows)

    def _ensure_review_columns(self, conn: sqlite3.Connection) -> None:
        columns = {
            "draft_spec_original_json": "TEXT",
            "review_reason": "TEXT",
            "review_signature": "TEXT",
            "review_diff_json": "TEXT",
            "last_review_action": "TEXT",
        }
        for column_name, sql_type in columns.items():
            if not self.column_exists(conn, "generated_procedure_drafts", column_name):
                conn.execute(f"ALTER TABLE generated_procedure_drafts ADD COLUMN {column_name} {sql_type}")
        conn.execute(
            """
            UPDATE generated_procedure_drafts
            SET draft_spec_original_json = COALESCE(NULLIF(draft_spec_original_json, ''), spec_json),
                review_diff_json = COALESCE(NULLIF(review_diff_json, ''), '{}')
            """
        )

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_sqliteify_schema(TAXONOMY_SCHEMA_SQL.read_text(encoding="utf-8")))
            conn.executescript(_sqliteify_schema(COVERAGE_SCHEMA_SQL.read_text(encoding="utf-8")))
            self._ensure_review_columns(conn)
            conn.commit()

    def ping(self) -> bool:
        try:
            with self.connect() as conn:
                conn.execute("SELECT 1")
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
        telematic = any(
            str(row.get("channel_code") or "").upper()
            in {"PCT_CIVILE", "PDP_PENALE", "PAT_AMMINISTRATIVO", "PTT_TRIBUTARIO", "PORTALE_MINISTERIALE", "SPORTELLO_PA", "PEC_ONLY"}
            for row in seed_rows
        )
        metadata = {
            "subbranch_code": subbranch_code,
            "operational_priority": int(seed_first.get("operational_priority") or 50),
            "preset_available": subbranch_code in {"CONSUMATORI_GARANZIE_E_RECESSO", "SUCCESSIONI_DICHIARAZIONE_DI_SUCCESSIONE"},
            "telematic": telematic,
            "specialist_without_preset": bool(seed_rows)
            and not telematic
            and str(seed_first.get("complexity_level") or "").upper() in {"HIGH", "SPECIALIST"},
        }
        with self.connect() as conn:
            if self.table_exists(conn, "legal_subbranch_profiles"):
                row = self._fetch_one(
                    conn,
                    """
                    SELECT operational_priority, is_telematic, requires_human_review
                    FROM legal_subbranch_profiles
                    WHERE subbranch_code = ?
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
                    "SELECT COUNT(*) AS total FROM legal_subbranch_profiles WHERE subbranch_code = ?",
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
                WHERE subbranch_code = ? AND is_active = 1
                ORDER BY code
                """,
                (subbranch_code,),
            )
            procedure_codes = [str(row["code"]) for row in procedure_rows if row.get("code")]
            counts["procedure"] = len(procedure_codes)
            if not procedure_codes:
                return counts

            placeholders = ", ".join(["?"] * len(procedure_codes))
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
                active_filter = " AND is_active = 1" if table_name in {"legal_templates", "legal_procedure_rules"} else ""
                row = self._fetch_one(
                    conn,
                    f"SELECT COUNT(*) AS total FROM {table_name} WHERE procedure_code IN ({placeholders}){active_filter}",
                    params,
                )
                counts[block] = int((row or {}).get("total") or 0)
        return counts

    def replace_snapshots(self, snapshots: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM coverage_snapshots")
            conn.executemany(
                """
                INSERT INTO coverage_snapshots (
                    subbranch_code,
                    coverage_score,
                    coverage_status,
                    missing_blocks_json,
                    procedure_count
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot["subbranch_code"],
                        snapshot["coverage_score"],
                        snapshot["coverage_status"],
                        json.dumps(snapshot["missing_blocks"], ensure_ascii=False),
                        snapshot["procedure_count"],
                    )
                    for snapshot in snapshots
                ],
            )
            conn.commit()

    def list_latest_snapshots(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                """
                SELECT s.id, s.subbranch_code, s.coverage_score, s.coverage_status,
                       s.missing_blocks_json, s.procedure_count, s.generated_at
                FROM coverage_snapshots s
                WHERE s.id = (
                    SELECT s2.id
                    FROM coverage_snapshots s2
                    WHERE s2.subbranch_code = s.subbranch_code
                    ORDER BY s2.generated_at DESC, s2.id DESC
                    LIMIT 1
                )
                ORDER BY s.subbranch_code
                """,
            )
        for row in rows:
            row["missing_blocks_json"] = _decode_json(row.get("missing_blocks_json"), [])
        return rows

    def replace_gap_queue(self, gaps: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM coverage_gap_queue WHERE status IN ('OPEN', 'IN_PROGRESS', 'GENERATED')")
            conn.executemany(
                """
                INSERT INTO coverage_gap_queue (
                    subbranch_code,
                    gap_type,
                    priority_score,
                    gap_payload_json,
                    status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        gap["subbranch_code"],
                        gap["gap_type"],
                        gap["priority_score"],
                        json.dumps(gap["gap_payload"], ensure_ascii=False),
                        gap.get("status", "OPEN"),
                    )
                    for gap in gaps
                ],
            )
            conn.commit()

    def list_open_gaps(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                """
                SELECT id, subbranch_code, gap_type, priority_score, gap_payload_json, status, created_at
                FROM coverage_gap_queue
                WHERE status = 'OPEN'
                ORDER BY priority_score DESC, created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
        for row in rows:
            row["gap_payload_json"] = _decode_json(row.get("gap_payload_json"), {})
        return rows

    def set_gap_status(self, gap_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE coverage_gap_queue
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
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
                WHERE (subbranch_code = ? OR subbranch_code IS NULL)
                  AND (complexity_level = ? OR complexity_level IS NULL)
                ORDER BY
                    CASE WHEN subbranch_code = ? THEN 0 ELSE 1 END,
                    CASE WHEN complexity_level = ? THEN 0 ELSE 1 END
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
            cur = conn.execute(
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    1 if payload.get("auto_publish_eligible") else 0,
                    json.dumps({}, ensure_ascii=False),
                    "generated",
                ),
            )
            conn.commit()
        return int(cur.lastrowid)

    def list_drafts(self, *, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        wanted = statuses or ("generated", "validated", "needs_review", "approved")
        placeholders = ", ".join(["?"] * len(wanted))
        with self.connect() as conn:
            rows = self._fetch_all(
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
        for row in rows:
            row["auto_publish_eligible"] = bool(row.get("auto_publish_eligible"))
        return rows

    def get_draft(self, draft_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = self._fetch_one(
                conn,
                """
                SELECT id, subbranch_code, procedure_code, draft_source, prompt_used,
                       retrieval_examples_json, spec_json, draft_spec_original_json, validation_report_json,
                       status, risk_level, auto_publish_eligible, created_at,
                       reviewed_at, reviewer, review_reason, review_signature,
                       review_diff_json, last_review_action, published_at
                FROM generated_procedure_drafts
                WHERE id = ?
                """,
                (draft_id,),
            )
        if not row:
            return None
        row["retrieval_examples_json"] = _decode_json(row.get("retrieval_examples_json"), [])
        row["spec_json"] = _decode_json(row.get("spec_json"), {})
        row["draft_spec_original_json"] = _decode_json(row.get("draft_spec_original_json"), {})
        row["validation_report_json"] = _decode_json(row.get("validation_report_json"), {})
        row["review_diff_json"] = _decode_json(row.get("review_diff_json"), {})
        row["auto_publish_eligible"] = bool(row.get("auto_publish_eligible"))
        return row

    def _record_review_event(
        self,
        conn: sqlite3.Connection,
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
        conn.execute(
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                WHERE id = ?
                """,
                (draft_id,),
            ) or {}
            original_spec = _decode_json(current.get("draft_spec_original_json"), _decode_json(current.get("spec_json"), {}))
            current_spec = _decode_json(current.get("spec_json"), {})
            diff_payload = build_review_diff(original_spec, spec_json)
            conn.execute(
                """
                UPDATE generated_procedure_drafts
                SET spec_json = ?,
                    validation_report_json = ?,
                    status = ?,
                    review_diff_json = ?,
                    last_review_action = 'saved',
                    review_signature = COALESCE(?, review_signature)
                WHERE id = ?
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
                WHERE id = ?
                """,
                (draft_id,),
            ) or {}
            current_spec = _decode_json(current.get("spec_json"), {})
            original_spec = _decode_json(current.get("draft_spec_original_json"), current_spec)
            diff_payload = build_review_diff(original_spec, current_spec)
            conn.execute(
                """
                UPDATE generated_procedure_drafts
                SET status = ?,
                    reviewer = ?,
                    review_reason = ?,
                    review_signature = ?,
                    review_diff_json = ?,
                    last_review_action = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
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
            where += " AND auto_publish_eligible = 1"
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                f"""
                SELECT id, subbranch_code, procedure_code, spec_json, validation_report_json,
                       auto_publish_eligible, created_at, reviewed_at,
                       review_reason, review_signature, review_diff_json
                FROM generated_procedure_drafts
                WHERE {where}
                ORDER BY reviewed_at IS NULL, reviewed_at ASC, created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
        for row in rows:
            row["spec_json"] = _decode_json(row.get("spec_json"), {})
            row["validation_report_json"] = _decode_json(row.get("validation_report_json"), {})
            row["review_diff_json"] = _decode_json(row.get("review_diff_json"), {})
            row["auto_publish_eligible"] = bool(row.get("auto_publish_eligible"))
        return rows

    def apply_generated_sql(self, sql_payload: str) -> None:
        with self.connect() as conn:
            conn.executescript(str(sql_payload or ""))
            conn.commit()

    def mark_published(self, draft_id: int, subbranch_code: str, procedure_code: str, sql_payload: str, mode: str) -> int:
        with self.connect() as conn:
            current = self._fetch_one(
                conn,
                """
                SELECT reviewer, review_reason, review_signature, spec_json, draft_spec_original_json, review_diff_json
                FROM generated_procedure_drafts
                WHERE id = ?
                """,
                (draft_id,),
            ) or {}
            cur = conn.execute(
                """
                INSERT INTO published_procedure_history (
                    draft_id,
                    procedure_code,
                    subbranch_code,
                    sql_payload,
                    published_mode
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (draft_id, procedure_code, subbranch_code, sql_payload, mode),
            )
            conn.execute(
                """
                UPDATE generated_procedure_drafts
                SET status = 'published',
                    last_review_action = 'published',
                    published_at = CURRENT_TIMESTAMP
                WHERE id = ?
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
                before_spec=_decode_json(current.get("spec_json"), {}),
                after_spec=_decode_json(current.get("spec_json"), {}),
                diff_payload=_decode_json(current.get("review_diff_json"), {})
                or build_review_diff(
                    _decode_json(current.get("draft_spec_original_json"), _decode_json(current.get("spec_json"), {})),
                    _decode_json(current.get("spec_json"), {}),
                ),
            )
            conn.commit()
        return int(cur.lastrowid)

    def record_learning_event(self, history_id: int, subbranch_code: str, procedure_code: str, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO coverage_learning_events (
                    history_id,
                    subbranch_code,
                    procedure_code,
                    signal_type,
                    signal_payload_json
                ) VALUES (?, ?, ?, 'PUBLISHED_SPEC', ?)
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
            rows = self._fetch_all(
                conn,
                """
                SELECT procedure_code, signal_payload_json, created_at
                FROM coverage_learning_events
                WHERE subbranch_code = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (subbranch_code, limit),
            )
        for row in rows:
            row["signal_payload_json"] = _decode_json(row.get("signal_payload_json"), {})
        return rows

    def list_procedure_examples(self, subbranch_code: str, *, limit: int = 5) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if not self.table_exists(conn, "legal_procedures"):
                return []
            return self._fetch_all(
                conn,
                """
                SELECT code, subbranch_code, channel_code, act_type_code,
                       norm_source_code, name, description, complexity_level
                FROM legal_procedures
                WHERE subbranch_code = ? AND is_active = 1
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (subbranch_code, limit),
            )

    def list_published_history(self, *, limit: int = 12) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return self._fetch_all(
                conn,
                """
                SELECT id, draft_id, procedure_code, subbranch_code, published_mode, published_at, sql_payload
                FROM published_procedure_history
                ORDER BY published_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )

    def list_review_history(self, draft_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if not self.table_exists(conn, "coverage_review_audit_log"):
                return []
            rows = self._fetch_all(
                conn,
                """
                SELECT id, draft_id, review_action, reviewer, reviewer_signature,
                       review_reason, diff_json, created_at
                FROM coverage_review_audit_log
                WHERE draft_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (draft_id, limit),
            )
        for row in rows:
            row["diff_json"] = _decode_json(row.get("diff_json"), {})
        return rows

    def count_learning_events(self) -> int:
        with self.connect() as conn:
            row = self._fetch_one(conn, "SELECT COUNT(*) AS total FROM coverage_learning_events")
        return int((row or {}).get("total") or 0)
