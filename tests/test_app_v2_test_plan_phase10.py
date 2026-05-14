from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "react-migration" / "generate_app_v2_test_docs.py"
SMOKE_ALL = REPO_ROOT / "scripts" / "smoke_app_v2_all.py"
TEST_PLAN = REPO_ROOT / "docs" / "test-plan-app-v2.md"
TEST_INVENTORY = REPO_ROOT / "docs" / "test-inventory.md"
TEST_MATRIX = REPO_ROOT / "docs" / "test-matrix-app-v2.md"
MANIFEST = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"


def _run(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def _load_generator():
    spec = importlib.util.spec_from_file_location("phase10_test_docs", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _priority(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    risk = str(route.get("risk") or "medium")
    if risk == "critical" or (risk == "high" and status != "react_operational_full"):
        return "P0"
    if risk == "high" or (risk == "medium" and status != "react_operational_full"):
        return "P1"
    if risk == "medium":
        return "P2"
    return "P3"


def test_phase10_docs_are_generated_and_deterministic() -> None:
    result = _run(str(GENERATOR), "--check")
    assert result.returncode == 0, result.stdout + result.stderr

    plan = TEST_PLAN.read_text(encoding="utf-8")
    inventory = TEST_INVENTORY.read_text(encoding="utf-8")
    matrix = TEST_MATRIX.read_text(encoding="utf-8")

    assert "# Piano test App V2" in plan
    assert "## Backend coverage" in plan
    assert "## Frontend coverage" in plan
    assert "## Commands recommended for CI" in plan
    assert "Nessun Vitest/Jest/React Testing Library coverage" in plan or "Non esistono Vitest/Jest/React Testing Library coverage" in plan
    assert "scripts\\smoke_app_v2_all.py" in plan
    assert "E2E completo" not in plan

    assert "# Inventario test IUSENTRA" in inventory
    assert "File pytest censiti" in inventory
    assert "| Area | Tipo test | File | Copre | Gap | Stato |" in inventory
    assert "frontend/package.json" in inventory

    assert "# Matrice test App V2" in matrix
    assert "| Area | Pagina | Priorita | Ruoli | Tenant | Flag | Backend | Frontend | RBAC | Tenant test | Feature flag | Contract | E2E/Smoke | Stato |" in matrix
    assert "tested" in matrix
    assert "partial" in matrix


def test_phase10_matrix_marks_p0_p1_full_routes_as_tested() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    routes = manifest["routes"]
    p0p1_full = [
        str(route["route"])
        for route in routes
        if route.get("status") == "react_operational_full" and _priority(route) in {"P0", "P1"}
    ]
    assert p0p1_full

    generator = _load_generator()
    generated = generator._matrix_rows(routes)
    by_route = {row[1]: row for row in generated}
    missing = [route for route in p0p1_full if by_route.get(route, [""])[-1] != "tested"]
    assert not missing


def test_phase10_smoke_inventory_runs_without_credentials_or_secrets() -> None:
    result = _run(str(SMOKE_ALL), "--subset", "inventory")
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "Smoke App V2 fase 10 completato" in output
    assert "Workflow App V2 censiti" in output
    assert "Mapping legacy -> App V2" in output
    assert "PasswordSicura" not in output
    assert "Operatore123" not in output
    assert "access_token" not in output

