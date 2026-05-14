from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.smoke_lib import (
    SEVERITY_CRITICAL,
    STATUS_FAIL,
    STATUS_PASS,
    SmokeCheck,
    SmokeReport,
    build_url,
    make_check,
    redact,
    utc_now,
    write_json_report,
)


def test_redact_masks_secret_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IUSENTRA_ADMIN_PASSWORD", "SecretSmokePassword123")
    text = "login failed for password=SecretSmokePassword123 token=abc.def"

    redacted = redact(text)

    assert "SecretSmokePassword123" not in redacted
    assert "abc.def" not in redacted
    assert "[redacted]" in redacted


def test_build_url_rejects_external_paths() -> None:
    assert build_url("https://app.example.test", "/api/pronto") == "https://app.example.test/api/pronto"
    with pytest.raises(ValueError):
        build_url("https://app.example.test", "https://evil.example/path")


def test_json_report_shape_excludes_secret_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IUSENTRA_SMOKE_API_KEY", "test-api-key-secret")
    report = SmokeReport(
        started_at=utc_now(),
        base_url="https://app.example.test",
        environment="staging",
        read_only=True,
        checks=[
            make_check("health", "readiness", STATUS_PASS, SEVERITY_CRITICAL, "ok"),
            make_check("auth", "secret", STATUS_FAIL, SEVERITY_CRITICAL, "token=test-api-key-secret"),
        ],
    )
    report.finish()
    output = tmp_path / "smoke-report.json"

    write_json_report(report, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["summary"]["pass"] == 1
    assert payload["summary"]["fail"] == 1
    assert payload["checks"][1]["message"] == "token=[redacted]"
    assert "test-api-key-secret" not in output.read_text(encoding="utf-8")


def test_report_failure_policy() -> None:
    report = SmokeReport(
        started_at=utc_now(),
        base_url="http://127.0.0.1:8080",
        environment="local",
        read_only=True,
        checks=[SmokeCheck("tenant", "cross-tenant", STATUS_FAIL, SEVERITY_CRITICAL, "blocked")],
    )

    assert report.has_failure()
