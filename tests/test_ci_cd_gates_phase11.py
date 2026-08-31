from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _load_required_gates_module() -> ModuleType:
    path = REPO_ROOT / "tools" / "check_github_required_gates.py"
    spec = importlib.util.spec_from_file_location("iusentra_required_gates", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase11_ci_gates_documented() -> None:
    doc = _read("docs/ci-cd-gates.md")

    for needle in (
        ".github/workflows/ci.yml",
        ".github/workflows/security-supply-chain.yml",
        ".github/workflows/smoke-staging.yml",
        "Required Secrets and Environment Variables",
        "Recommended Required Checks",
        "provider verification",
        "tenant isolation",
        "routes.appV2",
        "Bloccante",
    ):
        assert needle in doc


def test_main_ci_runs_phase11_blocking_gates() -> None:
    workflow = _read(".github/workflows/ci.yml")

    for needle in (
        "python scripts/react-migration/generate_app_v2_test_docs.py --check",
        "python scripts/smoke_app_v2_all.py --subset inventory",
        "python scripts/smoke_app_v2_all.py --subset contracts",
        "tests/test_ci_cd_gates_phase11.py",
        "tests/test_backend_security_phase5.py",
        "tests/test_tenant_isolation_runtime.py",
        "tests/test_app_v2_feature_flags.py",
        "tests/test_app_v2_routing.py",
        "tests/test_openapi_contracts_phase6.py",
        "pnpm/action-setup@v4",
        "pnpm --filter @iusentra/studio typecheck",
        "pnpm --filter @iusentra/studio build",
    ):
        assert needle in workflow


def test_smoke_staging_workflow_is_manual_and_secret_safe() -> None:
    workflow = _read(".github/workflows/smoke-staging.yml")

    assert "workflow_dispatch" in workflow
    assert "pull_request_target" not in workflow
    assert "environment:" in workflow
    assert "name: staging" in workflow
    assert "IUSENTRA_ADMIN_PASSWORD: ${{ secrets.IUSENTRA_ADMIN_PASSWORD }}" in workflow
    assert "python scripts/smoke_app_v2_all.py --base-url" in workflow
    # version-agnostic: il gate verifica che l'upload artifact esista,
    # non blocca i bump di manutenzione delle action (es. v4 -> v5 per Node 24)
    assert "actions/upload-artifact@" in workflow


def test_security_supply_chain_blocks_critical_dependency_regressions() -> None:
    workflow = _read(".github/workflows/security-supply-chain.yml")

    assert "push:" in workflow
    assert "pip-audit -r requirements.txt --format json --output pip-audit.json" in workflow
    assert "pnpm/action-setup@v4" in workflow
    assert "pnpm --filter @iusentra/studio audit --audit-level=critical --prod --json" in workflow
    assert "pip-audit-report" in workflow
    assert "frontend-pnpm-audit-report" in workflow


def test_ci_required_gates_blocks_missing_skipped_and_external_drift() -> None:
    config = json.loads(_read(".github/required-checks.json"))
    workflow = _read(".github/workflows/ci-required-gates.yml")
    deploy_workflow = _read(".github/workflows/deploy-hetzner.yml")
    frontend_workflow = _read(".github/workflows/frontend-ci.yml")
    module = _load_required_gates_module()

    assert config["branch_protection"]["enforce_admins"] is False
    contexts = module.branch_protection_contexts(config)
    assert "CI reale eseguita sul commit corrente" in contexts
    assert "Lint + syntax" in contexts
    # CodeQL e' richiesto solo su pull_request (l'ombrello Code Scanning non e'
    # prodotto sui push): non entra nei branch-protection contexts, che sono push-only.
    assert "CodeQL" not in contexts
    assert "Analyze (python)" in contexts
    assert "Review dipendenze in ingresso" not in contexts
    assert "Frontend React contratti" in contexts
    assert "Frontend React typecheck" in contexts
    assert "Frontend React build" in contexts
    assert "Security Supply Chain" not in contexts
    assert "Deploy su Hetzner CPX42" not in contexts
    assert "Vercel" not in contexts
    assert "Vercel Preview Comments" not in contexts
    assert "sync-peer-branch" not in contexts
    assert len(contexts) >= 80

    pull_request_checks = {check.name for check in module.expand_required_checks(config, event="pull_request")}
    push_checks = {check.name for check in module.expand_required_checks(config, event="push")}
    assert "Review dipendenze in ingresso" in pull_request_checks
    assert "Review dipendenze in ingresso" not in push_checks

    codeql = [check for check in module.expand_required_checks(config) if check.name == "CodeQL"][0]
    assert codeql.accepted_conclusions == ("success", "neutral")

    # CodeQL e' in scope solo su pull_request, dove neutral->ok. Su push NON e'
    # richiesto: il context-umbrella "CodeQL" non viene prodotto sui push (solo il
    # job "Analyze (python)"), quindi richiederlo lo renderebbe eternamente "missing".
    assert "CodeQL" not in push_checks
    assert "CodeQL" in pull_request_checks
    rows = module.evaluate_required_checks(
        config,
        [
            {"name": "Lint + syntax", "status": "completed", "conclusion": "success"},
            {"name": "Governance repo", "status": "completed", "conclusion": "skipped"},
            {"name": "CodeQL", "status": "completed", "conclusion": "neutral"},
        ],
        "pull_request",
    )
    by_name = {row.name: row for row in rows}
    assert by_name["Lint + syntax"].state == "ok"
    assert by_name["Governance repo"].state == "failed"
    assert by_name["CodeQL"].state == "ok"
    assert by_name["Smoke test Flask"].state == "missing"

    # Su push, CodeQL NON e' richiesto: la scansione e' coperta dal job required
    # "Analyze (python)" (gia' verde), mentre il context-umbrella "CodeQL" non
    # esiste sui push. Nessun check-run "CodeQL" nel valutato -> non deve comparire
    # come "missing"/bloccante fra i gate di push.
    push_rows = module.evaluate_required_checks(
        config,
        [
            {"name": "Analyze (python)", "status": "completed", "conclusion": "success"},
        ],
        "push",
    )
    push_by_name = {row.name: row for row in push_rows}
    assert "CodeQL" not in push_by_name
    assert push_by_name["Analyze (python)"].state == "ok"

    duplicated_rows = module.evaluate_required_checks(
        {"required_checks": [{"name": "Coverage moduli critici parte 1/12", "events": ["push"]}]},
        [
            {
                "name": "Coverage moduli critici parte 1/12",
                "status": "completed",
                "conclusion": "success",
                "completed_at": "2026-06-14T14:59:43Z",
            },
            {
                "name": "Coverage moduli critici parte 1/12",
                "status": "completed",
                "conclusion": "cancelled",
                "completed_at": "2026-06-14T15:00:48Z",
            },
        ],
        "push",
    )
    assert duplicated_rows[0].state == "ok"

    statuses = module.evaluate_statuses(
        config,
        [
            {"context": "Vercel", "state": "failure", "target_url": "https://vercel.example"},
            {"context": "Altro provider", "state": "failure", "target_url": "https://example.test"},
        ],
    )
    status_by_name = {row.name: row for row in statuses}
    assert status_by_name["Vercel"].state == "ignored"
    assert status_by_name["Altro provider"].state == "failed"

    assert "python tools/check_github_required_gates.py" in workflow
    assert "--wait" in workflow
    assert "current-sha-required-gates.md" in workflow
    assert "Attendi CI richiesta dello SHA corrente" in deploy_workflow
    assert "deploy-required-gates.md" in deploy_workflow
    assert "Setup chiave SSH e known_hosts" in deploy_workflow
    assert deploy_workflow.index("Attendi CI richiesta dello SHA corrente") < deploy_workflow.index("Setup chiave SSH e known_hosts")
    assert "paths:" not in frontend_workflow


def test_phase11_test_plan_mentions_ci_workflows() -> None:
    test_plan = _read("docs/test-plan-app-v2.md")

    assert "## CI/CD fase 11" in test_plan
    assert "`.github/workflows/ci.yml`" in test_plan
    assert "`.github/workflows/smoke-staging.yml`" in test_plan
    assert "GitHub Actions" in test_plan


def test_every_push_required_check_has_a_producing_job() -> None:
    """Salvaguardia anti check-fantasma: ogni check richiesto su push DEVE essere
    prodotto da un job dei workflow. Un check richiesto ma mai prodotto resta
    eternamente 'missing', blocca il wait-gate e quindi il deploy.
    Eccezioni note: provider esterni (Vercel) non sono job di Actions.
    """
    import re

    import yaml

    module = _load_required_gates_module()
    config = json.loads(_read(".github/required-checks.json"))
    push_required = {check.name for check in module.expand_required_checks(config, event="push")}

    external_providers = {"Vercel", "Vercel Preview Comments"}
    # NB: nessuna esenzione per check "github-generated" come CodeQL. L'ombrello
    # Code Scanning non e' prodotto sui push, quindi CodeQL e' richiesto solo su
    # pull_request: se qualcuno lo rimettesse fra i required su push (recidiva
    # della regressione "check fantasma"), questo test lo cattura come orfano.
    # Il job-orchestratore che ATTENDE i gate non puo' attendere se stesso.
    waiter_jobs = {"CI reale eseguita sul commit corrente"}

    produced_prefixes: set[str] = set()
    for workflow_path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job_id, job in (workflow.get("jobs") or {}).items():
            raw_name = str(job.get("name", job_id))
            # i nomi matrice hanno parti ${{ matrix.* }}: confronto sul prefisso fisso
            prefix = re.split(r"\$\{\{", raw_name)[0].strip()
            if prefix:
                produced_prefixes.add(prefix)

    orphans = sorted(
        name
        for name in push_required
        if name not in external_providers
        and name not in waiter_jobs
        and not any(name == prefix or name.startswith(prefix) for prefix in produced_prefixes)
    )
    assert not orphans, (
        "Check richiesti su push senza job che li produce (resterebbero 'missing' e "
        f"bloccherebbero il deploy): {orphans}"
    )


def test_errore_di_trasporto_http2_e_considerato_transitorio() -> None:
    """Run 30841471702: il gate moriva su "stream error ... CANCEL" a check quasi verdi."""

    module = _load_required_gates_module()

    assert module._is_transient_gh_error(
        "stream error: stream ID 1; CANCEL; received from peer"
    )
    assert module._is_transient_gh_error("unexpected EOF")
    assert module._is_transient_gh_error("connection closed by peer")
    # Un errore reale non deve diventare transitorio.
    assert not module._is_transient_gh_error("Not Found (HTTP 404)")
    assert not module._is_transient_gh_error("Bad credentials (HTTP 401)")


def test_il_gate_continua_ad_attendere_dopo_una_lettura_fallita(monkeypatch) -> None:
    """Un blip dell'API a meta' attesa non deve buttare via il giro di 90 minuti."""

    import argparse

    module = _load_required_gates_module()
    tentativi = {"n": 0}

    def _fetch_check_runs(repo: str, sha: str):
        tentativi["n"] += 1
        if tentativi["n"] == 1:
            raise RuntimeError("gh api failed: stream error: stream ID 1; CANCEL")
        return [{"name": "Lint + syntax", "status": "completed", "conclusion": "success"}]

    monkeypatch.setattr(module, "fetch_check_runs", _fetch_check_runs)
    monkeypatch.setattr(module, "fetch_statuses", lambda repo, sha: [])
    monkeypatch.setattr(module, "evaluate_required_checks", lambda config, runs, event: [])
    monkeypatch.setattr(module, "evaluate_statuses", lambda config, statuses: [])
    monkeypatch.setattr(module, "_load_json", lambda path: {})
    monkeypatch.setattr(module, "resolve_repo", lambda value: "owner/repo")
    monkeypatch.setattr(module, "resolve_sha", lambda value: "abc123")
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "render_markdown", lambda *a, **k: "")
    monkeypatch.setattr(module, "write_reports", lambda *a, **k: None)

    args = argparse.Namespace(
        config="config.json",
        repo="owner/repo",
        sha="abc123",
        event="push",
        wait=True,
        timeout_seconds=60,
        poll_seconds=0,
        report_md="",
        report_json="",
        check_branch_protection=False,
    )

    esito = module.run_gate(args)

    assert tentativi["n"] >= 2, "il gate deve riprovare la lettura invece di abortire"
    assert esito == 0


