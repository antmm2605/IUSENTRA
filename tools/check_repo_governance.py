from __future__ import annotations

import sys
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _line_count(relative_path: str) -> int:
    return len(_read_text(relative_path).splitlines())


def _check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _inline_style_totals(root_relative_path: str) -> tuple[int, int, int]:
    root = REPO_ROOT / root_relative_path
    style_tag = re.compile(r"<style\b", re.IGNORECASE)
    style_attr = re.compile(r"\sstyle=", re.IGNORECASE)
    files = 0
    tags = 0
    attrs = 0
    for path in root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        file_tags = len(style_tag.findall(text))
        file_attrs = len(style_attr.findall(text))
        if file_tags or file_attrs:
            files += 1
            tags += file_tags
            attrs += file_attrs
    return files, tags, attrs


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
        "from lex.providers.local_ai_service import get_local_ai_service" in web_app,
        "web/app.py deve importare il servizio AI locale da lex.providers.local_ai_service.",
        failures,
    )
    _check(
        "from web.services.local_ai_runtime import get_local_ai_service" not in web_app,
        "web/app.py non deve dipendere direttamente da web.services.local_ai_runtime.",
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
        "web/services/local_ai_runtime.py": 40,
        "web/services/ollama_runtime.py": 40,
        "web/assistente.py": 40,
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

    local_ai_service = _read_text("lex/providers/local_ai_service.py")
    _check(
        "def get_local_ai_service() -> LocalAIService:" in local_ai_service,
        "lex/providers/local_ai_service.py deve possedere get_local_ai_service().",
        failures,
    )

    ollama_runtime = _read_text("lex/providers/ollama_runtime.py")
    _check(
        "def resolved_ollama_runtime(" in ollama_runtime,
        "lex/providers/ollama_runtime.py deve possedere la risoluzione runtime Ollama.",
        failures,
    )
    _check(
        "from .local_ai_service import get_local_ai_service" in ollama_runtime,
        "lex/providers/ollama_runtime.py deve dipendere dal servizio locale posseduto da Lex.",
        failures,
    )

    lex_blueprint = _read_text("web/blueprints/assistente.py")
    _check(
        "build_runtime_lex_blueprint" in lex_blueprint,
        "web/blueprints/assistente.py deve delegare al blueprint runtime di lex.",
        failures,
    )

    local_ai_facade = _read_text("web/services/local_ai_runtime.py")
    _check(
        "from lex.providers.local_ai_service import get_local_ai_service" in local_ai_facade,
        "web/services/local_ai_runtime.py deve essere solo una facciata verso lex.providers.local_ai_service.",
        failures,
    )

    ollama_facade = _read_text("web/services/ollama_runtime.py")
    _check(
        "from lex.providers.ollama_runtime import (" in ollama_facade,
        "web/services/ollama_runtime.py deve essere solo una facciata verso lex.providers.ollama_runtime.",
        failures,
    )

    legacy_assistente = _read_text("web/assistente.py")
    _check(
        "from web.blueprints.admin import admin_bp, superadmin_required" in legacy_assistente,
        "web/assistente.py deve restare solo un shim legacy verso web.blueprints.admin.",
        failures,
    )

    for relative_path in (
        "lex/contracts.py",
        "lex/router.py",
        "lex/registry.py",
        "lex/context/studio_context.py",
        "lex/providers/health.py",
        "lex/providers/local_ai_service.py",
        "lex/providers/ollama_runtime.py",
        "lex/retrieval/orchestrator.py",
        "lex/guards/orchestrator.py",
    ):
        _check((REPO_ROOT / relative_path).exists(), f"Struttura Lex incompleta: manca {relative_path}.", failures)

    app_scss = _read_text("web/static/scss/app.scss")
    for snippet in (
        "@use 'components/app-shell';",
        "@use 'components/feedback';",
        "@use 'components/compact-panels';",
        "@use 'pages/admin';",
        "@use 'pages/dashboard';",
        "@use 'pages/settings';",
        "@use 'pages/telematico-dashboard';",
    ):
        _check(snippet in app_scss, f"SCSS principale incompleto: manca '{snippet}'.", failures)

    for relative_path in (
        "web/static/scss/components/_app-shell.scss",
        "web/static/scss/pages/_admin.scss",
    ):
        _check((REPO_ROOT / relative_path).exists(), f"SCSS governabile mancante: {relative_path}.", failures)

    base_template = _read_text("web/templates/base.html")
    for snippet in (
        "topbar-counter-badge",
        "ocr-pill is-hidden",
        "notifiche-panel is-hidden",
        "notif-item__body",
        "ss-chip-identificativo",
    ):
        _check(snippet in base_template, f"Base template non allineato al refactor SCSS: manca '{snippet}'.", failures)
    _check("<style" not in base_template, "web/templates/base.html non deve contenere blocchi <style> inline.", failures)
    _check("style=" not in base_template, "web/templates/base.html non deve contenere attributi style inline.", failures)

    admin_base = _read_text("web/templates/admin/base.html")
    for css_link in (
        "/static/css/app.css?v={{ app_version }}",
        "/static/css/design-system.css?v={{ app_version }}",
        "/static/css/mobile.css?v={{ app_version }}",
        "/static/css/theme.css?v={{ app_version }}",
    ):
        _check(css_link in admin_base, f"Admin base non carica il bundle CSS richiesto: {css_link}.", failures)
    _check("<style" not in admin_base, "web/templates/admin/base.html non deve contenere blocchi <style> inline.", failures)
    _check("style=" not in admin_base, "web/templates/admin/base.html non deve contenere attributi style inline.", failures)

    for relative_path in (
        "web/templates/admin/dashboard.html",
        "web/templates/admin/studio_nuovo.html",
    ):
        content = _read_text(relative_path)
        _check("<style" not in content, f"{relative_path} non deve contenere blocchi <style> inline.", failures)
        _check("style=" not in content, f"{relative_path} non deve contenere attributi style inline.", failures)

    inline_files, inline_tags, inline_attrs = _inline_style_totals("web/templates")
    _check(
        inline_files <= 165,
        f"Template HTML fuori budget governance: {inline_files} file con inline style (limite 165).",
        failures,
    )
    _check(
        inline_tags <= 53,
        f"Template HTML fuori budget governance: {inline_tags} tag <style> (limite 53).",
        failures,
    )
    _check(
        inline_attrs <= 1464,
        f"Template HTML fuori budget governance: {inline_attrs} attributi style= (limite 1464).",
        failures,
    )

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
    _check(
        "github.com/antmm2605/hacs/actions/workflows/ci.yml" in readme,
        "README non collega la vista live del workflow CI.",
        failures,
    )

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
