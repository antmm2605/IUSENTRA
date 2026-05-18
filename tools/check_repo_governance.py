from __future__ import annotations

import sys
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_PATTERN = re.compile(
    r"\u00c3.|\u00c2.|\u00e2[\u20ac\u201a\u0192\u201e\u2026\u2020\u2021\u02c6\u2030\u0160\u2039\u0152\u017d\u2018\u2019\u201c\u201d\u2022\u2013\u2014\u02dc\u2122\u0161\u203a\u0153\u017e\u0178]|\u00e2\u0153.|\u00e2\u0161."
)
_GOVERNED_TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".css",
    ".dtd",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".scss",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".wsdl",
    ".xml",
    ".xsd",
    ".yaml",
    ".yml",
}
_GOVERNED_TEXT_NAMES = {
    ".editorconfig",
    ".flake8",
    ".gitattributes",
    ".gitignore",
    "Dockerfile",
    "Makefile",
    "railway.toml",
}
_TEXT_PREFIX_EXCLUSIONS = (
    "docs/specs/ministero/",
    "tools/dist/",
)
_TEXT_PART_EXCLUSIONS = {
    "__pycache__",
    ".pytest_cache",
}


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
    tracked: list[str] = []
    for line in result.stdout.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if not (REPO_ROOT / normalized).exists():
            continue
        tracked.append(normalized)
    return tracked


def _iter_governed_text_files():
    for relative_path in _tracked_files():
        normalized = relative_path.replace("\\", "/")
        if any(normalized.startswith(prefix) for prefix in _TEXT_PREFIX_EXCLUSIONS):
            continue
        if any(part in _TEXT_PART_EXCLUSIONS for part in normalized.split("/")):
            continue
        path = REPO_ROOT / relative_path
        if path.suffix.lower() not in _GOVERNED_TEXT_SUFFIXES and path.name not in _GOVERNED_TEXT_NAMES:
            continue
        yield normalized, path


