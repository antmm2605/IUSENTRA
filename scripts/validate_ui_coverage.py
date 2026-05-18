from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"
FRONTEND_DOC_PATH = REPO_ROOT / "docs" / "frontend-app-v2-pages.md"
REGISTRY_DOC_PATH = REPO_ROOT / "docs" / "app-v2-page-registry.md"
UI_DOC_PATH = REPO_ROOT / "docs" / "ui-regression-and-storybook.md"
FIXTURES_PATH = REPO_ROOT / "frontend" / "src" / "test" / "fixtures" / "app-v2-ui-fixtures.json"
PACKAGE_JSON_PATH = REPO_ROOT / "frontend" / "package.json"

REQUIRED_UI_STATES = {"default", "loading", "empty", "error", "forbidden", "flag-off", "readonly"}
REQUIRED_FIXTURE_KEYS = {
    "fascicolo",
    "documento",
    "documentoUpload",
    "comunicazione",
    "deposito",
    "scadenza",
    "eventoAgenda",
    "cliente",
    "notifica",
    "auditLog",
    "settingsMascherati",
}
SECRET_KEY_PARTS = ("password", "secret", "token", "api_key", "apikey", "chiave")
MASKED_VALUES = {"********", "dato mascherato", "percorso mascherato", "non configurato", "non comunicato"}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


class CoverageError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise CoverageError(message)


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"File mancante: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        fail(f"JSON non valido in {path.relative_to(REPO_ROOT)}: {exc}")


def priority(route: dict[str, Any]) -> str:
    status = str(route.get("status") or "")
    risk = str(route.get("risk") or "medium")
    if risk == "critical" or (risk == "high" and status != "react_operational_full"):
        return "P0"
    if risk == "high" or (risk == "medium" and status != "react_operational_full"):
        return "P1"
    if risk == "medium":
        return "P2"
    return "P3"


def storybook_present() -> bool:
    package = load_json(PACKAGE_JSON_PATH)
    scripts = package.get("scripts", {})
    if any("storybook" in str(key).lower() or "storybook" in str(value).lower() for key, value in scripts.items()):
        return True
    if (REPO_ROOT / ".storybook").exists() or (REPO_ROOT / "frontend" / ".storybook").exists():
        return True
    story_patterns = ["*.stories.ts", "*.stories.tsx", "*.stories.js", "*.stories.jsx", "*.mdx"]
    return any(next((REPO_ROOT / "frontend").rglob(pattern), None) is not None for pattern in story_patterns)


def phase9_lines(doc: str) -> list[str]:
    marker = "## Copertura UI fase 9"
    if marker not in doc:
        fail("docs/frontend-app-v2-pages.md: manca la sezione Copertura UI fase 9")
    section = doc.split(marker, 1)[1]
    next_section = section.find("\n## ")
    if next_section >= 0:
        section = section[:next_section]
    return [line for line in section.splitlines() if line.startswith("| ")]


