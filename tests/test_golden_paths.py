from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pct.cli import cli
from pct.golden_paths import build_golden_path_payload, run_golden_path_suites


def test_build_golden_path_payload_senza_report_mostra_suite_ufficiali(tmp_path):
    payload = build_golden_path_payload(base_dir=str(tmp_path))

    assert payload["summary"]["paths_total"] >= 5
    assert payload["summary"]["not_run"] == payload["summary"]["paths_total"]
    assert payload["rows"][0]["status"] == "not_run"


def test_run_golden_path_suites_persist_report(monkeypatch, tmp_path):
    class _Result:
        def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _fake_run(cmd, cwd, capture_output, text, encoding, errors, check):
        assert cmd[:3] == [__import__("sys").executable, "-m", "pytest"]
        return _Result(0, "... 12 passed in 1.23s")

    monkeypatch.setattr("pct.golden_paths.subprocess.run", _fake_run)

    report = run_golden_path_suites(base_dir=str(tmp_path), cwd=str(tmp_path))
    latest_report = Path(tmp_path) / "golden_paths_latest.json"

    assert report["success"] is True
    assert latest_report.exists()
    payload = json.loads(latest_report.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert len(payload["suites"]) >= 5


def test_cli_golden_path_restituisce_json(monkeypatch, tmp_path):
    runner = CliRunner()

    monkeypatch.setattr(
        "pct.cli.run_golden_path_suites",
        lambda *, base_dir, cwd: {
            "generated_at": "2026-04-19T18:00:00",
            "report_path": str(Path(base_dir) / "golden_paths_20260419_180000.json"),
            "success": True,
            "suites": [],
        },
    )
    monkeypatch.setattr(
        "pct.cli.build_golden_path_payload",
        lambda *, base_dir, report_payload=None: {
            "summary": {"paths_total": 6, "passed": 6, "failed": 0, "not_run": 0},
            "rows": [],
        },
    )

    result = runner.invoke(cli, ["golden-path", "--report-dir", str(tmp_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["paths_total"] == 6
    assert payload["report_path"].endswith(".json")
