from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    "README.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/index.md",
    "docs/architecture.md",
    "docs/app-v2.md",
    "docs/api-contracts.md",
    "docs/test-plan-app-v2.md",
    "docs/ci-cd-gates.md",
    "docs/ui-regression-and-storybook.md",
    "docs/release-rollout.md",
    "docs/troubleshooting.md",
    "docs/database-and-migrations.md",
    "docs/release-notes-app-v2.md",
]

CODE_BLOCK_RE = re.compile(r"```(?:bash|powershell|shell|sh|text)?\n(.*?)```", re.S)

WORKFLOWS = [
    ".github/workflows/ci.yml",
    ".github/workflows/frontend-ci.yml",
    ".github/workflows/security-supply-chain.yml",
    ".github/workflows/smoke-staging.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/dependency-review.yml",
]

REQUIRED_PATHS = [
    "scripts/react-migration/generate_app_v2_page_registry.py",
    "scripts/react-migration/generate_app_v2_area_requirements.py",
    "scripts/react-migration/generate_app_v2_test_docs.py",
    "scripts/react-migration/generate_api_contracts.py",
    "scripts/validate_openapi.py",
    "scripts/verify_openapi_provider.py",
    "scripts/smoke_app_v2_all.py",
    "scripts/smoke_app_v2_pages.py",
    "scripts/smoke_app_v2_routing.py",
    "scripts/smoke_app_v2_workflows.py",
    "scripts/smoke_backend_security.py",
    "scripts/validate_ui_coverage.py",
    "scripts/run_pytest_phases.py",
    "tools/sync_packaging_files.py",
    "docs/openapi.yaml",
]


def _load_scripts(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return set((data.get("scripts") or {}).keys())


def _normalise(line: str) -> str:
    line = line.strip()
    if not line or line.startswith("#"):
        return ""
    if line.endswith("\\"):
        line = line[:-1].strip()
    return line


def _split(line: str) -> list[str]:
    try:
        return shlex.split(line.replace("\\", "/"), posix=False)
    except ValueError:
        return line.replace("\\", "/").split()


def main() -> int:
    errors: list[str] = []
    root_scripts = _load_scripts(ROOT / "package.json")
    frontend_scripts = _load_scripts(ROOT / "frontend" / "package.json")

    for rel in WORKFLOWS + REQUIRED_PATHS:
        if not (ROOT / rel).exists():
            errors.append(f"missing required path: {rel}")

    checked = 0
    for rel in DOCS:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"missing document: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for block in CODE_BLOCK_RE.findall(text):
            for raw_line in block.splitlines():
                line = _normalise(raw_line)
                if not line or line.startswith("$"):
                    continue
                parts = _split(line)
                if not parts:
                    continue
                command = parts[0]
                if command in {"IUSENTRA_BASE_URL=https://app.iusentra.it", "IUSENTRA_SMOKE_API_KEY=\"$IUSENTRA_SMOKE_API_KEY\""}:
                    continue
                if command == "python":
                    if len(parts) >= 2 and parts[1].endswith(".py"):
                        script = parts[1].strip('"')
                        if not (ROOT / script).exists():
                            errors.append(f"{rel}: missing python script in command: {script}")
                        checked += 1
                    elif len(parts) >= 3 and parts[1] == "-m":
                        checked += 1
                elif command == "node":
                    if len(parts) >= 2:
                        script = parts[1].strip('"')
                        if script.endswith(".mjs") and not (ROOT / script).exists():
                            errors.append(f"{rel}: missing node script in command: {script}")
                        checked += 1
                elif command == "npm":
                    if "--prefix" in parts and "run" in parts:
                        run_index = parts.index("run")
                        script_name = parts[run_index + 1] if run_index + 1 < len(parts) else ""
                        if "--prefix" in parts and "frontend" in parts:
                            if script_name not in frontend_scripts:
                                errors.append(f"{rel}: missing frontend npm script: {script_name}")
                        elif script_name not in root_scripts:
                            errors.append(f"{rel}: missing root npm script: {script_name}")
                        checked += 1
                elif command in {"docker", "git", "ssh", "curl", "curl.exe", "powershell", "bash", "pip-audit", "coverage"}:
                    checked += 1

    if errors:
        print("Document command validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Document command validation OK: {checked} documented commands/paths checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