def test_il_gate_attende_i_job_pendenti_anche_dopo_un_fallimento(monkeypatch) -> None:
    """Un errore già concluso non deve far classificare gli altri job come missing."""

    import argparse

    module = _load_required_gates_module()
    letture = {"n": 0}

    def _fetch_check_runs(repo: str, sha: str):
        letture["n"] += 1
        return []

    def _evaluate_required_checks(config, runs, event):
        if letture["n"] == 1:
            return [
                module.GateRow("Lint + syntax", "completed", "failure", "failed"),
                module.GateRow("Pytest core", "in_progress", "", "pending"),
            ]
        return [module.GateRow("Lint + syntax", "completed", "failure", "failed")]

    monkeypatch.setattr(module, "fetch_check_runs", _fetch_check_runs)
    monkeypatch.setattr(module, "fetch_statuses", lambda repo, sha: [])
    monkeypatch.setattr(module, "evaluate_required_checks", _evaluate_required_checks)
    monkeypatch.setattr(module, "evaluate_statuses", lambda config, statuses: [])
    monkeypatch.setattr(module, "_load_json", lambda path: {})
    monkeypatch.setattr(module, "resolve_repo", lambda value: "owner/repo")
    monkeypatch.setattr(module, "resolve_sha", lambda value: "abc123")
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "render_markdown", lambda *a, **k: "")
    monkeypatch.setattr(module, "write_reports", lambda *a, **k: None)

    args = argparse.Namespace(
        config="config.json",
        repo="owner/repo",
        sha="abc123",
        event="push",
        wait=True,
        timeout_seconds=60,
        poll_seconds=0,
        report_md="",
        report_json="",
        check_branch_protection=False,
    )

    esito = module.run_gate(args)

    assert letture["n"] == 2
    assert esito == 1
