from __future__ import annotations

from copy import deepcopy
import sqlite3
from pathlib import Path

from pct.legal_coverage_pipeline import (
    approve_draft,
    build_dashboard_payload,
    build_gap_queue,
    generate_drafts,
    publish_single_draft,
    publish_approved_drafts,
    run_coverage_audit,
    save_draft,
)
from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig, SQLiteCoverageRepository


class _FakeCoverageRepository:
    def __init__(self):
        self.snapshots: list[dict] = []
        self.gaps: list[dict] = []
        self.drafts: list[dict] = []
        self.history: list[dict] = []
        self.learning_events: list[dict] = []
        self.applied_sql: list[str] = []
        self._next_gap_id = 1
        self._next_draft_id = 1
        self._next_history_id = 1
        self._block_state = {
            "CONSUMATORI_GARANZIE_E_RECESSO": {
                "profile": 1,
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
            },
            "PENALE_DENUNCIA": {
                "profile": 1,
                "procedure": 1,
                "variant": 1,
                "phases": 2,
                "acts": 1,
                "documents": 1,
                "norms": 1,
                "checklists": 2,
                "requirements": 0,
                "outcomes": 0,
                "rules": 0,
                "templates": 0,
            },
        }
        self._metadata = {
            "CONSUMATORI_GARANZIE_E_RECESSO": {
                "operational_priority": 79,
                "telematic": False,
                "preset_available": True,
                "specialist_without_preset": False,
            },
            "PENALE_DENUNCIA": {
                "operational_priority": 88,
                "telematic": False,
                "preset_available": False,
                "specialist_without_preset": True,
            },
        }

    def ensure_schema(self):
        return None

    def ping(self):
        return True

    def list_known_subbranches(self):
        return sorted(self._block_state)

    def get_subbranch_block_state(self, subbranch_code: str):
        return deepcopy(self._block_state[subbranch_code])

    def replace_snapshots(self, snapshots):
        self.snapshots = [
            {
                **row,
                "id": index + 1,
                "missing_blocks_json": list(row["missing_blocks"]),
            }
            for index, row in enumerate(snapshots)
        ]

    def list_latest_snapshots(self):
        return deepcopy(self.snapshots)

    def get_subbranch_metadata(self, subbranch_code: str):
        return deepcopy(self._metadata[subbranch_code])

    def replace_gap_queue(self, gaps):
        self.gaps = []
        for gap in gaps:
            row = deepcopy(gap)
            row["id"] = self._next_gap_id
            row["gap_payload_json"] = deepcopy(gap["gap_payload"])
            self._next_gap_id += 1
            self.gaps.append(row)

    def list_open_gaps(self, *, limit: int = 20):
        return [deepcopy(row) for row in self.gaps if row["status"] == "OPEN"][:limit]

    def set_gap_status(self, gap_id: int, status: str):
        for gap in self.gaps:
            if gap["id"] == gap_id:
                gap["status"] = status

    def get_policy(self, subbranch_code: str, complexity_level: str):
        if subbranch_code == "CONSUMATORI_GARANZIE_E_RECESSO" and complexity_level == "LOW":
            return {
                "auto_publish_allowed": True,
                "min_score_to_skip_generation": 90,
                "require_human_review": False,
            }
        return {
            "auto_publish_allowed": False,
            "min_score_to_skip_generation": 100,
            "require_human_review": True,
        }

    def create_draft(self, payload):
        row = deepcopy(payload)
        row["id"] = self._next_draft_id
        row["created_at"] = "2026-04-17T10:00:00"
        row["reviewed_at"] = None
        self._next_draft_id += 1
        self.drafts.append(row)
        return row["id"]

    def list_drafts(self, *, statuses=None):
        wanted = set(statuses or ("generated", "validated", "needs_review", "approved"))
        return [deepcopy(row) for row in self.drafts if row["status"] in wanted]

    def get_draft(self, draft_id: int):
        return next((deepcopy(row) for row in self.drafts if row["id"] == draft_id), None)

    def update_draft_spec(self, draft_id: int, spec_json, validation, status):
        for draft in self.drafts:
            if draft["id"] == draft_id:
                draft["spec_json"] = deepcopy(spec_json)
                draft["validation_report_json"] = deepcopy(validation)
                draft["status"] = status

    def set_draft_status(self, draft_id: int, status: str, reviewer: str = ""):
        for draft in self.drafts:
            if draft["id"] == draft_id:
                draft["status"] = status
                draft["reviewer"] = reviewer
                draft["reviewed_at"] = "2026-04-17T11:00:00"

    def list_publishable_drafts(self, *, limit: int = 20, auto_only: bool = False):
        rows = [row for row in self.drafts if row["status"] == "approved"]
        if auto_only:
            rows = [row for row in rows if row["auto_publish_eligible"]]
        return [deepcopy(row) for row in rows[:limit]]

    def apply_generated_sql(self, sql_payload: str):
        self.applied_sql.append(sql_payload)

    def mark_published(self, draft_id: int, subbranch_code: str, procedure_code: str, sql_payload: str, mode: str):
        row = {
            "id": self._next_history_id,
            "draft_id": draft_id,
            "subbranch_code": subbranch_code,
            "procedure_code": procedure_code,
            "published_mode": mode,
            "published_at": "2026-04-17T12:00:00",
        }
        self._next_history_id += 1
        self.history.append(row)
        for draft in self.drafts:
            if draft["id"] == draft_id:
                draft["status"] = "published"
        self._block_state[subbranch_code] = {
            "profile": 1,
            "procedure": 1,
            "variant": 1,
            "phases": 3,
            "acts": 1,
            "documents": 2,
            "norms": 1,
            "checklists": 3,
            "requirements": 1,
            "outcomes": 1,
            "rules": 1,
            "templates": 1,
        }
        return row["id"]

    def record_learning_event(self, history_id: int, subbranch_code: str, procedure_code: str, payload):
        self.learning_events.append(
            {
                "history_id": history_id,
                "subbranch_code": subbranch_code,
                "procedure_code": procedure_code,
                "signal_payload_json": deepcopy(payload),
            }
        )

    def list_learning_examples(self, subbranch_code: str, *, limit: int = 4):
        return [
            deepcopy(row)
            for row in self.learning_events
            if row["subbranch_code"] == subbranch_code
        ][:limit]

    def list_procedure_examples(self, subbranch_code: str, *, limit: int = 5):
        return []

    def list_published_history(self, *, limit: int = 12):
        return deepcopy(self.history[:limit])

    def count_learning_events(self):
        return len(self.learning_events)


