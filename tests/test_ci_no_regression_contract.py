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
