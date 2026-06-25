from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from scripts.check_runtime_services import (
    _compose_base,
    _run,
    expected_job_interval_seconds,
    filter_latest_runs_for_wait,
    parse_compose_ps_json,
    validate_compose_services,
    validate_container_versions,
    validate_scheduler_job,
    validate_scheduler_run_audit,
)


def _row(service: str, *, version: str = "2.253.108", state: str = "running", health: str = "healthy") -> dict:
    return {
        "Service": service,
        "State": state,
        "Health": health,
        "Image": f"iusentra-{service}",
        "Labels": f"org.opencontainers.image.version={version},com.docker.compose.service={service}",
    }


def test_run_decodifica_output_subprocess_in_utf8(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr("scripts.check_runtime_services.subprocess.run", fake_run)

    assert _run(["echo", "Integrità"], cwd=tmp_path) == "ok"
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["text"] is True


def test_parse_compose_ps_json_accetta_json_lines():
    output = "\n".join(json.dumps(_row(service)) for service in ("app", "scheduler-worker", "ocr-worker"))

    rows = parse_compose_ps_json(output)

    assert [row["Service"] for row in rows] == ["app", "scheduler-worker", "ocr-worker"]


def test_compose_base_supporta_env_file_produzione():
    command = _compose_base("deploy/hetzner/docker-compose.hetzner.yml", "/opt/iusentra/.env.hetzner")

    assert command == [
        "docker",
        "compose",
        "--env-file",
        "/opt/iusentra/.env.hetzner",
        "-f",
        "deploy/hetzner/docker-compose.hetzner.yml",
    ]


def test_validate_compose_services_blocca_worker_con_immagine_vecchia():
    rows = [
        _row("app", version="2.253.107"),
        _row("scheduler-worker", version="2.253.97"),
        _row("ocr-worker", version="2.253.107"),
        {"Service": "redis", "State": "running", "Health": "healthy", "Image": "redis:7-alpine", "Labels": ""},
    ]

    report = validate_compose_services(rows, expected_version="2.253.107")

    assert report["ok"] is False
    assert any("scheduler-worker" in error and "2.253.97" in error for error in report["errors"])


def test_validate_container_versions_blocca_runtime_non_allineato():
    report = validate_container_versions(
        {"app": "2.253.107", "scheduler-worker": "2.253.97", "ocr-worker": "2.253.107"},
        expected_version="2.253.107",
    )

    assert report["ok"] is False
    assert "scheduler-worker: pct.__version__=2.253.97" in report["errors"][0]


def test_validate_scheduler_job_richiede_sentenza_automatica_ogni_dieci_minuti():
    missing = validate_scheduler_job({"job": "", "trigger": ""}, job_id="lex_sentenza_economia_auto")
    wrong_trigger = validate_scheduler_job(
        {"job": "lex_sentenza_economia_auto", "trigger": "cron[minute='*/30']"},
        job_id="lex_sentenza_economia_auto",
    )
    ok = validate_scheduler_job(
        {"job": "lex_sentenza_economia_auto", "trigger": "cron[minute='*/10']"},
        job_id="lex_sentenza_economia_auto",
    )
    ok_staggered = validate_scheduler_job(
        {"job": "lex_sentenza_economia_auto", "trigger": "cron[minute='7-57/10']"},
        job_id="lex_sentenza_economia_auto",
    )

    assert missing["ok"] is False
    assert wrong_trigger["ok"] is False
    assert ok["ok"] is True
    assert ok_staggered["ok"] is True


def test_expected_job_interval_accetta_cron_sfalsato_ogni_dieci_minuti():
    assert expected_job_interval_seconds(_job(minute="7-57/10")) == 600


def test_filter_latest_runs_for_wait_filtra_solo_job_obbligatorio():
    since = datetime(2026, 6, 25, 10, 30, tzinfo=timezone.utc)
    latest = {
        "lex_sentenza_economia_auto": {
            "status": "completed",
            "finished_at": "2026-06-25T10:20:00Z",
        },
        "pst_certificati_cifratura_weekly": {
            "status": "failed",
            "finished_at": "2026-06-25T10:20:00Z",
        },
    }

    filtered = filter_latest_runs_for_wait(
        latest,
        target_job_id="lex_sentenza_economia_auto",
        since_utc=since,
    )

    assert "lex_sentenza_economia_auto" not in filtered
    assert filtered["pst_certificati_cifratura_weekly"]["status"] == "failed"


def _job(job_id: str = "lex_sentenza_economia_auto", *, minute: str = "*/10") -> dict:
    return {
        "job_id": job_id,
        "name": "Sentenze Lex ed economia",
        "family": "Lex AI",
        "enabled": True,
        "trigger_kind": "cron",
        "hour": "",
        "minute": minute,
        "day_of_week": "",
    }


def test_validate_scheduler_run_audit_blocca_job_mai_eseguito_dopo_finestra():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {"jobs": [_job()], "latest_runs": {}},
        now=now,
        worker_started_at=now - timedelta(minutes=20),
    )

    assert report["ok"] is False
    assert any("nessun run registrato" in error for error in report["errors"])
    assert report["jobs"][0]["status"] == "never_ran"


