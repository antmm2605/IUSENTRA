from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta

from pct.legal_update_autofetch import (
    LEGAL_SOURCE_QUALITY_QUESTIONS,
    LEGAL_UPDATE_AUTOFETCH_SCHEMA,
    LegalAutoFetchConfig,
    build_legal_autofetch_plan,
    run_legal_update_autofetch_tick,
)


class FakeRepository:
    def __init__(self):
        self.sources = [
            {
                "id": 1,
                "code": "cassazione_massimario",
                "name": "Corte di Cassazione",
                "base_url": "https://www.cortedicassazione.it/",
                "category": "giurisprudenza",
                "enabled": True,
                "is_official": True,
                "polling_minutes": 60,
            },
            {
                "id": 2,
                "code": "gazzetta_ufficiale",
                "name": "Gazzetta Ufficiale",
                "base_url": "https://www.gazzettaufficiale.it/",
                "category": "normativa",
                "enabled": True,
                "is_official": True,
                "polling_minutes": 1440,
            },
            {
                "id": 3,
                "code": "fonte_spenta",
                "name": "Fonte spenta",
                "base_url": "https://example.test/",
                "category": "prassi",
                "enabled": False,
                "is_official": False,
                "polling_minutes": 60,
            },
        ]

    def list_sources(self, *, enabled_only: bool = True):
        return [row for row in self.sources if row["enabled"] or not enabled_only]

    def source_activity_summary(self):
        return {
            "cassazione_massimario": {
                "raw_documents": 4,
                "normalized_documents": 4,
                "review_pending": 1,
                "review_published": 2,
            },
            "gazzetta_ufficiale": {
                "raw_documents": 0,
                "normalized_documents": 0,
                "review_pending": 0,
                "review_published": 0,
            },
        }

    def latest_source_agent_runs(self):
        return {
            "gazzetta_ufficiale": {
                "status": "failed",
                "error_message": "Timeout lettura fonte.",
                "finished_at": "2026-05-18T09:00:00Z",
            }
        }

    def dashboard_snapshot(self):
        return {"headline": {"sources": 2, "raw_documents": 4, "review_pending": 1}}


class FakePipeline:
    def __init__(self):
        self.repository = FakeRepository()

    def dashboard_snapshot(self):
        return self.repository.dashboard_snapshot()


def test_autofetch_plan_rispetta_cursori_budget_e_fonti_disattivate():
    now = datetime(2026, 5, 18, 10, 0, tzinfo=UTC)
    cursor_payload = {
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "sources": {
            "gazzetta_ufficiale": {
                "last_enqueued_at": (now - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
            }
        },
    }

    plan = build_legal_autofetch_plan(
        FakeRepository().list_sources(enabled_only=False),
        cursor_payload=cursor_payload,
        now=now,
        source_budget=1,
    )

    assert plan["schema"] == LEGAL_UPDATE_AUTOFETCH_SCHEMA
    assert plan["selected_count"] == 1
    assert plan["selected"][0]["source_code"] == "cassazione_massimario"
    assert plan["selected"][0]["quality_questions"] == list(LEGAL_SOURCE_QUALITY_QUESTIONS)
    assert {row["reason"] for row in plan["skipped"]} >= {"non_ancora_dovuta", "fonte_disattivata"}


def test_autofetch_tick_accoda_deduplica_esegue_e_aggiorna_monitor(tmp_path):
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(list(command))
        payload = {
            "ok": True,
            "payload": {
                "report": {
                    "reports": [
                        {
                            "documents_found": 1,
                            "processed": 1,
                            "skipped_unchanged": 0,
                        }
                    ]
                }
            },
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    config = LegalAutoFetchConfig(
        intelligence_db=str(tmp_path / "motori.json"),
        giurisprudenza_db=str(tmp_path / "giurisprudenza.json"),
        queue_db_path=str(tmp_path / "jobs.sqlite"),
        cursor_path=str(tmp_path / "cursors.json"),
        source_budget=1,
        item_timeout_seconds=5,
        publish_max_items=1,
    )

    first = run_legal_update_autofetch_tick(
        config,
        pipeline=FakePipeline(),
        source_codes=["cassazione_massimario", "gazzetta_ufficiale"],
        runner=runner,
        now=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )
    second = run_legal_update_autofetch_tick(
        config,
        pipeline=FakePipeline(),
        source_codes=["cassazione_massimario"],
        runner=runner,
        now=datetime(2026, 5, 18, 10, 5, tzinfo=UTC),
    )

    assert first["ok"] is True
    assert len(first["enqueued_jobs"]) == 1
    assert first["enqueued_jobs"][0]["source_code"] == "cassazione_massimario"
    assert first["monitor"]["queue"]["total"] == 1
    assert first["monitor"]["sources_ready"] >= 1
    assert calls

    assert second["plan"]["selected_count"] == 0
    assert second["monitor"]["queue"]["total"] == 1

    cursor_payload = json.loads((tmp_path / "cursors.json").read_text(encoding="utf-8"))
    assert cursor_payload["sources"]["cassazione_massimario"]["last_status"] == "completed"


def test_autofetch_monitor_mostra_fonti_pronte_e_da_verificare(tmp_path):
    config = LegalAutoFetchConfig(
        intelligence_db=str(tmp_path / "motori.json"),
        queue_db_path=str(tmp_path / "jobs.sqlite"),
        cursor_path=str(tmp_path / "cursors.json"),
        execute_due_sources=False,
    )

    report = run_legal_update_autofetch_tick(
        config,
        pipeline=FakePipeline(),
        source_codes=["gazzetta_ufficiale"],
        now=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    statuses = {row["source_code"]: row["status"] for row in report["monitor"]["sources"]}

    assert statuses["cassazione_massimario"] == "pronta"
    assert statuses["gazzetta_ufficiale"] == "da_verificare"
    assert report["monitor"]["readiness"]["status"] == "da_verificare"
