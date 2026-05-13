from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "app-v2-page-registry.md"
FRONTEND_PAGES_PATH = REPO_ROOT / "docs" / "frontend-app-v2-pages.md"
ROUTING_MAP_PATH = REPO_ROOT / "docs" / "legacy-to-app-v2-routing-map.md"
GENERATOR = REPO_ROOT / "scripts" / "react-migration" / "generate_app_v2_page_registry.py"
SMOKE = REPO_ROOT / "scripts" / "smoke_app_v2_pages.py"
ROUTING_SMOKE = REPO_ROOT / "scripts" / "smoke_app_v2_routing.py"
MANIFEST = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"


def _manifest_routes() -> list[dict[str, object]]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["routes"]


def test_app_v2_registry_docs_are_generated_and_complete():
    registry = REGISTRY_PATH.read_text(encoding="utf-8")
    frontend = FRONTEND_PAGES_PATH.read_text(encoding="utf-8")
    routing = ROUTING_MAP_PATH.read_text(encoding="utf-8")

    assert "Registro ufficiale pagine" in registry
    assert "Backlog per priorita" in frontend
    assert "routes.appV2.documents.list" in registry
    assert "routes.appV2.comms.deposits" in registry
    assert "routes.appV2.agenda.calendar" in registry
    assert "Fallback flag off" in registry
    assert "Protezione frontend" in registry
    assert "Protezione backend" in registry
    assert "Test flag on/off" in registry
    assert "Redirect strategy" in registry
    assert "Deep link support" in registry
    assert "Query params support" in registry
    assert "Stato finale fase 4" in registry
    assert "routes.appV2.dashboard.home" in frontend
    assert "Mappa routing legacy -> App V2" in routing
    assert "Query bloccate" in routing
    assert "Redirect attivati live in fase 4: 0" in routing
    assert "next" in routing
    assert "return_url" in routing

    for route in _manifest_routes():
        assert f"| {route['route']} |" in registry
        assert route["status"] in {"legacy_operational", "react_operational_partial", "react_operational_full"}


def test_app_v2_registry_generator_is_deterministic():
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Registro App V2 aggiornato" in result.stdout


def test_app_v2_registry_prioritizes_non_full_routes():
    registry = REGISTRY_PATH.read_text(encoding="utf-8")
    pending_routes = [
        route for route in _manifest_routes()
        if route["status"] != "react_operational_full"
    ]

    assert pending_routes
    for route in pending_routes:
        needle = f"| {route['route']} |"
        start = registry.index(needle)
        line = registry[start: registry.index("\n", start)]
        assert any(priority in line for priority in ("| P0 |", "| P1 |", "| P2 |", "| P3 |"))
        assert "non promossa" in line or "parziale" in line


def test_app_v2_smoke_script_lists_targets_without_credentials():
    result = subprocess.run(
        [sys.executable, str(SMOKE), "--list"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Manifest routes:" in result.stdout
    assert "/api/v1/ui/feature-flags" in result.stdout


def test_app_v2_routing_smoke_script_lists_targets_without_credentials():
    result = subprocess.run(
        [sys.executable, str(ROUTING_SMOKE), "--list"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Mapping legacy -> App V2:" in result.stdout
    assert "Open redirect bloccato" in result.stdout
