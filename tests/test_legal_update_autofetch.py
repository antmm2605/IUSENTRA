from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta

import pytest

from pct.legal_update_autofetch import (
    LEGAL_SOURCE_QUALITY_QUESTIONS,
    LEGAL_UPDATE_AUTOFETCH_SCHEMA,
    LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES,
    LegalAutoFetchConfig,
    build_legal_autofetch_plan,
    build_legal_update_progressive_run_plan,
    legal_update_progressive_source_classification,
    legal_update_progressive_scheduler_payload,
    run_legal_update_autofetch_tick,
    run_legal_update_progressive_cycle,
)
from pct.legal_update_health_report import build_giurisprudenza_structured_canary, build_legal_updates_health_report
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS, build_legal_update_pipeline
from pct.legal_update_source_capabilities import get_source_capability


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


def test_scheduler_progressivo_step1_abilita_solo_fonti_verdi():
    payload = legal_update_progressive_scheduler_payload(
        [
            {"code": "cassazione_ultime_sent_ord_questioni", "name": "Cassazione", "enabled": True},
            {"code": "corte_conti", "name": "Corte dei Conti", "enabled": True},
            {"code": "curia_cgue_rss", "name": "Curia", "enabled": True},
            {"code": "inps_circolari", "name": "INPS circolari", "enabled": True},
            {"code": "inps_messaggi", "name": "INPS messaggi", "enabled": True},
            {"code": "agcom_provvedimenti", "name": "AGCOM", "enabled": True},
            {"code": "anac_documenti", "name": "ANAC", "enabled": True},
            {"code": "garante_privacy", "name": "Garante", "enabled": True},
            {"code": "gazzetta_ufficiale", "name": "Gazzetta", "enabled": True},
            {"code": "openga_sentenze", "name": "OpenGA sentenze", "enabled": True},
            {"code": "corte_costituzionale", "name": "Corte costituzionale", "enabled": True},
        ]
    )

    assert payload["enabled_source_codes"] == list(LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES)
    assert payload["source_budget"] == 3
    assert payload["publish_max_items"] == 5
    assert payload["item_timeout_seconds"] == 120
    assert payload["cassazione_latest_max_items"] == 5
    assert payload["source_classification"]["openga_sentenze"] == "rag_only"
    assert payload["publication_policy"]["openga_sentenze"] == "no_publish"
    assert payload["source_classification"]["corte_costituzionale"] == "osservazione"
    excluded = {row["source_code"]: row["reason"] for row in payload["excluded_sources"]}
    assert "RAG-only" in excluded["openga_sentenze"]
    assert "osservazione" in excluded["corte_costituzionale"]


def test_scheduler_progressivo_classifica_tutte_le_fonti_ufficiali_del_catalogo():
    allowed = {
        "verde_abilitata",
        "rag_only",
        "osservazione",
        "archivio_locale",
        "fuori_perimetro",
    }

    for source in DEFAULT_SOURCE_ROWS:
        code = str(source["code"])
        classification = legal_update_progressive_source_classification(code)
        assert classification in allowed
        if get_source_capability(code).publication_destination != "out_of_scope":
            assert classification != "fuori_perimetro", code


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


