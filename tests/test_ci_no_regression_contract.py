from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _load_pytest_phase_runner() -> ModuleType:
    path = REPO_ROOT / "scripts" / "run_pytest_phases.py"
    spec = importlib.util.spec_from_file_location("iusentra_pytest_phases", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_pytest_core_uses_ten_parallel_shards_without_removing_tests() -> None:
    workflow = _read(".github/workflows/ci.yml")
    shards_section = workflow.split("tests-core-shards:", 1)[1].split("tests-core:", 1)[0]
    summary_section = workflow.split("tests-core:", 1)[1].split("coverage-critical:", 1)[0]

    assert "name: Pytest core fase ${{ matrix.phase }}/10" in shards_section
    assert "fail-fast: false" in shards_section
    assert "phase: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]" in shards_section
    assert "--core-shard ${{ matrix.phase }}" in shards_section
    assert "--core-total-shards 10" in shards_section
    assert "--timeout-minutes 10" in shards_section
    assert "name: Pytest core" in summary_section
    assert "needs['tests-core-shards'].result" in summary_section

    timeout = re.search(r"timeout-minutes:\s*(\d+)", shards_section)
    assert timeout
    assert int(timeout.group(1)) <= 15

    runner = _load_pytest_phase_runner()
    core_files = runner.discover_core_test_files()
    shards = runner.split_core_shards(core_files, 10)
    discovered = {path.relative_to(REPO_ROOT).as_posix() for path in core_files}
    flattened = [path for shard in shards for path in shard]

    assert len(shards) == 10
    assert all(shard for shard in shards)
    assert len(flattened) == len(core_files)
    assert len(set(flattened)) == len(core_files)

    required_core_tests = (
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
        assert snippet in discovered

    lex_tests = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "lex" / "tests").rglob("test_*.py")
    }
    assert lex_tests
    assert lex_tests <= discovered


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
