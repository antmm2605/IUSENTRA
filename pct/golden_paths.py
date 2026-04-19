"""Golden path ufficiali del prodotto con report eseguibile e persistito."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class GoldenPathSuite:
    suite_id: str
    label: str
    business_outcome: str
    criticality: str
    surfaces: tuple[str, ...]
    pytest_selectors: tuple[str, ...]


GOLDEN_PATH_SUITES: tuple[GoldenPathSuite, ...] = (
    GoldenPathSuite(
        suite_id="bootstrap_admin",
        label="Bootstrap, login e superfici admin",
        business_outcome="L'app parte, autentica l'utente e rende raggiungibili le superfici amministrative core.",
        criticality="critico",
        surfaces=("login", "dashboard admin", "bootstrap Flask", "observability"),
        pytest_selectors=(
            "tests/test_web_bootstrap.py",
            "tests/test_observability_runtime.py",
            "tests/test_operational_surfaces.py",
        ),
    ),
    GoldenPathSuite(
        suite_id="migrazione_tenant",
        label="Migrazione tenant, diff e cutover",
        business_outcome="Lo studio migra davvero, produce report reale, cutover controllato e rollback governato.",
        criticality="critico",
        surfaces=("assistente migrazione", "storage parity", "cutover PostgreSQL"),
        pytest_selectors=(
            "tests/test_migration_assistant.py",
            "tests/test_storage_postgres_migration.py",
            "tests/test_storage_governance.py",
        ),
    ),
    GoldenPathSuite(
        suite_id="workflow_business",
        label="Workflow cliente -> fascicolo -> parcella -> incasso",
        business_outcome="Il ciclo commerciale ed economico resta utilizzabile da onboarding a saldo cliente.",
        criticality="alto",
        surfaces=("workflow commerciale", "dashboard economica", "portale economici"),
        pytest_selectors=(
            "tests/test_clienti_workflow.py",
            "tests/test_workflow_pipeline.py",
            "tests/test_workflow_commerciale.py",
            "tests/test_economic_dashboard.py",
            "tests/test_portale_economici.py",
        ),
    ),
    GoldenPathSuite(
        suite_id="coverage_ai_review_publish",
        label="Copertura AI: audit -> gap -> review -> publish SQL",
        business_outcome="La pipeline Coverage AI genera draft, li revisiona e li pubblica davvero su repository SQL.",
        criticality="critico",
        surfaces=("dashboard coverage", "review UI", "publish SQL"),
        pytest_selectors=(
            "tests/test_legal_coverage_pipeline.py",
            "tests/test_legal_coverage_surface.py",
        ),
    ),
    GoldenPathSuite(
        suite_id="update_intelligence_review_publish",
        label="Update Intelligence: fonti -> staging -> review -> news",
        business_outcome="Il motore aggiornamenti legali acquisisce fonti, apre review e pubblica news strutturate.",
        criticality="alto",
        surfaces=("fonti", "staging", "review queue", "news giuridiche"),
        pytest_selectors=(
            "tests/test_legal_updates_pipeline.py",
            "tests/test_legal_intelligence.py",
        ),
    ),
    GoldenPathSuite(
        suite_id="telematico_ufficiale",
        label="Telematico ufficiale: consultazione, import e deposito",
        business_outcome="I portali ufficiali e il deposito telematico mantengono parita' di flusso e regole PST/PDP/PAT.",
        criticality="critico",
        surfaces=("polisWeb", "PDP", "PAT", "simulazione deposito"),
        pytest_selectors=(
            "tests/test_polisweb.py",
            "tests/test_telematico_workflow.py",
            "tests/test_pdp_penale_workflow.py",
            "tests/test_simulazione_deposito.py",
        ),
    ),
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _resolve_report_dir(base_dir: str = "") -> Path:
    configured = str(base_dir or os.getenv("PCT_GOLDEN_PATH_REPORT_DIR") or "./data/governance").strip()
    return Path(configured)


def _latest_report_payload(base_dir: str = "") -> dict[str, Any] | None:
    report_dir = _resolve_report_dir(base_dir)
    if not report_dir.exists():
        return None
    latest_file = report_dir / "golden_paths_latest.json"
    if latest_file.exists():
        try:
            payload = json.loads(latest_file.read_text(encoding="utf-8"))
        except Exception:
            payload = None
        if isinstance(payload, dict):
            payload["_path"] = str(latest_file)
            return payload
    best_payload: dict[str, Any] | None = None
    for candidate in report_dir.glob("golden_paths_*.json"):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        payload["_path"] = str(candidate)
        if best_payload is None or str(payload.get("generated_at") or "") >= str(best_payload.get("generated_at") or ""):
            best_payload = payload
    return best_payload


def _suite_row_base(suite: GoldenPathSuite) -> dict[str, Any]:
    return {
        "suite_id": suite.suite_id,
        "label": suite.label,
        "business_outcome": suite.business_outcome,
        "criticality": suite.criticality,
        "surfaces": list(suite.surfaces),
        "pytest_selectors": list(suite.pytest_selectors),
        "status": "not_run",
        "status_label": "Non eseguito",
        "duration_seconds": 0.0,
        "completed_at": "",
        "output_excerpt": "",
    }


def build_golden_path_payload(*, base_dir: str = "", report_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(report_payload or _latest_report_payload(base_dir) or {})
    registry_rows = {suite.suite_id: _suite_row_base(suite) for suite in GOLDEN_PATH_SUITES}
    for row in payload.get("suites") or []:
        suite_id = str((row or {}).get("suite_id") or "").strip()
        if suite_id and suite_id in registry_rows:
            merged = registry_rows[suite_id]
            merged.update({key: value for key, value in dict(row or {}).items() if key in merged or key in {"return_code"}})
            registry_rows[suite_id] = merged

    rows = [registry_rows[suite.suite_id] for suite in GOLDEN_PATH_SUITES]
    passed = sum(1 for row in rows if row["status"] == "passed")
    failed = sum(1 for row in rows if row["status"] == "failed")
    not_run = sum(1 for row in rows if row["status"] == "not_run")
    return {
        "summary": {
            "paths_total": len(rows),
            "passed": passed,
            "failed": failed,
            "not_run": not_run,
            "last_generated_at": str(payload.get("generated_at") or ""),
            "last_report_path": str(payload.get("_path") or payload.get("report_path") or ""),
            "status": "failed" if failed else "passed" if passed and not not_run else "not_run",
        },
        "rows": rows,
    }


def run_golden_path_suites(*, base_dir: str = "", cwd: str = "") -> dict[str, Any]:
    working_dir = str(cwd or Path.cwd())
    rows: list[dict[str, Any]] = []
    for suite in GOLDEN_PATH_SUITES:
        started = monotonic()
        completed_at = _now_iso()
        cmd = [sys.executable, "-m", "pytest", "-q", *suite.pytest_selectors]
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        duration_seconds = round(monotonic() - started, 2)
        stdout = str(result.stdout or "").strip()
        stderr = str(result.stderr or "").strip()
        excerpt_lines = [line for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
        output_excerpt = "\n".join(excerpt_lines[-12:])
        rows.append(
            {
                **asdict(suite),
                "surfaces": list(suite.surfaces),
                "pytest_selectors": list(suite.pytest_selectors),
                "status": "passed" if result.returncode == 0 else "failed",
                "status_label": "Pass" if result.returncode == 0 else "Fail",
                "return_code": int(result.returncode),
                "duration_seconds": duration_seconds,
                "completed_at": completed_at,
                "output_excerpt": output_excerpt,
            }
        )

    report = {
        "generated_at": _now_iso(),
        "cwd": working_dir,
        "success": all(row["status"] == "passed" for row in rows),
        "suites": rows,
    }
    report_dir = _resolve_report_dir(base_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"golden_paths_{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = report_dir / "golden_paths_latest.json"
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