def test_validate_scheduler_run_audit_non_blocca_job_non_ancora_dovuto():
    now = datetime(2026, 6, 25, 10, 4, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {"jobs": [_job("legal_official_archives_daily", minute="0")], "latest_runs": {}},
        job_id="",
        now=now,
        worker_started_at=now - timedelta(minutes=4),
    )

    assert report["ok"] is True
    assert report["jobs"][0]["status"] == "not_due"


def test_validate_scheduler_run_audit_distingue_stale_prima_della_finestra_post_restart():
    now = datetime(2026, 6, 25, 10, 4, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job("legal_official_archives_daily", minute="0")],
            "latest_runs": {
                "legal_official_archives_daily": {
                    "status": "completed",
                    "finished_at": "2026-06-20T23:00:00Z",
                    "message": "Esecuzione completata dal worker.",
                }
            },
        },
        job_id="",
        now=now,
        require_all_due=True,
        worker_started_at=now - timedelta(minutes=4),
    )

    assert report["ok"] is True
    assert report["jobs"][0]["status"] == "not_due_after_restart"
    assert "prossima scadenza" in report["jobs"][0]["reason"]


def test_validate_scheduler_run_audit_non_blocca_heartbeat_interno():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {"jobs": [_job("scheduler_registry_reload", minute="*/1")], "latest_runs": {}},
        job_id="",
        now=now,
        require_all_due=True,
        worker_started_at=now - timedelta(minutes=20),
    )

    assert report["ok"] is True
    assert report["jobs"][0]["status"] == "internal_control"


def test_validate_scheduler_run_audit_blocca_ultimo_run_fallito_con_motivo():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job()],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "status": "failed",
                    "finished_at": "2026-06-25T10:30:00Z",
                    "message": "Esecuzione non completata dal worker.",
                    "error_message": "database is locked",
                    "result": {"ok": False, "error": "database is locked"},
                }
            },
        },
        now=now,
    )

    assert report["ok"] is False
    assert any("database is locked" in error for error in report["errors"])
    assert report["jobs"][0]["status"] == "failed"


def test_validate_scheduler_run_audit_blocca_run_in_corso_oltre_tempo():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job()],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "status": "running",
                    "started_at": "2026-06-25T08:00:00Z",
                    "created_at": "2026-06-25T08:00:00Z",
                    "message": "Esecuzione avviata dal worker.",
                    "result": {"ok": True, "event": "submitted"},
                }
            },
        },
        now=now,
    )

    assert report["ok"] is False
    assert any("run in corso oltre" in error for error in report["errors"])
    assert report["jobs"][0]["status"] == "stale_running"


def test_validate_scheduler_run_audit_job_obbligatorio_running_non_e_verde():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job()],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "status": "running",
                    "started_at": "2026-06-25T10:39:00Z",
                    "created_at": "2026-06-25T10:39:00Z",
                    "message": "Esecuzione avviata dal worker.",
                    "result": {"ok": True, "event": "submitted"},
                }
            },
        },
        now=now,
    )

    assert report["ok"] is False
    assert any("non ancora completato" in error for error in report["errors"])
    assert report["jobs"][0]["status"] == "running"


def test_validate_scheduler_run_audit_accetta_completed_recente_se_run_successiva_in_corso():
    now = datetime(2026, 6, 25, 10, 48, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job(minute="7-57/10")],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "job_id": "lex_sentenza_economia_auto",
                    "status": "running",
                    "started_at": "2026-06-25T10:47:00Z",
                    "created_at": "2026-06-25T10:47:00Z",
                    "message": "Esecuzione avviata dal worker.",
                    "result": {"ok": True, "event": "submitted"},
                }
            },
            "recent_runs": [
                {
                    "job_id": "lex_sentenza_economia_auto",
                    "status": "completed",
                    "finished_at": "2026-06-25T10:40:13Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {
                        "ok": True,
                        "totals": {
                            "documents_seen": 4408,
                            "sentenze_found": 53,
                            "matrix_confirmed": 17,
                            "vector_indexed": 17,
                            "errors": 0,
                            "vector_embedding_errors": 0,
                        },
                    },
                }
            ],
        },
        now=now,
        worker_started_at=now - timedelta(minutes=15),
    )

    assert report["ok"] is True
    assert report["jobs"][0]["status"] == "ok"
    assert report["jobs"][0]["totals"]["sentenze_found"] == 53
    assert report["jobs"][0]["superseded_running_started_at"] == "2026-06-25T10:47:00Z"


