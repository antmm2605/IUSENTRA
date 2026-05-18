from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


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
    assert "actions/upload-artifact@v4" in workflow


def test_security_supply_chain_blocks_critical_dependency_regressions() -> None:
    workflow = _read(".github/workflows/security-supply-chain.yml")

    assert "pip-audit -r requirements.txt --format json --output pip-audit.json" in workflow
    assert "pnpm --filter @iusentra/studio audit --audit-level=critical --prod --json" in workflow
    assert "pip-audit-report" in workflow
    assert "frontend-pnpm-audit-report" in workflow


def test_phase11_test_plan_mentions_ci_workflows() -> None:
    test_plan = _read("docs/test-plan-app-v2.md")

    assert "## CI/CD fase 11" in test_plan
    assert "`.github/workflows/ci.yml`" in test_plan
    assert "`.github/workflows/smoke-staging.yml`" in test_plan
    assert "GitHub Actions" in test_plan
