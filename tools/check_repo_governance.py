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


def main() -> int:
    failures: list[str] = []

    web_app = _read_text("web/app.py")
    _check("@app.route" not in web_app, "web/app.py non deve contenere route inline.", failures)
    _check(
        _line_count("web/app.py") < 7000,
        f"web/app.py supera il budget: {_line_count('web/app.py')} righe.",
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
        "web/services/assistente_followup.py": 40,
        "web/services/assistente_social_intent.py": 40,
        "web/services/assistente_language_guidance.py": 40,
        "web/services/assistente_prompt.py": 40,
        "web/services/assistente_today_summary.py": 40,
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

    ci_workflow = _read_text(".github/workflows/ci.yml")
    for snippet in (
        "name: Governance repo",
        "python tools/check_repo_governance.py",
        "name: Lint + syntax",
        "name: Smoke test Flask",
        "name: Pytest core",
        "name: Local Signer e PKCS#11 (${{ matrix.os }})",
    ):
        _check(snippet in ci_workflow, f"Workflow CI incompleto: manca '{snippet}'.", failures)

    readme = _read_text("README.md")
    _check("Governance repo" in readme, "README non documenta il job di governance repo.", failures)

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
