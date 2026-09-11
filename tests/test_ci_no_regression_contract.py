from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _load_required_checks(*, event: str):
    """Espande `.github/required-checks.json` con lo stesso codice del deploy."""

    path = REPO_ROOT / "tools" / "check_github_required_gates.py"
    spec = importlib.util.spec_from_file_location("iusentra_required_gates", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    config = json.loads((REPO_ROOT / ".github" / "required-checks.json").read_text(encoding="utf-8"))
    return module.expand_required_checks(config, event=event)


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
        "name: Coverage moduli critici parte",
        "tests/test_lex_docling_parser.py",
        "tests/test_storage_strategy.py",
        "--cov-config=config/coverage-critical.ini",
        "coverage-critical-shards:",
        "mv .coverage",
        "include-hidden-files: true",
        "name: Gate anti-regressione CI 100%",
    )
    for snippet in required:
        assert snippet in workflow

    assert "\n  coverage-critical:\n" not in workflow
    assert "name: Coverage moduli critici\n" not in workflow
    assert "--fail-under=71" not in workflow

    thresholds = [int(value) for value in re.findall(r"--cov-fail-under=(\d+)", workflow)]
    thresholds.extend(int(value) for value in re.findall(r"--fail-under=(\d+)", workflow))
    assert thresholds
    assert max(thresholds) >= 100


def test_legacy_coverage_aggregator_resta_solo_advisory_documentato() -> None:
    commit_gates = _read("docs/COMMIT_PUSH_REQUIRED_GATES.md")
    ci_gates = _read("docs/ci-cd-gates.md")
    combined = "\n".join((commit_gates, ci_gates))

    assert "aggregatore legacy" in combined
    assert "solo advisory" in combined
    assert "memoria operativa" in combined
    assert "non diventa required check" in combined
    assert "Coverage moduli critici parte */12" in combined


def test_pytest_core_uses_ten_parallel_shards_without_removing_tests() -> None:
    workflow = _read(".github/workflows/ci.yml")
    shards_section = workflow.split("tests-core-shards:", 1)[1].split("tests-core:", 1)[0]
    summary_section = workflow.split("tests-core:", 1)[1].split("coverage-critical:", 1)[0]

    assert "name: Pytest core fase ${{ matrix.label }}" in shards_section
    assert "fail-fast: false" in shards_section
    assert "include:" in shards_section
    assert "--core-shard ${{ matrix.phase }}" in shards_section
    assert "--core-total-shards 10" in shards_section
    assert "--core-subshard ${{ matrix.subshard }}" in shards_section
    assert "--core-total-subshards ${{ matrix.total_subshards }}" in shards_section
    assert "--core-subdivide-items" in shards_section
    assert "--timeout-minutes 5" in shards_section
    assert "name: Pytest core" in summary_section
    assert "needs['tests-core-shards'].result" in summary_section

    rows = re.findall(
        r"- phase:\s*(\d+)\s+subshard:\s*(\d+)\s+total_subshards:\s*(\d+)\s+"
        r"subdivide_items:\s*(true|false)\s+label:",
        shards_section,
    )
    #  La suddivisione delle fasi viene letta dal runner, non ricopiata qui:
    #  una copia si sfasa in silenzio appena una fase viene suddivisa, e il
    #  contratto smette di sorvegliare proprio cio' per cui esiste.
    runner = _load_pytest_phase_runner()
    expected_subshards = dict(runner.CORE_CI_SUBSHARDS)
    total_shards = int(runner.CORE_CI_TOTAL_SHARDS)
    attese = sum(expected_subshards.get(phase, 1) for phase in range(1, total_shards + 1))

    assert len(rows) == attese
    split_rows = {(int(phase), int(sub), int(total), item_mode) for phase, sub, total, item_mode in rows}
    for phase, total in expected_subshards.items():
        assert {(phase, sub, total, "true") for sub in range(1, total + 1)} <= split_rows
    for phase in range(1, total_shards + 1):
        if phase not in expected_subshards:
            assert (phase, 1, 1, "false") in split_rows

    timeout = re.search(r"timeout-minutes:\s*(\d+)", shards_section)
    assert timeout
    assert int(timeout.group(1)) <= 15

    #  I check richiesti dal deploy devono chiamarsi esattamente come i job
    #  che la CI produce. Quando una fase viene suddivisa il suo job cambia
    #  nome: se l'elenco resta indietro, il deploy attende per novanta minuti
    #  un check che nessuno emettera' mai e fallisce a CI verde (accaduto con
    #  la fase 4 dalla 2.284.0 e con la fase 3 dalla 2.285.1).
    etichette = set(re.findall(r'label:\s*"([^"]+)"', shards_section))
    attesi_dalla_ci = {f"Pytest core fase {etichetta}" for etichetta in etichette}
    richiesti = {
        check.name
        for check in _load_required_checks(event="push")
        if check.name.startswith("Pytest core fase ")
    }
    assert richiesti == attesi_dalla_ci, (
        "Elenco dei check richiesti disallineato dalla matrice di ci.yml. "
        f"Mancano: {sorted(attesi_dalla_ci - richiesti)}. "
        f"Non esistono piu': {sorted(richiesti - attesi_dalla_ci)}."
    )

    core_files = runner.discover_core_test_files()
    #  ``pin_phases`` come nella divisione in fasi vera: senza, i file ancorati
    #  finiscono dove capita e il contratto verificherebbe una distribuzione
    #  che la CI non usa.
    shards = runner.split_core_shards(core_files, total_shards, pin_phases=True)
    discovered = {path.relative_to(REPO_ROOT).as_posix() for path in core_files}
    flattened = [path for shard in shards for path in shard]

    assert len(shards) == 10
    assert all(shard for shard in shards)
    assert len(flattened) == len(core_files)
    assert len(set(flattened)) == len(core_files)
    for phase, total in expected_subshards.items():
        phase_targets = runner.discover_test_items(shards[phase - 1])
        subshards = runner.split_core_shards(phase_targets, total)
        subshard_targets = [target for subshard in subshards for target in subshard]
        assert len(subshards) == total
        assert len(subshard_targets) == len(phase_targets)
        assert len(set(subshard_targets)) == len(phase_targets)
    assert any("tests/test_observability_runtime.py::" in item for item in runner.discover_test_items(shards[6]))
    assert any("tests/test_ocr_worker.py::" in item for item in runner.discover_test_items(shards[7]))

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