def parse_phase9_rows(doc: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in phase9_lines(doc):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 11 or cells[0] in {"Area", "---"}:
            continue
        rows[cells[1]] = line
    return rows


def validate_fixtures(payload: dict[str, Any]) -> None:
    if payload.get("schemaVersion") != 1 or payload.get("phase") != "9":
        fail("Fixture UI: schemaVersion=1 e phase=9 sono obbligatori")
    resources = payload.get("resources")
    if not isinstance(resources, dict):
        fail("Fixture UI: manca resources")
    missing = sorted(REQUIRED_FIXTURE_KEYS - set(resources))
    if missing:
        fail("Fixture UI: resources mancanti: " + ", ".join(missing))
    users = payload.get("users")
    tenants = payload.get("tenants")
    if not isinstance(users, dict) or not {"admin", "avvocato", "collaboratore", "readonly"}.issubset(users):
        fail("Fixture UI: utenti admin/avvocato/collaboratore/readonly mancanti")
    if not isinstance(tenants, dict) or not {"tenantA", "tenantB"}.issubset(tenants):
        fail("Fixture UI: tenant A/B mancanti")

    def walk(value: Any, path: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
            return
        if not isinstance(value, str):
            return
        for match in EMAIL_RE.findall(value):
            if not (match.endswith("@example.invalid") or match.endswith("@pec.example.invalid")):
                fail(f"Fixture UI: email non fittizia in {path}: {match}")
        key = path.lower().split(".")[-1]
        if any(part in key for part in SECRET_KEY_PARTS) and value.lower() not in MASKED_VALUES:
            fail(f"Fixture UI: segreto non mascherato in {path}")
        forbidden_fragments = ["bearer ", "sk_live", "sk_test", "pk_live", "pk_test", "116.203.45.57"]
        if any(fragment in value.lower() for fragment in forbidden_fragments):
            fail(f"Fixture UI: valore sensibile vietato in {path}")

    walk(payload)


def validate_docs() -> tuple[int, int]:
    manifest = load_json(MANIFEST_PATH)
    routes = manifest.get("routes")
    if not isinstance(routes, list):
        fail("route-manifest.json: routes non e' una lista")

    frontend_doc = read_text(FRONTEND_DOC_PATH)
    registry_doc = read_text(REGISTRY_DOC_PATH)
    ui_doc = read_text(UI_DOC_PATH)
    fixtures = load_json(FIXTURES_PATH)

    for text, label in [
        (frontend_doc, "docs/frontend-app-v2-pages.md"),
        (registry_doc, "docs/app-v2-page-registry.md"),
    ]:
        if "Copertura UI fase 9" not in text:
            fail(f"{label}: manca Copertura UI fase 9")
        if "vrt_ready" in text or "storybook_ready" in text:
            fail(f"{label}: non deve dichiarare Storybook/VRT ready in fase 9")

    storybook_is_present = storybook_present()
    expected_storybook_status = "Storybook: presente" if storybook_is_present else "Storybook: non introdotto"
    required_doc_snippets = [
        expected_storybook_status,
        "VRT: non attivo",
        "frontend/src/test/fixtures/app-v2-ui-fixtures.json",
        "python scripts\\validate_ui_coverage.py",
        "RBAC",
        "Feature Flag",
        "Accessibilita",
        "Design System Consistency",
    ]
    for snippet in required_doc_snippets:
        if snippet not in ui_doc:
            fail(f"docs/ui-regression-and-storybook.md: manca '{snippet}'")

    if storybook_is_present and "Storybook: non introdotto" in ui_doc:
        fail("Storybook risulta presente ma il documento lo dichiara non introdotto")
    if storybook_is_present and "Storybook: presente" not in ui_doc:
        fail("Storybook risulta presente ma il documento non lo dichiara")
    if not storybook_is_present and "Storybook: non introdotto" not in ui_doc:
        fail("Storybook assente: il documento deve dichiararlo esplicitamente")

    validate_fixtures(fixtures)
    rows = parse_phase9_rows(frontend_doc)
    p0p1 = [route for route in routes if priority(route) in {"P0", "P1"}]
    p0p1_full = [route for route in p0p1 if route.get("status") == "react_operational_full"]

    for route in p0p1_full:
        path = str(route.get("route") or "")
        component = str(route.get("targetComponent") or "")
        if not component or not (REPO_ROOT / component).exists():
            fail(f"{path}: componente React non trovato: {component}")
        row = rows.get(path)
        if not row:
            fail(f"{path}: riga fase 9 mancante in docs/frontend-app-v2-pages.md")
        lowered = row.lower()
        if "ui_tested" not in lowered:
            fail(f"{path}: P0/P1 full non marcata ui_tested")
        for state in REQUIRED_UI_STATES:
            if state not in lowered:
                fail(f"{path}: stato UI fase 9 mancante: {state}")
        if "validate_ui_coverage" not in lowered or "check-app-v2-frontend" not in lowered:
            fail(f"{path}: component test fase 9 non collegato ai gate reali")

    for route in p0p1:
        if route.get("status") == "react_operational_full":
            continue
        path = str(route.get("route") or "")
        row = rows.get(path)
        if row and "ui_tested" in row.lower():
            fail(f"{path}: pagina non full marcata impropriamente ui_tested")

    return len(p0p1), len(p0p1_full)


def main() -> int:
    try:
        p0p1, p0p1_full = validate_docs()
    except CoverageError as exc:
        print(f"ERRORE | UI coverage fase 9 | {exc}", file=sys.stderr)
        return 1
    storybook = "presente" if storybook_present() else "non introdotto"
    print(
        "OK | UI coverage fase 9 | "
        f"P0/P1={p0p1} | P0/P1 full ui_tested={p0p1_full} | "
        f"Storybook={storybook} | VRT=non attivo"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
