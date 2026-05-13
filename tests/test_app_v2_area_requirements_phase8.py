from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AREA_REQUIREMENTS_DOC = REPO_ROOT / "docs" / "app-v2-area-requirements.md"
AREA_GENERATOR = REPO_ROOT / "scripts" / "react-migration" / "generate_app_v2_area_requirements.py"
WORKFLOW_SMOKE = REPO_ROOT / "scripts" / "smoke_app_v2_workflows.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def test_phase8_area_requirements_doc_is_generated_and_source_locked():
    result = _run(str(AREA_GENERATOR), "--check")
    assert result.returncode == 0, result.stderr + result.stdout

    doc = AREA_REQUIREMENTS_DOC.read_text(encoding="utf-8")
    assert "fase 8 `fasereact`" in doc
    assert "| Area | Pagine | URL App V2 | Flag | RBAC | PII | Workflow | Test richiesti | Test presenti | Priorita | Stato |" in doc
    assert "Comunicazioni, PEC e notifiche legali" in doc
    assert "Impostazioni e integrazioni" in doc
    assert "Servizi telematici" in doc
    assert "scripts/smoke_app_v2_workflows.py --list" in doc
    assert "complete_tested" in doc
    assert "partial" in doc
    assert "blocked" in doc
    assert "not_present" not in doc
    assert "segreti mai restituiti in chiaro" in doc
    assert "Local Signer fail-closed" in doc


def test_complete_tested_area_does_not_hide_pending_or_partial_routes():
    generator = _load_module(AREA_GENERATOR, "phase8_area_generator")
    routes = generator._read_manifest()
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for route in routes:
        grouped[generator._area_for_route(route)].append(route)

    complete_areas = [
        area
        for area, area_routes in grouped.items()
        if generator._area_status(area, area_routes) == "complete_tested"
    ]
    assert {"agenda", "anagrafiche", "comunicazioni", "impostazioni"}.issubset(set(complete_areas))
    assert "documenti" not in complete_areas
    assert "telematico" not in complete_areas

    for area in complete_areas:
        statuses = {str(route.get("status") or "") for route in grouped[area]}
        assert statuses == {"react_operational_full"}, (area, statuses)


def test_workflow_smoke_lists_real_p0_p1_workflows_without_secrets():
    result = _run(str(WORKFLOW_SMOKE), "--list")
    assert result.returncode == 0, result.stderr + result.stdout
    output = result.stdout
    for expected in (
        "P0 fascicoli",
        "P0 documenti",
        "P0 comunicazioni",
        "P0 amministrazione",
        "P0 impostazioni",
        "P1 agenda",
        "IUSENTRA_ADMIN_USER",
        "IUSENTRA_TENANT_A_USER",
        "IUSENTRA_READONLY_PASSWORD",
    ):
        assert expected in output
    assert "PasswordSicura" not in output
    assert "Operatore123" not in output
    assert "access_token" not in output


def test_workflow_smoke_requires_credentials_when_requested():
    env = os.environ.copy()
    for key in (
        "IUSENTRA_ADMIN_USER",
        "IUSENTRA_ADMIN_PASSWORD",
        "IUSENTRA_TENANT_A_USER",
        "IUSENTRA_TENANT_A_PASSWORD",
        "IUSENTRA_TENANT_B_USER",
        "IUSENTRA_TENANT_B_PASSWORD",
        "IUSENTRA_READONLY_USER",
        "IUSENTRA_READONLY_PASSWORD",
    ):
        env.pop(key, None)

    result = _run(str(WORKFLOW_SMOKE), "--require-credentials", env=env)
    assert result.returncode == 2
    assert "Smoke workflow autenticato non eseguito" in result.stdout
    assert "IUSENTRA_ADMIN_USER" in result.stderr
    assert "IUSENTRA_READONLY_PASSWORD" in result.stderr