class _StubGenerator:
    def generate_draft(self, repository, gap):
        subbranch_code = gap["subbranch_code"]
        spec = {
            "subbranch_profile": {
                "subbranch_code": subbranch_code,
                "coverage_mode": "OPERATIONAL_READY",
                "operational_priority": 79,
                "is_telematic": False,
                "requires_human_review": False,
                "default_channel_code": "STRAGIUDIZIALE",
            },
            "procedure": {
                "code": "PROC_AUTO_CONS_001",
                "subbranch_code": subbranch_code,
                "phase_code": "PREPARAZIONE",
                "channel_code": "STRAGIUDIZIALE",
                "act_type_code": "LETTERA",
                "norm_source_code": "CODICE_CIVILE",
                "name": "Reclamo consumatore automatico",
                "description": "Bozza standard auto-generata.",
                "workflow_code": "WF_AUTO_CONS_001",
                "estimated_duration_days": 20,
                "complexity_level": "LOW",
                "mandatory_human_review": False,
                "requires_hearing": False,
                "requires_registry_enrollment": False,
                "allows_settlement": True,
                "default_output_bundle_code": "BUNDLE_AUTO_CONS_001",
                "is_active": True,
            },
            "variants": [{"name": "Variante default", "is_default": True}],
            "phase_map": [
                {"phase_code": "PREPARAZIONE", "sort_order": 10, "is_required": True},
                {"phase_code": "NOTIFICA", "sort_order": 20, "is_required": True},
                {"phase_code": "CHIUSURA", "sort_order": 30, "is_required": True},
            ],
            "acts": [{"name": "Reclamo scritto", "act_type_code": "LETTERA", "is_required": True, "is_active": True}],
            "documents": [
                {"name": "Prova acquisto", "document_type_code": "RICEVUTA", "phase_code": "PREPARAZIONE", "is_required": True},
                {"name": "Contratto o ordine", "document_type_code": "CONTRATTO", "phase_code": "PREPARAZIONE", "is_required": False},
            ],
            "norms": [{"norm_source_code": "CODICE_CIVILE", "notes": "Garanzia legale e rimedi consumer."}],
            "checklists": [
                {"item_text": "Verificare scontrino o ordine", "is_required": True},
                {"item_text": "Qualificare garanzia o recesso", "is_required": True},
                {"item_text": "Inviare reclamo e monitorare il riscontro", "is_required": True},
            ],
            "requirements": [{"requirement_type": "DOCUMENT", "requirement_key": "prova_acquisto", "requirement_value": "required", "is_required": True}],
            "deadlines": [{"label": "Monitorare il riscontro del professionista", "relative_to": "EVENTO", "days_offset": 0, "is_peremptory": False}],
            "outcomes": [{"name": "Reclamo inviato e presidiato", "is_positive": True}],
            "rules": [{"rule_type": "WARNING", "rule_key": "followup_required", "rule_expression": "followup_done == true", "user_message": "Verificare il riscontro del professionista."}],
            "templates": [{"name": "Reclamo consumatore", "body": "Oggetto: {{ oggetto }}", "variables": [{"variable_name": "oggetto", "variable_type": "STRING", "source_scope": "MANUAL", "is_required": True}]}],
        }
        validation = {"errors": [], "warnings": [], "score": 100, "missing_blocks": []}
        return {
            "prompt_used": "prompt sintetico",
            "retrieval_examples": [],
            "spec_json": spec,
            "validation_report_json": validation,
            "procedure_code": "PROC_AUTO_CONS_001",
            "risk_level": "LOW",
        }


