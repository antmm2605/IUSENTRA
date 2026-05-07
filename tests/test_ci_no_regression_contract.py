from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_ci_keeps_core_and_coverage_gates() -> None:
    workflow = _read(".github/workflows/ci.yml")
    required = (
        "name: Lint + syntax",
        "name: Governance repo",
        "name: Pytest core",
        "name: Coverage moduli critici",
        "tests/test_lex_docling_parser.py",
        "tests/test_storage_strategy.py",
        "--cov-config=config/coverage-critical.ini",
        "name: Gate anti-regressione CI 100%",
    )
    for snippet in required:
        assert snippet in workflow

    thresholds = [int(value) for value in re.findall(r"--cov-fail-under=(\d+)", workflow)]
    assert thresholds
    assert max(thresholds) >= 100
    assert any(value >= 71 for value in thresholds)


def test_pytest_core_timeout_covers_full_suite_without_removing_tests() -> None:
    workflow = _read(".github/workflows/ci.yml")
    section = workflow.split("tests-core:", 1)[1].split("coverage-critical:", 1)[0]
    timeout = re.search(r"timeout-minutes:\s*(\d+)", section)
    assert timeout
    assert int(timeout.group(1)) >= 45

    required_core_tests = (
        "lex/tests",
        "tests/test_auth.py",
        "tests/test_scheduler.py",
        "tests/test_scheduler_worker.py",
        "tests/test_storage_strategy.py",
        "tests/test_observability_runtime.py",
        "tests/test_ocr_worker.py",
        "tests/test_assistente_followup.py",
        "tests/test_assistente_language_guidance.py",
        "tests/test_assistente_social.py",
        "tests/test_assistente_social_intent.py",
        "tests/test_assistente_legal_reference_guard.py",
        "tests/test_web_bootstrap.py",
        "tests/test_web_security.py",
        "tests/test_database.py",
        "tests/test_local_ai.py",
        "tests/test_pst_catalog.py",
        "tests/test_giurisprudenza_repository.py",
        "tests/test_legal_intelligence_repository.py",
        "tests/test_telematico_repository.py",
        "tests/test_template_atti_repository.py",
        "tests/test_preventivi_repository.py",
        "tests/test_applicazioni_repository.py",
        "tests/test_lex_module.py",
    )
    for snippet in required_core_tests:
        assert snippet in section


def test_agents_documents_ci_no_regression_rule() -> None:
    agents = _read("AGENTS.md")
    required = (
        "CI, coverage e anti-regressione definitiva",
        "Pytest core",
        "Coverage moduli critici",
        "Gate anti-regressione al 100%",
        "target richiesto dall'utente per chiudere definitivamente la coverage critica e' **100%**",
        "vietato dichiarare che il problema coverage sia chiuso",
        "71,49%",
        "release-blocking",
    )
    for snippet in required:
        assert snippet in agents


def test_coverage_config_remains_governed() -> None:
    coverage_config = _read("config/coverage-critical.ini")
    workflow = _read(".github/workflows/ci.yml")
    assert "[run]" in coverage_config
    assert "lex/reasoning/case_law_interpreter.py" in coverage_config
    assert "--cov-config=config/coverage-critical.ini" in workflow
