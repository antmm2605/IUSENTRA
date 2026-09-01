#!/usr/bin/env python3
"""Run the IUSENTRA pytest suite in explicit, reviewable phases.

The historical ``python -m pytest -q`` command is still valid, but it can be
too opaque for local release work: a single long-running process hides which
domain is slow or broken. This runner keeps the same tests reachable while
splitting them into named phases that can be launched independently or in
sequence.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeVar


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOTS = [REPO_ROOT / "tests", REPO_ROOT / "lex" / "tests"]
T = TypeVar("T")
LEX_CROSS_SUITE: tuple[Path, ...] = tuple(
    sorted((REPO_ROOT / "tests").glob("test_lex_*.py"))
)
CORE_CI_SUBSHARDS: dict[int, int] = {
    5: 6,
    6: 16,
    7: 3,
    8: 3,
    9: 6,
}
CORE_CI_ITEM_SPLIT_PHASES = set(CORE_CI_SUBSHARDS)
CI_TEST_SUITES: dict[str, tuple[Path, ...]] = {
    "coverage-critical": (
        REPO_ROOT / "lex" / "tests",
        *LEX_CROSS_SUITE,
        REPO_ROOT / "tests" / "test_auth.py",
        REPO_ROOT / "tests" / "test_storage_strategy.py",
        REPO_ROOT / "tests" / "test_storage_governance.py",
        REPO_ROOT / "tests" / "test_telematico_repository.py",
        REPO_ROOT / "tests" / "test_telematico_workflow.py",
        REPO_ROOT / "tests" / "test_telematico_resilience.py",
    ),
    "e2e-smoke": (
        REPO_ROOT / "tests" / "e2e" / "test_studio_reale_flow.py",
    ),
    "signer": (
        REPO_ROOT / "tests" / "test_local_signer.py",
        REPO_ROOT / "tests" / "test_build_dist.py",
        REPO_ROOT / "tests" / "test_visible_signature.py",
    ),
    "quality-overlay": (
        REPO_ROOT / "tests" / "test_lex_quality_gates.py",
        REPO_ROOT / "tests" / "test_performance_budget.py",
        REPO_ROOT / "tests" / "test_local_signer_ai_cache.py",
    ),
    "release-readiness": (
        REPO_ROOT / "tests" / "test_release_readiness.py",
    ),
    "e2e-nightly": (
        REPO_ROOT / "tests" / "e2e" / "test_studio_reale_flow.py",
        REPO_ROOT / "tests" / "e2e" / "test_ai_pipeline_full.py",
        REPO_ROOT / "tests" / "e2e" / "test_tenant_migration_full.py",
        REPO_ROOT / "tests" / "e2e" / "test_operational_crash_day.py",
    ),
}
CORE_TARGETS: tuple[Path, ...] = (
    REPO_ROOT / "lex" / "tests",
    REPO_ROOT / "tests" / "test_auth.py",
    REPO_ROOT / "tests" / "test_scheduler.py",
    REPO_ROOT / "tests" / "test_scheduler_worker.py",
    REPO_ROOT / "tests" / "test_storage_strategy.py",
    REPO_ROOT / "tests" / "test_observability_runtime.py",
    REPO_ROOT / "tests" / "test_ocr_worker.py",
    REPO_ROOT / "tests" / "test_assistente_followup.py",
    REPO_ROOT / "tests" / "test_assistente_language_guidance.py",
    REPO_ROOT / "tests" / "test_assistente_social.py",
    REPO_ROOT / "tests" / "test_assistente_social_intent.py",
    REPO_ROOT / "tests" / "test_assistente_legal_reference_guard.py",
    REPO_ROOT / "tests" / "test_web_bootstrap.py",
    REPO_ROOT / "tests" / "test_web_security.py",
    REPO_ROOT / "tests" / "test_database.py",
    REPO_ROOT / "tests" / "test_local_ai.py",
    REPO_ROOT / "tests" / "test_pst_catalog.py",
    REPO_ROOT / "tests" / "test_giurisprudenza_repository.py",
    REPO_ROOT / "tests" / "test_legal_intelligence_repository.py",
    REPO_ROOT / "tests" / "test_telematico_repository.py",
    REPO_ROOT / "tests" / "test_template_atti_repository.py",
    REPO_ROOT / "tests" / "test_preventivi_repository.py",
    REPO_ROOT / "tests" / "test_applicazioni_repository.py",
    REPO_ROOT / "tests" / "test_lex_module.py",
)


@dataclass(frozen=True)
class Phase:
    name: str
    description: str
    pattern: re.Pattern[str]


PHASES: tuple[Phase, ...] = (
    Phase(
        "00-ci-contracts",
        "Contratti CI, packaging, sicurezza minima e guardrail tecnici rapidi.",
        re.compile(
            r"("
            r"test_ci_|test_packaging_consistency|test_release_readiness|test_backup|"
            r"test_build_dist|test_docker_entrypoint|test_hetzner_backup_retention|"
            r"test_performance_budget|test_secrets_manager|test_security_headers|"
            r"test_upload_security|test_rate_limit|test_cache|test_circuit_breaker|"
            r"test_structured_logging|test_metrics_endpoint|test_jobs"
            r")"
        ),
    ),
    Phase(
        "01-flask-core",
        "Bootstrap Flask, autenticazione, sicurezza web, osservabilita' e superfici operative.",
        re.compile(
            r"("
            r"test_auth|test_auth_management_routes|test_web_bootstrap|test_web_security|"
            r"test_audit_hmac|"
            r"test_healthcheck|test_observability_runtime|test_operational_resilience|"
            r"test_operational_surfaces|test_product_governance_surface|"
            r"test_server_maintenance_surface|test_support_remote|test_config_studio|"
            r"test_config_studio_smtp|test_runtime_resilience|test_scheduler|"
            r"test_scheduler_worker"
            r")"
        ),
    ),
    Phase(
        "02-react-ui",
        "Contratti React, regia, topbar, layout mobile e coerenza design system.",
        re.compile(
            r"("
            r"test_react_|test_regia_|test_topbar_operational_api|"
            r"test_mobile_layout|test_design_tokens|test_dashboard_mailbox_sync|"
            r"test_lex_widget_contract|test_fascicolo_detail_ux"
            r")"
        ),
    ),
    Phase(
        "03-core-business",
        "Domini gestionali: clienti, fascicoli, agenda, preventivi, tariffario e workflow economico.",
        re.compile(
            r"("
            r"test_agenda|test_applicazioni|test_calendar_sync|test_checklist_atti|"
            r"test_clienti|test_compensi|test_condivisione|test_economic_dashboard|"
            r"test_economico_context|test_fascicoli|test_fatturazione|test_messaggi|"
            r"test_motore_preventivo|test_portale_economici|test_preventivi|"
            r"test_profili|test_reports|test_responsabile_conformita|"
            r"test_scadenziario|test_studio_site|test_strumenti_legali|"
            r"test_tariffario|test_tassonomia_preventivi|test_termini_processuali|"
            r"test_timesheet|test_workflow_|test_workspace_intelligente"
            r")"
        ),
    ),
    Phase(
        "04-storage",
        "Persistenza, migrazioni, tenant, repository SQL e parita' storage.",
        re.compile(
            r"("
            r"test_database|test_database_migration|test_repository_sql_parity|"
            r"test_storage_|test_tenant_|test_migration_assistant|test_sync"
            r")"
        ),
    ),
    Phase(
        "05-documents",
        "Documenti, template atti, editor, firma visibile e intelligenza documentale.",
        re.compile(
            r"("
            r"test_compilatore_atti|test_document_|test_editor_|test_template_atti|"
            r"test_visible_signature|test_firme_cades"
            r")"
        ),
    ),
    Phase(
        "06-telematico",
        "PCT, PEC, portali telematici, SIGP, buste, Local Signer e deposito.",
        re.compile(
            r"("
            r"test_busta|test_conformita_pst|test_deposito|test_firma_|"
            r"test_local_pec_bridge|test_local_signer|test_pdp_|test_pec|"
            r"test_polisweb|test_portali_|test_pst_|test_reginde|"
            r"test_sigp_|test_simulazione_deposito|test_sync_uffici|"
            r"test_telematico"
            r")"
        ),
    ),
    Phase(
        "07-lex-ai",
        "Lex, assistenti, fonti ufficiali, legal intelligence, coverage AI e ricerca.",
        re.compile(
            r"("
            r"lex/tests/|test_ai_coverage|test_assistente_|test_gazzetta|"
            r"test_giurisprudenza|test_global_search|test_legal_|test_lex_|"
            r"test_local_ai|test_local_deep_research|test_normative|"
            r"test_normattiva|test_official_sources|test_search_index"
            r")"
        ),
    ),
    Phase(
        "08-e2e",
        "Flussi end-to-end e golden path ufficiali.",
        re.compile(r"(tests/e2e/|test_end_to_end_studio|test_golden_paths)"),
    ),
)

MISC_PHASE = Phase(
    "09-misc",
    "Test non classificati dalle regole sopra: fase di sicurezza, non va ignorata.",
    re.compile(r".*"),
)

PRESETS: dict[str, tuple[str, ...]] = {
    "react-migration": ("00-ci-contracts", "01-flask-core", "02-react-ui"),
    "ci-core-local": (
        "00-ci-contracts",
        "01-flask-core",
        "04-storage",
        "06-telematico",
        "07-lex-ai",
    ),
    "full": tuple(phase.name for phase in (*PHASES, MISC_PHASE)),
}


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def discover_test_files() -> list[Path]:
    files: list[Path] = []
    for root in TEST_ROOTS:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("test_*.py") if path.is_file())
    return sorted(files, key=rel)


def discover_core_test_files() -> list[Path]:
    files: list[Path] = []
    missing: list[str] = []
    for target in CORE_TARGETS:
        if target.is_dir():
            files.extend(path for path in target.rglob("test_*.py") if path.is_file())
        elif target.is_file():
            files.append(target)
        else:
            missing.append(rel(target))

    if missing:
        raise SystemExit(f"Target Pytest core mancanti: {', '.join(missing)}")

    deduped = dict.fromkeys(files)
    return sorted(deduped, key=rel)


def discover_suite_test_files(suite_name: str) -> list[Path]:
    try:
        targets = CI_TEST_SUITES[suite_name]
    except KeyError as exc:
        known = ", ".join(sorted(CI_TEST_SUITES))
        raise SystemExit(f"Suite CI sconosciuta: {suite_name}. Valori ammessi: {known}") from exc

    files: list[Path] = []
    missing: list[str] = []
    for target in targets:
        if target.is_dir():
            files.extend(path for path in target.rglob("test_*.py") if path.is_file())
        elif target.is_file():
            files.append(target)
        else:
            missing.append(rel(target))

    if missing:
        raise SystemExit(f"Target suite {suite_name} mancanti: {', '.join(missing)}")

    deduped = dict.fromkeys(files)
    return sorted(deduped, key=rel)


def split_core_shards(items: list[T], total_shards: int) -> list[list[T]]:
    if total_shards < 1:
        raise SystemExit("--core-total-shards deve essere almeno 1")

    shards: list[list[T]] = [[] for _ in range(total_shards)]
    for index, item in enumerate(items):
        if total_shards == 10 and isinstance(item, Path):
            item_rel = rel(item)
            if item_rel == "tests/test_observability_runtime.py":
                shards[6].append(item)
                continue
            if item_rel == "tests/test_ocr_worker.py":
                shards[7].append(item)
                continue
        shards[index % total_shards].append(item)
    return shards


def discover_test_items(files: Iterable[Path]) -> list[str]:
    """Espande i file in node id pytest per diagnosi a grana fine."""
    items: list[str] = []
    for path in files:
        relative = rel(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            items.append(relative)
            continue

        found = False
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                items.append(f"{relative}::{node.name}")
                found = True
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        items.append(f"{relative}::{node.name}::{child.name}")
                        found = True
        if not found:
            items.append(relative)
    return items


def group_tests(files: Iterable[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {phase.name: [] for phase in (*PHASES, MISC_PHASE)}
    for path in files:
        relative = rel(path)
        for phase in PHASES:
            if phase.pattern.search(relative):
                groups[phase.name].append(path)
                break
        else:
            groups[MISC_PHASE.name].append(path)
    return groups


def phase_by_name(name: str) -> Phase:
    for phase in (*PHASES, MISC_PHASE):
        if phase.name == name:
            return phase
    raise KeyError(name)


def expand_requested_phases(values: list[str] | None) -> list[str]:
    if not values:
        return list(PRESETS["full"])

    expanded: list[str] = []
    for value in values:
        for item in value.split(","):
            name = item.strip()
            if not name:
                continue
            if name in PRESETS:
                expanded.extend(PRESETS[name])
            elif name == "all":
                expanded.extend(PRESETS["full"])
            else:
                expanded.append(name)

    known = {phase.name for phase in (*PHASES, MISC_PHASE)}
    unknown = [name for name in expanded if name not in known]
    if unknown:
        raise SystemExit(f"Fasi sconosciute: {', '.join(unknown)}")

    deduped: list[str] = []
    for name in expanded:
        if name not in deduped:
            deduped.append(name)
    return deduped


def build_summary(groups: dict[str, list[Path]]) -> dict[str, object]:
    phases = []
    for phase in (*PHASES, MISC_PHASE):
        files = groups[phase.name]
        phases.append(
            {
                "name": phase.name,
                "description": phase.description,
                "fileCount": len(files),
                "files": [rel(path) for path in files],
            }
        )
    return {
        "totalFiles": sum(len(files) for files in groups.values()),
        "phases": phases,
        "presets": {key: list(value) for key, value in PRESETS.items()},
    }


def print_list(summary: dict[str, object]) -> None:
    print("Fasi pytest IUSENTRA")
    print("====================")
    print(f"File test totali: {summary['totalFiles']}")
    print("")
    for phase in summary["phases"]:  # type: ignore[index]
        print(f"{phase['name']}: {phase['fileCount']} file")  # type: ignore[index]
        print(f"  {phase['description']}")  # type: ignore[index]
    print("")
    print("Preset:")
    for name, phases in summary["presets"].items():  # type: ignore[index]
        print(f"  {name}: {', '.join(phases)}")


def _target_label(target: Path | str) -> str:
    if isinstance(target, Path):
        return rel(target)
    return target


def build_core_summary(total_shards: int) -> dict[str, object]:
    files = discover_core_test_files()
    shards = split_core_shards(files, total_shards)
    shard_entries: list[dict[str, object]] = []
    for index, shard in enumerate(shards, start=1):
        total_subshards = CORE_CI_SUBSHARDS.get(index, 1)
        item_mode = index in CORE_CI_ITEM_SPLIT_PHASES
        targets: list[Path | str] = discover_test_items(shard) if item_mode else list(shard)
        subshards = split_core_shards(targets, total_subshards)
        shard_entries.append(
            {
                "name": f"core-{index:02d}",
                "fileCount": len(shard),
                "files": [rel(path) for path in shard],
                "targetMode": "test-items" if item_mode else "files",
                "totalSubshards": total_subshards,
                "subshards": [
                    {
                        "name": f"core-{index:02d}.{subindex:02d}",
                        "targetCount": len(subshard),
                        "targets": [_target_label(target) for target in subshard],
                    }
                    for subindex, subshard in enumerate(subshards, start=1)
                ],
            }
        )
    return {
        "totalFiles": len(files),
        "totalShards": total_shards,
        "splitPhases": CORE_CI_SUBSHARDS,
        "shards": shard_entries,
    }


def build_ci_suites_summary() -> dict[str, object]:
    suites: dict[str, object] = {}
    for name in sorted(CI_TEST_SUITES):
        files = discover_suite_test_files(name)
        suites[name] = {
            "fileCount": len(files),
            "itemCount": len(discover_test_items(files)),
            "files": [rel(path) for path in files],
        }
    return {"suites": suites}


def print_core_list(summary: dict[str, object]) -> None:
    print("Fasi Pytest core IUSENTRA")
    print("=========================")
    print(f"File test core totali: {summary['totalFiles']}")
    print(f"Shard paralleli: {summary['totalShards']}")
    print("")
    for shard in summary["shards"]:  # type: ignore[index]
        detail = f"{shard['fileCount']} file"  # type: ignore[index]
        if shard["totalSubshards"] != 1:  # type: ignore[index]
            detail += f", {shard['totalSubshards']} sotto-fasi {shard['targetMode']}"  # type: ignore[index]
        print(f"{shard['name']}: {detail}")  # type: ignore[index]
        for subshard in shard["subshards"]:  # type: ignore[index]
            if shard["totalSubshards"] != 1:  # type: ignore[index]
                print(f"  {subshard['name']}: {subshard['targetCount']} target")  # type: ignore[index]


def print_suite_list(summary: dict[str, object]) -> None:
    print("Suite test CI IUSENTRA")
    print("=====================")
    for name, suite in summary["suites"].items():  # type: ignore[index]
        print(f"{name}: {suite['fileCount']} file, {suite['itemCount']} test item")  # type: ignore[index]


def run_file_set(
    label: str,
    description: str,
    files: list[Path | str],
    *,
    collect_only: bool,
    pytest_args: list[str],
    timeout_minutes: int | None,
    batch_size: int | None = None,
) -> int:
    if not files:
        print(f"\n[{label}] nessun file da eseguire.")
        return 0

    if batch_size and batch_size > 0 and len(files) > batch_size:
        batches = [files[index : index + batch_size] for index in range(0, len(files), batch_size)]
        for index, batch_files in enumerate(batches, start=1):
            batch_label = f"{label}#{index}/{len(batches)}"
            code = run_file_set(
                batch_label,
                description,
                batch_files,
                collect_only=collect_only,
                pytest_args=pytest_args,
                timeout_minutes=timeout_minutes,
            )
            if code != 0:
                return code
        return 0

    cmd = [sys.executable, "-m", "pytest", "-q", *[str(path) for path in files]]
    if collect_only:
        cmd.append("--collect-only")
    cmd.extend(pytest_args)

    print(f"\n[{label}] {description}")
    print(f"[{label}] target: {len(files)}")
    print(f"[{label}] comando: {' '.join(cmd)}")

    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            check=False,
            timeout=None if timeout_minutes is None else timeout_minutes * 60,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        print(f"[{label}] timeout dopo {elapsed:.1f}s")
        return 124

    elapsed = time.monotonic() - started
    print(f"[{label}] esito {completed.returncode} in {elapsed:.1f}s")
    return completed.returncode


def run_phase(
    phase_name: str,
    files: list[Path],
    *,
    collect_only: bool,
    pytest_args: list[str],
    timeout_minutes: int | None,
    batch_size: int | None,
    item_batch_size: int | None,
) -> int:
    phase = phase_by_name(phase_name)
    if batch_size and item_batch_size:
        raise SystemExit("Usa solo uno tra --batch-size e --item-batch-size.")
    if item_batch_size and item_batch_size > 0:
        return run_file_set(
            phase.name,
            phase.description,
            discover_test_items(files),
            collect_only=collect_only,
            pytest_args=pytest_args,
            timeout_minutes=timeout_minutes,
            batch_size=item_batch_size,
        )
    return run_file_set(
        phase.name,
        phase.description,
        files,
        collect_only=collect_only,
        pytest_args=pytest_args,
        timeout_minutes=timeout_minutes,
        batch_size=batch_size,
    )


def write_report(path: Path, summary: dict[str, object], results: list[dict[str, object]] | None = None) -> None:
    payload = dict(summary)
    if results is not None:
        payload["results"] = results
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue pytest IUSENTRA per fasi.")
    parser.add_argument("--phase", action="append", help="Fase, elenco separato da virgola, preset o 'all'.")
    parser.add_argument("--list", action="store_true", help="Mostra fasi, conteggi e preset senza eseguire pytest.")
    parser.add_argument("--core-list", action="store_true", help="Mostra i 10 shard del gate Pytest core CI.")
    parser.add_argument("--core-shard", type=int, help="Esegue uno shard 1-based del gate Pytest core CI.")
    parser.add_argument("--core-total-shards", type=int, default=10, help="Numero di shard Pytest core CI.")
    parser.add_argument("--core-subshard", type=int, default=1, help="Sotto-shard 1-based dentro uno shard Pytest core.")
    parser.add_argument(
        "--core-total-subshards",
        type=int,
        default=1,
        help="Numero di sotto-shard dentro lo shard Pytest core selezionato.",
    )
    parser.add_argument(
        "--core-subdivide-items",
        action="store_true",
        help="Divide lo shard Pytest core in sotto-shard di singoli test item invece che di file.",
    )
    parser.add_argument("--suite-list", action="store_true", help="Mostra le suite test CI aggiuntive.")
    parser.add_argument("--suite", choices=sorted(CI_TEST_SUITES), help="Esegue una suite test CI governata.")
    parser.add_argument("--suite-shard", type=int, default=1, help="Shard 1-based della suite CI selezionata.")
    parser.add_argument("--suite-total-shards", type=int, default=1, help="Numero di shard della suite CI selezionata.")
    parser.add_argument(
        "--suite-subdivide-items",
        action="store_true",
        help="Divide la suite CI in sotto-shard di singoli test item invece che di file.",
    )
    parser.add_argument("--json", action="store_true", help="Con --list stampa JSON invece del riepilogo testuale.")
    parser.add_argument("--collect-only", action="store_true", help="Passa --collect-only a pytest per validare la raccolta.")
    parser.add_argument("--timeout-minutes", type=int, help="Timeout massimo per singola fase.")
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Spezza ogni fase in batch da N file. Usa 1 per isolare un file lento o bloccato.",
    )
    parser.add_argument(
        "--item-batch-size",
        type=int,
        help="Spezza ogni fase in batch da N test item per diagnosticare file molto lenti.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Scrive un report JSON delle fasi e, se eseguite, dei risultati.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Argomenti extra da passare a pytest dopo '--'.",
    )
    args = parser.parse_args()

    pytest_args = args.pytest_args
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]

    if args.suite_list:
        suite_summary = build_ci_suites_summary()
        if args.json:
            print(json.dumps(suite_summary, indent=2, ensure_ascii=False))
        else:
            print_suite_list(suite_summary)
        if args.report:
            write_report(args.report, suite_summary)
        if args.suite is None:
            return 0

    if args.suite is not None:
        suite_files = discover_suite_test_files(args.suite)
        targets: list[Path | str] = discover_test_items(suite_files) if args.suite_subdivide_items else list(suite_files)
        suite_shards = split_core_shards(targets, args.suite_total_shards)
        suite_index = args.suite_shard - 1
        if suite_index < 0 or suite_index >= args.suite_total_shards:
            raise SystemExit(
                "--suite-shard deve essere tra 1 e "
                f"{args.suite_total_shards}: ricevuto {args.suite_shard}"
            )

        suite_targets = suite_shards[suite_index]
        label = f"{args.suite}-{args.suite_shard:02d}-{args.suite_total_shards}"
        code = run_file_set(
            label,
            f"Suite CI {args.suite}, shard {args.suite_shard}/{args.suite_total_shards}.",
            suite_targets,
            collect_only=args.collect_only,
            pytest_args=pytest_args,
            timeout_minutes=args.timeout_minutes,
            batch_size=args.batch_size,
        )
        if args.report:
            write_report(
                args.report,
                build_ci_suites_summary(),
                [{"phase": label, "exitCode": code, "targetCount": len(suite_targets)}],
            )
        return code

    if args.core_list or args.core_shard is not None:
        core_summary = build_core_summary(args.core_total_shards)
        if args.core_list:
            if args.json:
                print(json.dumps(core_summary, indent=2, ensure_ascii=False))
            else:
                print_core_list(core_summary)
            if args.report:
                write_report(args.report, core_summary)
            if args.core_shard is None:
                return 0

        shard_index = args.core_shard - 1
        if shard_index < 0 or shard_index >= args.core_total_shards:
            raise SystemExit(
                f"--core-shard deve essere tra 1 e {args.core_total_shards}: ricevuto {args.core_shard}"
            )

        files = discover_core_test_files()
        shards = split_core_shards(files, args.core_total_shards)
        shard_files = shards[shard_index]
        targets: list[Path | str] = discover_test_items(shard_files) if args.core_subdivide_items else list(shard_files)
        subshards = split_core_shards(targets, args.core_total_subshards)
        subshard_index = args.core_subshard - 1
        if subshard_index < 0 or subshard_index >= args.core_total_subshards:
            raise SystemExit(
                "--core-subshard deve essere tra 1 e "
                f"{args.core_total_subshards}: ricevuto {args.core_subshard}"
            )

        shard_targets = subshards[subshard_index]
        label = f"core-{args.core_shard:02d}"
        if args.core_total_subshards > 1:
            label = f"{label}.{args.core_subshard:02d}-{args.core_total_subshards}"
        code = run_file_set(
            label,
            (
                f"Shard {args.core_shard}/{args.core_total_shards}, "
                f"sotto-shard {args.core_subshard}/{args.core_total_subshards} "
                "del gate Pytest core CI."
            ),
            shard_targets,
            collect_only=args.collect_only,
            pytest_args=pytest_args,
            timeout_minutes=args.timeout_minutes,
            batch_size=args.batch_size,
        )
        if args.report:
            write_report(
                args.report,
                core_summary,
                [{"phase": label, "exitCode": code, "targetCount": len(shard_targets)}],
            )
        return code

    files = discover_test_files()
    groups = group_tests(files)
    summary = build_summary(groups)

    if args.list:
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print_list(summary)
        if args.report:
            write_report(args.report, summary)
        return 0

    requested = expand_requested_phases(args.phase)
    results: list[dict[str, object]] = []
    exit_code = 0
    for name in requested:
        code = run_phase(
            name,
            groups[name],
            collect_only=args.collect_only,
            pytest_args=pytest_args,
            timeout_minutes=args.timeout_minutes,
            batch_size=args.batch_size,
            item_batch_size=args.item_batch_size,
        )
        results.append({"phase": name, "exitCode": code, "fileCount": len(groups[name])})
        if code != 0:
            exit_code = code
            break

    if args.report:
        write_report(args.report, summary, results)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