def test_progressive_run_plan_esclude_fonti_non_verdi(tmp_path):
    config = LegalAutoFetchConfig(
        intelligence_db=str(tmp_path / "motori.json"),
        queue_db_path=str(tmp_path / "jobs.sqlite"),
        cursor_path=str(tmp_path / "cursors.json"),
        source_budget=3,
    )

    report = build_legal_update_progressive_run_plan(
        config,
        pipeline=FakePipeline(),
        now=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    assert report["publication_mode"] == "guarded"
    assert report["green_source_codes"] == ["gazzetta_ufficiale"]
    assert report["plan"]["selected"][0]["source_code"] == "gazzetta_ufficiale"
    excluded = {row["source_code"]: row for row in report["excluded_sources"]}
    assert excluded["cassazione_massimario"]["classification"] == "osservazione"


def test_progressive_cycle_dry_run_non_accoda_e_non_esegue(tmp_path):
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    config = LegalAutoFetchConfig(
        intelligence_db=str(tmp_path / "motori.json"),
        queue_db_path=str(tmp_path / "jobs.sqlite"),
        cursor_path=str(tmp_path / "cursors.json"),
        source_budget=1,
    )

    report = run_legal_update_progressive_cycle(
        config,
        guarded_only=True,
        dry_run=True,
        pipeline=FakePipeline(),
        runner=runner,
        now=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    assert report["dry_run"] is True
    assert report["executed"] is False
    assert report["enqueued_jobs"] == []
    assert calls == []
    assert not (tmp_path / "jobs.sqlite").exists()


def test_progressive_cycle_richiede_guarded_only(tmp_path):
    config = LegalAutoFetchConfig(
        intelligence_db=str(tmp_path / "motori.json"),
        queue_db_path=str(tmp_path / "jobs.sqlite"),
        cursor_path=str(tmp_path / "cursors.json"),
    )

    with pytest.raises(ValueError, match="guarded-only"):
        run_legal_update_progressive_cycle(config, guarded_only=False, dry_run=True, pipeline=FakePipeline())


def test_progressive_cycle_rispetta_budget_timeout_e_publish_max(tmp_path):
    pipeline = FakePipeline()
    pipeline.repository.sources.append(
        {
            "id": 4,
            "code": "inps_circolari",
            "name": "INPS circolari",
            "base_url": "https://www.inps.it/",
            "category": "prassi",
            "enabled": True,
            "is_official": True,
            "polling_minutes": 1440,
        }
    )
    calls: list[tuple[list[str], int]] = []

    def runner(command, **kwargs):
        calls.append((list(command), int(kwargs.get("timeout") or 0)))
        if "--publish-only" in command:
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"published_count": 0}), stderr="")
        payload = {"ok": True, "payload": {"report": {"reports": [{"documents_found": 1, "processed": 1}]}}}
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    config = LegalAutoFetchConfig(
        intelligence_db=str(tmp_path / "motori.json"),
        giurisprudenza_db=str(tmp_path / "giurisprudenza.json"),
        queue_db_path=str(tmp_path / "jobs.sqlite"),
        cursor_path=str(tmp_path / "cursors.json"),
        source_budget=1,
        item_timeout_seconds=7,
        publish_max_items=2,
    )

    report = run_legal_update_progressive_cycle(
        config,
        guarded_only=True,
        dry_run=False,
        pipeline=pipeline,
        runner=runner,
        now=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    assert report["plan"]["selected_count"] == 1
    assert len(report["enqueued_jobs"]) == 1
    assert len([command for command, _timeout in calls if "--source-code" in command]) == 1
    assert len([command for command, _timeout in calls if "--publish-only" in command]) <= 2
    assert {timeout for _command, timeout in calls} == {7}


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


def test_health_report_regime_controllato_include_dashboard_retry_backfill(tmp_path):
    report = build_legal_updates_health_report(
        intelligence_db=str(tmp_path / "motori.json"),
        giurisprudenza_db=str(tmp_path / "giurisprudenza.json"),
        queue_db_path=str(tmp_path / "jobs.sqlite"),
        cursor_path=str(tmp_path / "cursors.json"),
        pipeline=FakePipeline(),
    )

    dashboard = report["source_quality_dashboard"]
    totals = dashboard["totals"]

    assert report["schema"] == "iusentra.legal_updates_health_report.v1"
    assert totals["fonti_attive"] == 1
    assert totals["fonti_in_osservazione"] == 1
    assert totals["fonti_non_pubblicabili"] >= 1
    assert report["scheduler"]["publication_mode"] == "guarded"
    assert report["pubblicazioni"]["uncontrolled_publication"] is False
    assert report["retry_sicuro"]["max_attempts"] == 3
    assert report["retry_sicuro"]["timeout_seconds"] == 120
    assert report["retry_sicuro"]["does_not_publish_without_guard"] is True
    assert set(report["backfill_periodico"]["allowed_missing_kinds"]) == {
        "attachments",
        "ocr",
        "references",
        "questions",
    }
    assert "--no-publish" in report["backfill_periodico"]["combined_command"]
    assert report["nuove_fonti"]["steps"] == [
        "capability",
        "fixture",
        "canary",
        "report",
        "pilot",
        "scheduler",
    ]


def test_giurisprudenza_structured_canary_non_forza_promozione_senza_chiavi(tmp_path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    report = build_giurisprudenza_structured_canary(pipeline=pipeline, limit=20)

    assert report["status"] == "chiuso_con_blocco_intenzionale"
    assert report["complete_candidate_count"] == 0
    assert "non viene forzata" in report["reason"]
