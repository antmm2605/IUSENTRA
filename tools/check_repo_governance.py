from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _line_count(relative_path: str) -> int:
    return len(_read_text(relative_path).splitlines())


def _check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _tracked_files() -> list[str]:
    git_dir = REPO_ROOT / ".git"
    if not git_dir.exists():
        return []
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    failures: list[str] = []

    web_app = _read_text("web/app.py")
    _check("@app.route" not in web_app, "web/app.py non deve contenere route inline.", failures)
    _check(
        _line_count("web/app.py") <= 250,
        f"web/app.py supera il budget: {_line_count('web/app.py')} righe.",
        failures,
    )
    _check(
        "from web.bootstrap.app_wiring import register_app_wiring" in web_app,
        "web/app.py deve delegare il wiring a web.bootstrap.app_wiring.",
        failures,
    )
    _check(
        "register_app_wiring(" in web_app,
        "web/app.py deve usare register_app_wiring().",
        failures,
    )
    _check(
        "from web.bootstrap." not in web_app.replace(
            "from web.bootstrap.app_wiring import register_app_wiring", ""
        ),
        "web/app.py non deve importare direttamente i moduli route/bootstrap verticali.",
        failures,
    )

    bootstrap_limits = {
        "deposito_routes.py": 1000,
        "scadenziario_routes.py": 700,
        "fascicoli_pdp_routes.py": 900,
    }
    for path in sorted((REPO_ROOT / "web/bootstrap").glob("*.py")):
        if path.name == "__init__.py":
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        limit = bootstrap_limits.get(path.name, 650)
        _check(
            line_count <= limit,
            f"Modulo bootstrap troppo grande: {path.name} ha {line_count} righe (limite {limit}).",
            failures,
        )

    focused_limits = {
        "web/blueprints/assistente.py": 40,
        "web/services/assistente_document_export.py": 40,
        "web/services/assistente_followup.py": 40,
        "web/services/assistente_social_intent.py": 40,
        "web/services/assistente_language_guidance.py": 40,
        "web/services/assistente_legal_reference_guard.py": 40,
        "web/services/assistente_prompt.py": 40,
        "web/services/assistente_today_summary.py": 40,
        "web/services/assistente_web_execution.py": 40,
    }
    for relative_path, limit in focused_limits.items():
        line_count = _line_count(relative_path)
        _check(
            line_count <= limit,
            f"{relative_path} ha {line_count} righe: deve restare una facciata governabile (limite {limit}).",
            failures,
        )

    runtime_dependencies = _read_text("lex/runtime_dependencies.py")
    _check(
        "def build_runtime_lex_dependencies() -> LexDependencies:" in runtime_dependencies,
        "lex/runtime_dependencies.py deve esporre build_runtime_lex_dependencies.",
        failures,
    )
    _check(
        "def require_authenticated_flask_user(fn):" in runtime_dependencies,
        "lex/runtime_dependencies.py deve esporre require_authenticated_flask_user.",
        failures,
    )
    _check(
        "from web.services.assistente_studio_context" not in runtime_dependencies,
        "lex/runtime_dependencies.py non deve dipendere direttamente da web.services.assistente_studio_context.",
        failures,
    )
    _check(
        "from web.services.ollama_runtime" not in runtime_dependencies,
        "lex/runtime_dependencies.py non deve dipendere direttamente da web.services.ollama_runtime.",
        failures,
    )

    lex_blueprint = _read_text("web/blueprints/assistente.py")
    _check(
        "build_runtime_lex_blueprint" in lex_blueprint,
        "web/blueprints/assistente.py deve delegare al blueprint runtime di lex.",
        failures,
    )

    for relative_path in (
        "lex/contracts.py",
        "lex/router.py",
        "lex/registry.py",
        "lex/context/studio_context.py",
        "lex/providers/health.py",
        "lex/retrieval/orchestrator.py",
        "lex/guards/orchestrator.py",
    ):
        _check((REPO_ROOT / relative_path).exists(), f"Struttura Lex incompleta: manca {relative_path}.", failures)

    ci_workflow = _read_text(".github/workflows/ci.yml")
    for snippet in (
        "name: Governance repo",
        "python tools/check_repo_governance.py",
        "name: Lint + syntax",
        "name: Smoke test Flask",
        "from web.app import create_app",
        "name: Pytest core",
        "name: Local Signer e PKCS#11 (${{ matrix.os }})",
    ):
        _check(snippet in ci_workflow, f"Workflow CI incompleto: manca '{snippet}'.", failures)

    readme = _read_text("README.md")
    _check("Governance repo" in readme, "README non documenta il job di governance repo.", failures)
    _check("docs/QUICKSTART.md" in readme, "README non collega il quickstart operativo.", failures)
    _check("docs/DEPLOY.md" in readme, "README non collega la guida deploy/release.", failures)
    _check("lex/registry.py" in readme, "README non documenta il registry del bounded context Lex.", failures)

    for relative_path in ("docs/QUICKSTART.md", "docs/DEPLOY.md"):
        _check((REPO_ROOT / relative_path).exists(), f"Documentazione mancante: {relative_path}.", failures)

    tracked_files = _tracked_files()
    forbidden_exact = {
        "pct.zip",
        "web/polisWeb - Copia.html",
    }
    forbidden_suffixes = (".pyc", ".pyo", ".rej", ".orig", ".bak")
    for tracked in tracked_files:
        normalized = tracked.replace("\\", "/")
        _check(
            "__pycache__/" not in normalized,
            f"Artefatto Python tracciato: {normalized}.",
            failures,
        )
        _check(
            normalized not in forbidden_exact,
            f"Zavorra di sviluppo tracciata: {normalized}.",
            failures,
        )
        _check(
            " - Copia." not in normalized,
            f"File copia tracciato: {normalized}.",
            failures,
        )
        _check(
            not normalized.endswith(forbidden_suffixes),
            f"Artefatto non governabile tracciato: {normalized}.",
            failures,
        )

    if failures:
        print("Governance check FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Governance check OK")
    print(f"web/app.py: {_line_count('web/app.py')} righe, 0 route inline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