def _find_mojibake_or_non_utf8_files() -> list[str]:
    offenders: list[str] = []
    for relative_path, path in _iter_governed_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            offenders.append(f"{relative_path} (non UTF-8)")
            continue
        if MOJIBAKE_PATTERN.search(text):
            offenders.append(f"{relative_path} (mojibake)")
    return offenders


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
        "from web.bootstrap.flask_app_factory import create_flask_app" in web_app,
        "web/app.py deve delegare la factory base a web.bootstrap.flask_app_factory.",
        failures,
    )
    _check(
        "from web.bootstrap.runtime_bundle import build_application_runtime_bundle" in web_app,
        "web/app.py deve delegare l'assemblaggio runtime a web.bootstrap.runtime_bundle.",
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
        "from web.services." not in web_app,
        "web/app.py non deve importare direttamente i runtime applicativi da web.services.",
        failures,
    )
    _check(
        "from pct.scheduler import start_scheduler" not in web_app,
        "web/app.py non deve avviare direttamente lo scheduler.",
        failures,
    )
    _check(
        "start_scheduler(" not in web_app,
        "web/app.py non deve avviare lo scheduler dentro la factory web.",
        failures,
    )
    for snippet in (
        "build_core_runtime(",
        "build_fascicoli_runtime(",
        "build_telematico_runtime(",
        "build_pdp_penale_runtime(",
        "build_ocr_runtime(",
        "apply_security_defaults(",
    ):
        _check(
            snippet not in web_app,
            f"web/app.py non deve contenere bootstrap runtime diretto: trovato '{snippet}'.",
            failures,
        )

    scheduler_worker = _read_text("pct/scheduler_worker.py")
    scheduler_module = _read_text("pct/scheduler.py")
    _check(
        "def create_scheduler_app(" in scheduler_worker,
        "pct/scheduler_worker.py deve esporre create_scheduler_app().",
        failures,
    )
    _check(
        "def start_scheduler_worker(" in scheduler_worker,
        "pct/scheduler_worker.py deve esporre start_scheduler_worker().",
        failures,
    )
    _check(
        'cfg["SCHEDULER_ONLY"] = True' in scheduler_worker,
        "pct/scheduler_worker.py deve forzare il profilo SCHEDULER_ONLY.",
        failures,
    )
    _check(
        "_scheduler_bootstrap_allowed" in scheduler_module,
        "pct/scheduler.py deve avere una guardia esplicita per l'avvio solo sul worker dedicato.",
        failures,
    )
    _check(
        "PCT_SCHEDULER_WORKER" in scheduler_module,
        "pct/scheduler.py deve controllare il profilo worker prima di avviare APScheduler.",
        failures,
    )

    bootstrap_limits = {
        "deposito_routes.py": 1000,
        "scadenziario_routes.py": 700,
        "fascicoli_pdp_routes.py": 900,
        "runtime_bundle.py": 220,
        "core_surface_wiring.py": 250,
        "fascicoli_surface_wiring.py": 200,
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

    _check(
        _line_count("web/bootstrap/flask_app_factory.py") <= 80,
        "web/bootstrap/flask_app_factory.py deve restare una factory base molto compatta (limite 80 righe).",
        failures,
    )
    _check(
        _line_count("web/bootstrap/app_wiring.py") <= 80,
        "web/bootstrap/app_wiring.py deve restare un delegatore molto compatto (limite 80 righe).",
        failures,
    )

    app_wiring = _read_text("web/bootstrap/app_wiring.py")
    _check(
        "from web.bootstrap.core_surface_wiring import register_core_surfaces" in app_wiring,
        "web/bootstrap/app_wiring.py deve delegare a register_core_surfaces().",
        failures,
    )
    _check(
        "from web.bootstrap.fascicoli_surface_wiring import register_fascicoli_surfaces" in app_wiring,
        "web/bootstrap/app_wiring.py deve delegare a register_fascicoli_surfaces().",
        failures,
    )
    _check(
        "from web.bootstrap.telematico_surface_wiring import register_telematico_surfaces" in app_wiring,
        "web/bootstrap/app_wiring.py deve delegare a register_telematico_surfaces().",
        failures,
    )
    for snippet in (
        "register_core_surfaces(",
        "register_fascicoli_surfaces(",
        "register_telematico_surfaces(",
        "register_blueprints(app)",
    ):
        _check(
            snippet in app_wiring,
            f"web/bootstrap/app_wiring.py incompleto: manca '{snippet}'.",
            failures,
        )

    blueprint_registry = _read_text("web/bootstrap/blueprint_registry.py")
    register_blueprints = _read_text("web/bootstrap/register_blueprints.py")
    _check(
        "class BlueprintRegistration" in blueprint_registry,
        "web/bootstrap/blueprint_registry.py deve esporre BlueprintRegistration.",
        failures,
    )
    _check(
        "BLUEPRINT_REGISTRY" in blueprint_registry,
        "web/bootstrap/blueprint_registry.py deve esporre BLUEPRINT_REGISTRY.",
        failures,
    )
    _check(
        "from web.bootstrap.blueprint_registry import BLUEPRINT_REGISTRY" in register_blueprints,
        "web/bootstrap/register_blueprints.py deve usare il registro dichiarativo dei blueprint.",
        failures,
    )
    _check(
        "entry.load_blueprint()" in register_blueprints,
        "web/bootstrap/register_blueprints.py deve registrare i blueprint iterando il registry.",
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
        "lex/orchestrator_http.py",
        "lex/orchestrator_workflow.py",
    ):
        _check((REPO_ROOT / relative_path).exists(), f"Struttura Lex incompleta: manca {relative_path}.", failures)

    ocr_worker = _read_text("pct/ocr_worker.py")
    _check(
        "def serve_ocr_worker(" in ocr_worker,
        "pct/ocr_worker.py deve esporre serve_ocr_worker().",
        failures,
    )
    _check(
        "OCRJobStore" in ocr_worker,
        "pct/ocr_worker.py deve usare la coda persistente OCRJobStore.",
        failures,
    )

    observability_runtime = _read_text("web/services/observability_runtime.py")
    _check(
        'app.extensions["runtime_metrics"] = registry' in observability_runtime,
        "web/services/observability_runtime.py deve registrare runtime_metrics nelle extensions Flask.",
        failures,
    )
    _check(
        "def build_observability_payload(" in observability_runtime,
        "web/services/observability_runtime.py deve esporre build_observability_payload().",
        failures,
    )

    health_routes = _read_text("web/bootstrap/health_routes.py")
    _check(
        '/api/metriche/runtime' in health_routes,
        "web/bootstrap/health_routes.py deve esporre /api/metriche/runtime.",
        failures,
    )

    admin_blueprint = _read_text("web/blueprints/admin.py")
    _check(
        '@admin_bp.route("/osservabilita")' in admin_blueprint,
        "web/blueprints/admin.py deve esporre la pagina admin /osservabilita.",
        failures,
    )

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

    compose = _read_text("docker-compose.yml")
    for snippet in (
        "scheduler-worker:",
        'command: ["python", "-m", "pct.scheduler_worker"]',
        "ocr-worker:",
        'command: ["python", "-m", "pct.ocr_worker"]',
        "PCT_OCR_QUEUE_DB: /data/search/ocr_jobs.db",
        'PCT_SQLITE_MODE: "1"',
        "host.docker.internal:host-gateway",
    ):
        _check(snippet in compose, f"Docker Compose non allineato: manca '{snippet}'.", failures)

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
        'assert "PCT_SCHEDULER" not in app.config',
        "name: Smoke scheduler worker",
        "from pct.scheduler_worker import start_scheduler_worker",
        "name: Pytest core",
        "name: Gate anti-regressione CI 100%",
        "tests/test_storage_strategy.py",
        "tests/test_observability_runtime.py",
        "tests/test_ocr_worker.py",
        "name: Local Signer e PKCS#11 (${{ matrix.os }})",
    ):
        _check(snippet in ci_workflow, f"Workflow CI incompleto: manca '{snippet}'.", failures)
    _check("\n  push:\n" in ci_workflow, "Workflow CI deve coprire i push in modo generico.", failures)
    _check(
        '      - "Codex/legal-electronic-filing-kIxcV"' not in ci_workflow,
        "Workflow CI non deve dipendere dal branch Codex specifico.",
        failures,
    )
    _check(
        '      - "claude/legal-electronic-filing-kIxcV"' not in ci_workflow,
        "Workflow CI non deve dipendere dal branch Claude specifico.",
        failures,
    )

    sync_workflow = _read_text(".github/workflows/sync-claude-to-codex.yml")
    for snippet in (
        "name: Sync Twin Branches",
        '      - "Codex/legal-electronic-filing-kIxcV"',
        '      - "claude/legal-electronic-filing-kIxcV"',
        'target="claude/legal-electronic-filing-kIxcV"',
        'target="Codex/legal-electronic-filing-kIxcV"',
        'git push origin "HEAD:refs/heads/${{ steps.branches.outputs.target }}" --force',
    ):
        _check(
            snippet in sync_workflow,
            f"Workflow sync branch gemelli incompleto: manca '{snippet}'.",
            failures,
        )

    repo_hygiene = _read_text("scripts/repo_hygiene.ps1")
    autosync_script = _read_text("scripts/git_branch_autosync.ps1")
    hook_runner = _read_text(".githooks/_run_powershell_hook.sh")
    post_commit = _read_text(".githooks/post-commit")
    post_checkout = _read_text(".githooks/post-checkout")
    post_merge = _read_text(".githooks/post-merge")
    post_rewrite = _read_text(".githooks/post-rewrite")

    for snippet in (
        "core.hooksPath .githooks",
        "safe.directory",
    ):
        _check(snippet in repo_hygiene, f"Repo hygiene incompleto: manca '{snippet}'.", failures)

    _check(
        "branch -f $branch $currentHead" in autosync_script,
        "Autosync locale branch non riallinea il branch gemello su HEAD.",
        failures,
    )
    _check(
        "git_branch_autosync.ps1" in hook_runner,
        "Runner hook non richiama lo script di autosync branch.",
        failures,
    )
    for content, hook_name in (
        (post_commit, "post-commit"),
        (post_checkout, "post-checkout"),
        (post_merge, "post-merge"),
        (post_rewrite, "post-rewrite"),
    ):
        _check(
            f'sh "$script_dir/_run_powershell_hook.sh" {hook_name} "$@"' in content,
            f"Hook {hook_name} non instrada l'autosync locale.",
            failures,
        )

    performance_workflow = _read_text(".github/workflows/performance-nightly.yml")
    for snippet in (
        "name: Performance Nightly",
        "tools/performance_smoke.py --strict",
        "performance-smoke.json",
    ):
        _check(
            snippet in performance_workflow,
            f"Workflow performance mancante o incompleto: '{snippet}'.",
            failures,
        )

    codeql_workflow = _read_text(".github/workflows/codeql.yml")
    dependency_review = _read_text(".github/workflows/dependency-review.yml")
    security_supply_chain = _read_text(".github/workflows/security-supply-chain.yml")
    for snippet in (
        "name: CodeQL",
        "github/codeql-action/analyze",
    ):
        _check(snippet in codeql_workflow, f"Workflow CodeQL incompleto: '{snippet}'.", failures)
    for snippet in (
        "name: Dependency Review",
        "dependency-review-action",
    ):
        _check(snippet in dependency_review, f"Workflow dependency review incompleto: '{snippet}'.", failures)
    for snippet in (
        "name: Security Supply Chain",
        "pip-audit",
        "sbom",
    ):
        _check(snippet in security_supply_chain, f"Workflow security supply chain incompleto: '{snippet}'.", failures)

    readme = _read_text("README.md")
    _check("Governance repo" in readme, "README non documenta il job di governance repo.", failures)
    _check("docs/QUICKSTART.md" in readme, "README non collega il quickstart operativo.", failures)
    _check("docs/DEPLOY.md" in readme, "README non collega la guida deploy/release.", failures)
    _check("docs/STORAGE_MATRIX.md" in readme, "README non collega la matrice storage.", failures)
    _check("docs/RELEASE_PROCESS.md" in readme, "README non collega la disciplina di release.", failures)
    _check("lex/registry.py" in readme, "README non documenta il registry del bounded context Lex.", failures)
    _check("scheduler-worker" in readme, "README non documenta il worker dedicato dello scheduler.", failures)
    _check("ocr-worker" in readme, "README non documenta il worker dedicato OCR.", failures)
    _check("/admin/osservabilita" in readme, "README non documenta la pagina di osservabilita'.", failures)
    _check("CodeQL" in readme, "README non documenta i workflow DevSecOps.", failures)
    _check(".github/workflows/sync-claude-to-codex.yml" in readme, "README non documenta il mirror dei branch gemelli.", failures)
    _check(".githooks/" in readme, "README non documenta i hook locali versionati.", failures)
    _check(
        "github.com/antmm2605/IUSENTRA/actions/workflows/ci.yml" in readme,
        "README non collega la vista live del workflow CI.",
        failures,
    )
    mojibake_offenders = _find_mojibake_or_non_utf8_files()
    _check(
        not mojibake_offenders,
        "Rilevati file testuali non UTF-8 o con possibile mojibake: "
        + ", ".join(mojibake_offenders[:8])
        + (" ..." if len(mojibake_offenders) > 8 else ""),
        failures,
    )

    for relative_path in (
        "docs/QUICKSTART.md",
        "docs/DEPLOY.md",
        "docs/STORAGE_MATRIX.md",
        "docs/RELEASE_PROCESS.md",
        "CHANGELOG.md",
        ".editorconfig",
    ):
        _check((REPO_ROOT / relative_path).exists(), f"Documentazione mancante: {relative_path}.", failures)

    tracked_files = _tracked_files()
    forbidden_exact = {
        "pct.zip",
        "web/polisWeb - Copia.html",
    }
    forbidden_root_directories = {
        "A1_WSDL_CATALOG_v1.52",
        "certificato autenticazione proxy",
        "DTD_20180328",
        "parte",
        "schema",
        "XSD PLO118 FASE2 per SW House",
        "XSD_REGINDE_20251010",
    }
    forbidden_root_files = {
        "Documentazione_servizi_web_v1.63.pdf",
        "Documentazione_servizi_web_v1.69.pdf",
        "PagamentiTelematiciGiustizia-6.0.1.xsd",
        "PagamentiTelematiciGiustizia.xsd",
        "Processo_Telematico_di_legittimit__Schemi_XSD_v.21.pdf",
        "Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf",
        "vademecum-deposito-atti-penali-sul-portale-telematico.pdf",
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
        _check(
            not (normalized.startswith("test_") and normalized.endswith(".py")),
            f"Test top-level da spostare sotto tests/: {normalized}.",
            failures,
        )
        _check(
            not normalized.startswith("tmp_local_signer_"),
            f"Log temporaneo Local Signer tracciato in root: {normalized}.",
            failures,
        )
        _check(
            normalized not in forbidden_root_directories,
            f"Asset ministeriale non deve stare in root: {normalized}.",
            failures,
        )
        _check(
            normalized not in forbidden_root_files,
            f"Specifica ministeriale non deve stare in root: {normalized}.",
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
