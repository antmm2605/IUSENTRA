from __future__ import annotations

import json
import sqlite3
import subprocess
from types import SimpleNamespace

from pct.legal_update_batch_runner import (
    LegalUpdateJobConfig,
    build_legal_update_job_command,
    run_legal_update_batch_with_timeouts,
    run_legal_update_publish_queue_with_timeouts,
)
from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository


def test_legal_update_job_cli_pubblica_un_solo_elemento(monkeypatch, capsys):
    import pct.legal_update_job as job

    class _Pipeline:
        def publish_auto_news(self, *, limit):
            assert limit == 1
            return {"count": 1, "items": [{"id": 10}]}

        def dashboard_snapshot(self):
            return {"headline": {"review_pending": 0}}

    monkeypatch.setattr(job, "build_legal_update_pipeline", lambda *args, **kwargs: _Pipeline())

    rc = job.main(["--intelligence-db", "legal.json", "--publish-only", "--publish-limit", "1"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "publish"
    assert payload["published_count"] == 1


def test_legal_update_job_cli_backfill_evidenze_usa_limiti_governati(monkeypatch, capsys):
    import pct.legal_update_job as job

    calls: list[dict[str, object]] = []

    class _Pipeline:
        def backfill_web_verification_evidence(self, **kwargs):
            calls.append(kwargs)
            return {
                "ok": True,
                "checked": 2,
                "verification_evidence_saved": 2,
                "dashboard": {"headline": {"web_evidence": 2}},
            }

        def dashboard_snapshot(self):
            return {"headline": {"web_evidence": 2}}

    monkeypatch.setattr(job, "build_legal_update_pipeline", lambda *args, **kwargs: _Pipeline())

    rc = job.main(
        [
            "--intelligence-db",
            "legal.json",
            "--backfill-web-evidence",
            "--backfill-limit",
            "7",
            "--backfill-max-seconds",
            "15",
            "--backfill-status",
            "pending",
            "--source-code",
            "agcom_provvedimenti",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "backfill_web_evidence"
    assert calls == [
        {
            "limit": 7,
            "source_codes": ["agcom_provvedimenti"],
            "statuses": ("pending",),
            "include_closed": False,
            "include_open_data": False,
            "direct_only": True,
            "max_seconds": 15,
            "query": "",
            "review_ids": (),
        }
    ]

    rc = job.main(
        [
            "--intelligence-db",
            "legal.json",
            "--backfill-web-evidence",
            "--backfill-query",
            "Circolare numero 53 del 07-05-2026",
            "--backfill-review-id",
            "8807",
        ]
    )

    assert rc == 0
    json.loads(capsys.readouterr().out)
    assert calls[-1]["query"] == "Circolare numero 53 del 07-05-2026"
    assert calls[-1]["review_ids"] == (8807,)


def test_legal_update_job_command_esegue_fonte_singola_con_timeout_governabile():
    config = LegalUpdateJobConfig(
        intelligence_db="/data/intelligence/motori.json",
        giurisprudenza_db="/data/intelligence/giurisprudenza.json",
        ai_base_url="http://ollama:11434/api",
        ai_model="gemma3:1b",
        export_json_enabled=True,
        mirror_giurisprudenza_json_enabled=True,
        python_executable="python",
    )

    command = build_legal_update_job_command(config, source_code="normattiva", auto_publish=False)

    assert command[:3] == ["python", "-m", "pct.legal_update_job"]
    assert command[command.index("--source-code") + 1] == "normattiva"
    assert "--no-auto-publish" in command
    assert "--export-json" in command
    assert "--mirror-giurisprudenza-json" in command


def test_legal_update_batch_con_timeout_non_blocca_le_fonti_successive():
    calls: list[list[str]] = []

    def _runner(command, **kwargs):
        calls.append(command)
        source = command[command.index("--source-code") + 1]
        if source == "lenta":
            raise subprocess.TimeoutExpired(command, timeout=kwargs["timeout"])
        stdout = json.dumps({"ok": True, "mode": "source", "source_code": source})
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    report = run_legal_update_batch_with_timeouts(
        LegalUpdateJobConfig(intelligence_db="legal.json", python_executable="python"),
        source_codes=["lenta", "normattiva"],
        auto_publish=False,
        item_timeout_seconds=2,
        runner=_runner,
    )

    assert report["ok"] is False
    assert report["timeouts"] == 1
    assert [row["label"] for row in report["reports"]] == ["lenta", "normattiva"]
    assert len(calls) == 2
    assert all("started_at" in row and "finished_at" in row for row in report["reports"])


def test_legal_update_batch_registra_esito_agente_per_fonte(tmp_path):
    intelligence_db = tmp_path / "intelligence" / "motori.json"
    cfg = LegalUpdateDbConfig.from_anchor(str(intelligence_db))
    repository = LegalUpdateRepository(cfg.db_path, json_path=cfg.json_path)
    repository.upsert_sources(
        [
            {
                "name": "Normattiva",
                "code": "normattiva",
                "category": "normativa",
                "base_url": "https://www.normattiva.it/",
                "source_type": "web",
                "trust_class": "A",
                "is_official": True,
                "enabled": True,
                "polling_minutes": 720,
                "parser_type": "html",
            }
        ]
    )

    def _runner(command, **kwargs):
        source = command[command.index("--source-code") + 1]
        stdout = json.dumps(
            {
                "ok": True,
                "mode": "source",
                "source_code": source,
                "report": {
                    "reports": [
                        {
                            "source": source,
                            "documents_found": 3,
                            "processed": 2,
                            "skipped_unchanged": 1,
                        }
                    ],
                    "autopublished": {"count": 0},
                },
            }
        )
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    report = run_legal_update_batch_with_timeouts(
        LegalUpdateJobConfig(intelligence_db=str(intelligence_db), python_executable="python"),
        source_codes=["normattiva"],
        auto_publish=False,
        item_timeout_seconds=30,
        runner=_runner,
        record_agent_runs=True,
    )

    latest = repository.latest_source_agent_runs()["normattiva"]
    assert report["ok"] is True
    assert latest["status"] == "completed"
    assert latest["documents_found"] == 3
    assert latest["processed"] == 2
    assert latest["skipped_unchanged"] == 1
    assert latest["timeout_seconds"] == 30


def test_legal_update_batch_marca_fonte_fallita_se_report_interno_ha_errore(tmp_path):
    intelligence_db = tmp_path / "intelligence" / "motori.json"
    cfg = LegalUpdateDbConfig.from_anchor(str(intelligence_db))
    repository = LegalUpdateRepository(cfg.db_path, json_path=cfg.json_path)
    repository.upsert_sources(
        [
            {
                "name": "Giustizia Amministrativa",
                "code": "giustizia_amministrativa",
                "category": "giurisprudenza",
                "base_url": "https://www.giustizia-amministrativa.it/",
                "source_type": "web",
                "trust_class": "A",
                "is_official": True,
                "enabled": True,
                "polling_minutes": 720,
                "parser_type": "html",
            }
        ]
    )

    def _runner(command, **kwargs):
        source = command[command.index("--source-code") + 1]
        stdout = json.dumps(
            {
                "ok": True,
                "mode": "source",
                "source_code": source,
                "report": {
                    "reports": [
                        {
                            "source": source,
                            "documents_found": 0,
                            "processed": 0,
                            "error": "Fonte non raggiungibile",
                        }
                    ],
                    "autopublished": {"count": 0},
                },
            }
        )
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    report = run_legal_update_batch_with_timeouts(
        LegalUpdateJobConfig(intelligence_db=str(intelligence_db), python_executable="python"),
        source_codes=["giustizia_amministrativa"],
        auto_publish=False,
        item_timeout_seconds=30,
        runner=_runner,
        record_agent_runs=True,
    )

    latest = repository.latest_source_agent_runs()["giustizia_amministrativa"]
    assert report["ok"] is False
    assert report["reports"][0]["inner_errors"] == ["Fonte non raggiungibile"]
    assert latest["status"] == "failed"
    assert "Fonte non raggiungibile" in latest["error_message"]
    assert "OpenGA ufficiale" in latest["error_message"]


def test_source_agent_run_storico_completed_con_errore_viene_letto_da_verificare(tmp_path):
    intelligence_db = tmp_path / "intelligence" / "motori.json"
    repository = LegalUpdateRepository(**LegalUpdateDbConfig.from_anchor(str(intelligence_db)).__dict__)
    run = repository.record_source_agent_run(
        source_code="giustizia_amministrativa",
        source_name="Giustizia Amministrativa",
        status="completed",
        payload={"reports": [{"source": "giustizia_amministrativa", "error": "Errore SSL"}]},
    )
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE source_agent_runs SET status = 'completed', error_message = '' WHERE id = ?",
            (run["id"],),
        )
        conn.commit()

    recovered = repository.get_source_agent_run(run["id"])
    latest = repository.latest_source_agent_runs()["giustizia_amministrativa"]

    assert recovered is not None
    assert recovered["status"] == "failed"
    assert latest["status"] == "failed"
    assert "Errore SSL" in latest["error_message"]
    assert "OpenGA ufficiale" in latest["error_message"]


def test_legal_update_publish_queue_pubblica_un_elemento_per_job():
    calls = 0

    def _runner(command, **kwargs):
        nonlocal calls
        calls += 1
        count = 1 if calls == 1 else 0
        stdout = json.dumps({"ok": True, "mode": "publish", "published_count": count})
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    report = run_legal_update_publish_queue_with_timeouts(
        LegalUpdateJobConfig(intelligence_db="legal.json", python_executable="python"),
        item_timeout_seconds=5,
        max_items=10,
        runner=_runner,
    )

    assert report["ok"] is True
    assert report["published_count"] == 1
    assert calls == 2
