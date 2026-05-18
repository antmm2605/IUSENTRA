from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_ui_coverage_validator_passes() -> None:
    result = run_command("scripts/validate_ui_coverage.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK | UI coverage fase 9" in result.stdout
    assert "Storybook=presente" in result.stdout
    assert "VRT=non attivo" in result.stdout


def test_ui_fixture_uses_safe_mock_data_only() -> None:
    payload = json.loads((ROOT / "frontend/src/test/fixtures/app-v2-ui-fixtures.json").read_text(encoding="utf-8"))
    assert payload["phase"] == "9"
    assert set(payload["users"]) >= {"admin", "avvocato", "collaboratore", "readonly"}
    assert set(payload["tenants"]) >= {"tenantA", "tenantB"}
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "example.invalid" in serialized
    assert "116.203.45.57" not in serialized
    assert "sk_live" not in serialized
    assert "bearer " not in serialized


def test_phase9_docs_do_not_claim_storybook_or_vrt_ready() -> None:
    ui_doc = (ROOT / "docs/ui-regression-and-storybook.md").read_text(encoding="utf-8")
    frontend_doc = (ROOT / "docs/frontend-app-v2-pages.md").read_text(encoding="utf-8")
    registry_doc = (ROOT / "docs/app-v2-page-registry.md").read_text(encoding="utf-8")
    assert "Storybook: presente" in ui_doc
    assert "Storybook: non introdotto" not in ui_doc
    assert "VRT: non attivo" in ui_doc
    assert "Copertura UI fase 9" in frontend_doc
    assert "Copertura UI fase 9" in registry_doc
    forbidden_claims = ("storybook_ready", "vrt_ready")
    assert all(claim not in ui_doc for claim in forbidden_claims)
    assert all(claim not in frontend_doc for claim in forbidden_claims)
    assert all(claim not in registry_doc for claim in forbidden_claims)