def test_legal_coverage_pipeline_copre_il_flusso_end_to_end():
    repository = _FakeCoverageRepository()

    audit = run_coverage_audit(repository)
    assert audit["subbranches_total"] == 2
    assert repository.snapshots[0]["coverage_status"] in {"EMPTY", "PARTIAL", "READY"}

    gaps = build_gap_queue(repository)
    assert gaps["gap_total"] == 2
    assert any(row["gap_type"] == "MISSING_PROCEDURE" for row in repository.gaps)

    generated = generate_drafts(repository, _StubGenerator(), limit=1)
    assert generated["draft_total"] == 1
    assert repository.drafts[0]["status"] == "approved"

    bad_spec = deepcopy(repository.drafts[0]["spec_json"])
    bad_spec["templates"] = []
    validation = save_draft(repository, repository.drafts[0]["id"], bad_spec)
    assert validation["errors"]
    assert repository.drafts[0]["status"] == "generated"

    approve_draft(repository, repository.drafts[0]["id"], "tester")
    assert repository.drafts[0]["status"] == "approved"

    published = publish_approved_drafts(repository, limit=1, auto_only=False, apply_to_db=True)
    assert published["published_total"] == 1
    assert repository.applied_sql
    assert repository.learning_events
    assert repository.history

    dashboard = build_dashboard_payload(repository)
    assert dashboard["headline"]["training_implicito"] == 1
    assert dashboard["headline"]["subbranch_ready"] >= 1


def test_publish_single_draft_pubblica_il_draft_richiesto():
    repository = _FakeCoverageRepository()
    run_coverage_audit(repository)
    build_gap_queue(repository)
    generate_drafts(repository, _StubGenerator(), limit=2)
    approve_draft(repository, repository.drafts[0]["id"], "reviewer")

    result = publish_single_draft(repository, repository.drafts[0]["id"], apply_to_db=True)

    assert result["published_total"] == 1
    assert repository.drafts[0]["status"] == "published"
    assert repository.history[0]["draft_id"] == repository.drafts[0]["id"]


def test_sqlite_coverage_repository_supporta_pipeline_end_to_end(tmp_path: Path):
    db_path = tmp_path / "studio.db"
    repository = SQLiteCoverageRepository(CoverageSqliteConfig(str(db_path)))

    assert repository.ping() is True

    audit = run_coverage_audit(repository)
    assert audit["subbranches_total"] >= 20

    gaps = build_gap_queue(repository)
    assert gaps["gap_total"] >= 1

    generated = generate_drafts(repository, _StubGenerator(), limit=1)
    assert generated["draft_total"] == 1

    draft = repository.list_drafts()[0]
    approve_draft(repository, int(draft["id"]), "tester")

    result = publish_single_draft(repository, int(draft["id"]), apply_to_db=True)
    assert result["published_total"] == 1

    conn = sqlite3.connect(str(db_path))
    try:
        legal_tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "coverage_snapshots" in legal_tables
        assert "generated_procedure_drafts" in legal_tables
        assert "legal_procedures" in legal_tables
        assert conn.execute("SELECT COUNT(*) FROM legal_procedures").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM published_procedure_history").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM coverage_learning_events").fetchone()[0] == 1
    finally:
        conn.close()
