from __future__ import annotations

import html
import json
import re
from pathlib import Path

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_TSX = REPO_ROOT / "frontend" / "src" / "App.tsx"
REACT_SHELL = REPO_ROOT / "web" / "blueprints" / "react_shell.py"
PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
FRONTEND_DOC = REPO_ROOT / "docs" / "frontend-app-v2-pages.md"
REGISTRY_DOC = REPO_ROOT / "docs" / "app-v2-page-registry.md"


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    return app


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_app_v2_phase7_frontend_guard_is_source_locked():
    app_text = _read(APP_TSX)
    shell_text = _read(REACT_SHELL)
    package_text = _read(PACKAGE_JSON)
    ci_text = _read(CI_WORKFLOW)

    for snippet in (
        "appV2NavigationActive(activePath)",
        "appV2UnknownRoute",
        "AppV2NotFoundPage",
        "visibleNavSections",
        "shouldShowNavItem",
        "requiredPermissionsForHref",
        "appV2FeatureFlagForPath(item.href)",
        "isFeatureFlagEnabledSync(flag)",
        "effectiveStandalonePage = isStandalonePage || appV2FlagDenied || appV2UnknownRoute",
    ):
        assert snippet in app_text

    for forbidden in ("localStorage", "sessionStorage", "return_url", "tenant_id=", "studio_id="):
        assert forbidden not in app_text

    assert '"permissions": permissions' in shell_text
    assert "permessi_effettivi" in shell_text
    assert '"test:app-v2"' in package_text
    assert "Frontend App V2 gates" in ci_text
    assert "npm --prefix frontend run test" in ci_text
    assert "npm --prefix frontend run typecheck" in ci_text
    assert "npm --prefix frontend run build" in ci_text


def test_react_shell_bootstrap_exposes_real_rbac_permissions(tmp_path: Path):
    app = _app(tmp_path)

    with app.test_client() as client:
        _login(client)
        response = client.get("/app-v2/area-non-censita")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    match = re.search(
        r'<script id="iusentra-react-bootstrap" type="application/json">(.*?)</script>',
        body,
        re.S,
    )
    assert match, body
    payload = json.loads(html.unescape(match.group(1)))

    assert payload["user"]["username"] == "operatore"
    assert payload["user"]["displayName"] == "Operatore Test"
    assert "permissions" in payload
    assert "fascicoli.leggi" in payload["permissions"]
    assert "utenti.leggi" in payload["permissions"]
    assert "featureFlags" in payload


def test_phase7_docs_track_complete_partial_and_pending_frontend_states():
    frontend = _read(FRONTEND_DOC)
    registry = _read(REGISTRY_DOC)

    assert "## Stato frontend fase 7" in frontend
    assert "## Stato frontend fase 7" in registry
    assert "404 sicura App V2" in registry
    assert "| Area | Pagina | App V2 URL | Legacy URL | Component | Flag | API | OpenAPI | RBAC UI | Stati UI | Test | Stato |" in frontend
    assert "| comunicazioni | /notifiche-legali | /app/notifiche-legali | /notifiche-legali | frontend/src/components/NotificheLegaliPage.tsx |" in frontend
    assert "| telematico | /deposito/checklist | /app/telematico | /deposito/checklist | frontend/src/components/TelematicoSurfacePage.tsx |" in frontend
    assert "| documenti | /checklist | /app | /checklist | frontend/src/components/ChecklistPage.tsx |" in frontend
    assert "complete_tested" in frontend
    assert "partial" in frontend
    assert "pending" in frontend
    assert "flag-off" in frontend
    assert "forbidden" in frontend
    assert "readonly" in frontend