def test_validate_scheduler_run_audit_running_stale_blocca_anche_con_completed_recente():
    now = datetime(2026, 6, 25, 10, 48, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job(minute="7-57/10")],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "job_id": "lex_sentenza_economia_auto",
                    "status": "running",
                    "started_at": "2026-06-25T08:00:00Z",
                    "created_at": "2026-06-25T08:00:00Z",
                    "message": "Esecuzione avviata dal worker.",
                    "result": {"ok": True, "event": "submitted"},
                }
            },
            "recent_runs": [
                {
                    "job_id": "lex_sentenza_economia_auto",
                    "status": "completed",
                    "finished_at": "2026-06-25T10:40:13Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {
                        "ok": True,
                        "totals": {
                            "documents_seen": 4408,
                            "sentenze_found": 53,
                            "matrix_confirmed": 17,
                            "vector_indexed": 17,
                            "errors": 0,
                            "vector_embedding_errors": 0,
                        },
                    },
                }
            ],
        },
        now=now,
        worker_started_at=now - timedelta(hours=3),
    )

    assert report["ok"] is False
    assert any("run in corso oltre" in error for error in report["errors"])
    assert report["jobs"][0]["status"] == "stale_running"


def test_validate_scheduler_run_audit_blocca_run_senza_totals_operativi():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job()],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "status": "completed",
                    "finished_at": "2026-06-25T10:39:00Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {"ok": True},
                }
            },
        },
        now=now,
    )

    assert report["ok"] is False
    assert any("senza riepilogo operativo" in error for error in report["errors"])


def test_validate_scheduler_run_audit_accetta_job_sentenza_eseguito_con_totals():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job()],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "status": "completed",
                    "finished_at": "2026-06-25T10:39:00Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {
                        "ok": True,
                        "totals": {
                            "documents_seen": 4,
                            "sentenze_found": 1,
                            "matrix_confirmed": 1,
                            "applied": 1,
                            "vector_indexed": 1,
                            "errors": 0,
                            "vector_embedding_errors": 0,
                        },
                    },
                }
            },
        },
        now=now,
    )

    assert report["ok"] is True
    assert report["jobs"][0]["status"] == "ok"
    assert report["jobs"][0]["totals"]["matrix_confirmed"] == 1


def test_validate_scheduler_run_audit_accetta_job_sentenza_incrementale_senza_nuovi_documenti():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job()],
            "latest_runs": {
                "lex_sentenza_economia_auto": {
                    "status": "completed",
                    "finished_at": "2026-06-25T10:39:00Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {
                        "ok": True,
                        "scan_mode": "incremental",
                        "incremental": {"newest_mtime_ns": 123},
                        "totals": {
                            "documents_catalogued": 4408,
                            "documents_seen": 0,
                            "skipped_by_cursor": 4408,
                            "sentenze_found": 0,
                            "matrix_confirmed": 0,
                            "vector_indexed": 0,
                            "errors": 0,
                            "vector_embedding_errors": 0,
                        },
                    },
                }
            },
        },
        now=now,
    )

    assert report["ok"] is True
    assert report["jobs"][0]["status"] == "ok"
    assert report["jobs"][0]["totals"]["documents_seen"] == 0


def test_validate_scheduler_run_audit_blocca_job_operativo_senza_totals():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job("pec_audit_pipeline_workers", minute="*/5"), _job(minute="7-57/10")],
            "latest_runs": {
                "pec_audit_pipeline_workers": {
                    "status": "completed",
                    "finished_at": "2026-06-25T10:39:00Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {"ok": True},
                },
                "lex_sentenza_economia_auto": {
                    "status": "completed",
                    "finished_at": "2026-06-25T10:37:00Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {
                        "ok": True,
                        "totals": {
                            "documents_seen": 0,
                            "errors": 0,
                            "vector_embedding_errors": 0,
                        },
                    },
                },
            },
        },
        job_id="lex_sentenza_economia_auto",
        now=now,
        require_all_due=True,
        worker_started_at=now - timedelta(minutes=20),
    )

    assert report["ok"] is False
    assert any("senza riepilogo operativo" in error for error in report["errors"])
    assert report["jobs"][0]["status"] == "failed"


def test_validate_scheduler_run_audit_accetta_job_operativo_con_totals():
    now = datetime(2026, 6, 25, 10, 40, tzinfo=timezone.utc)

    report = validate_scheduler_run_audit(
        {
            "jobs": [_job("pec_audit_pipeline_workers", minute="*/5"), _job(minute="7-57/10")],
            "latest_runs": {
                "pec_audit_pipeline_workers": {
                    "status": "completed",
                    "finished_at": "2026-06-25T10:39:00Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {
                        "ok": True,
                        "scan_mode": "incremental",
                        "totals": {
                            "archive_seen": 667,
                            "scanned": 1,
                            "ingested": 0,
                            "processed_jobs": 0,
                            "failed_jobs": 0,
                            "errors": 0,
                        },
                    },
                },
                "lex_sentenza_economia_auto": {
                    "status": "completed",
                    "finished_at": "2026-06-25T10:37:00Z",
                    "message": "Esecuzione completata dal worker.",
                    "result": {
                        "ok": True,
                        "totals": {
                            "documents_seen": 0,
                            "errors": 0,
                            "vector_embedding_errors": 0,
                        },
                    },
                },
            },
        },
        job_id="lex_sentenza_economia_auto",
        now=now,
        require_all_due=True,
        worker_started_at=now - timedelta(minutes=20),
    )

    assert report["ok"] is True
    assert report["jobs"][0]["status"] == "ok"
    assert report["jobs"][0]["totals"]["scanned"] == 1
