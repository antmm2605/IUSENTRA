from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

from pct.legal_update_batch_runner import (
    LegalUpdateJobConfig,
    build_legal_update_job_command,
    run_legal_update_batch_with_timeouts,
    run_legal_update_publish_queue_with_timeouts,
)


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