def test_ci_uses_five_minute_shards_for_other_test_suites() -> None:
    workflow = _read(".github/workflows/ci.yml")
    quality_overlay = _read(".github/workflows/ci_quality_overlay.yml")
    release_overlay = _read(".github/workflows/ci_release_overlay.yml")
    e2e_nightly = _read(".github/workflows/e2e-nightly.yml")
    frontend = _read(".github/workflows/frontend-ci.yml")
    performance = _read(".github/workflows/performance-nightly.yml")

    required = (
        "--suite coverage-critical",
        "--suite-total-shards 12",
        "--suite e2e-smoke",
        "--suite signer",
        "--suite-total-shards 4",
        "name: Local Signer e PKCS#11",
        "needs['signer-shards'].result",
        "name: Frontend React CI",
        "pnpm --filter @iusentra/studio build:vite",
    )
    combined = "\n".join((workflow, frontend))
    for snippet in required:
        assert snippet in combined

    assert "--suite quality-overlay" in quality_overlay
    assert "--suite-total-shards 3" in quality_overlay
    assert "--suite release-readiness" in release_overlay
    assert "--suite e2e-nightly" in e2e_nightly
    assert "--suite-total-shards 4" in e2e_nightly
    assert "timeout 5m python tools/performance_smoke.py" in performance

    for text in (workflow, quality_overlay, release_overlay, e2e_nightly):
        assert "--timeout-minutes 5" in text

    runner = _load_pytest_phase_runner()
    coverage_files = {path.relative_to(REPO_ROOT).as_posix() for path in runner.discover_suite_test_files("coverage-critical")}
    signer_items = runner.discover_test_items(runner.discover_suite_test_files("signer"))
    e2e_files = {path.relative_to(REPO_ROOT).as_posix() for path in runner.discover_suite_test_files("e2e-nightly")}

    assert "lex/tests/test_gateway_router.py" in coverage_files
    assert "tests/test_storage_strategy.py" in coverage_files
    assert any(item.startswith("tests/test_local_signer.py::") for item in signer_items)
    assert {
        "tests/e2e/test_studio_reale_flow.py",
        "tests/e2e/test_ai_pipeline_full.py",
        "tests/e2e/test_tenant_migration_full.py",
        "tests/e2e/test_operational_crash_day.py",
    } <= e2e_files


def test_agents_documents_ci_no_regression_rule() -> None:
    agents = _read("AGENTS.md")
    required = (
        "CI, coverage e anti-regressione definitiva",
        "Pytest core",
        "Coverage moduli critici parte */12",
        "Gate anti-regressione al 100%",
        "target richiesto dall'utente per chiudere definitivamente la coverage critica e' **100%**",
        "Il vecchio job aggregato `CI / Coverage moduli critici` senza `parte` e' stato eliminato",
        "vietato dichiarare che il problema coverage sia chiuso",
        "Regola permanente nuovi test",
        "tempo massimo di 5 minuti per singolo comando pytest/job operativo",
        "scripts/run_pytest_phases.py",
        "Regole professionali React, shadcn/ui e UI operativa",
        "Budget anti-monolite UI/backend/CSS",
        "componente React: massimo **250 righe**",
        "pagina React: massimo **450 righe**",
        "hook React: massimo **180 righe**",
        "file CSS/SCSS singolo: massimo **400 righe**",
        "Open Design / Open Designer",
        "open-design-support",
        "Impeccable",
        "lucide-react",
        "Performance, accessibilita, sicurezza e quality gate",
        "Report finale",
        "71,49%",
        "release-blocking",
    )
    for snippet in required:
        assert snippet in agents

    pytest_phases = _read("docs/PYTEST_PHASES.md")
    for snippet in (
        "Regola permanente per nuovi test",
        "Nessun nuovo comando",
        "pytest/job operativo deve superare 5 minuti",
        "mantenendo lo stesso perimetro di verifica",
    ):
        assert snippet in pytest_phases


def test_coverage_config_remains_governed() -> None:
    coverage_config = _read("config/coverage-critical.ini")
    workflow = _read(".github/workflows/ci.yml")
    assert "[run]" in coverage_config
    assert "lex/reasoning/case_law_interpreter.py" in coverage_config
    assert "--cov-config=config/coverage-critical.ini" in workflow
