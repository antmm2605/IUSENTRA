from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "audit"


@dataclass(frozen=True)
class AuditCommand:
    area: str
    label: str
    command: list[str]
    critical: bool = True


def _python() -> str:
    return sys.executable


def _npm() -> str:
    return shutil.which("npm") or "npm"


COMMANDS: list[AuditCommand] = [
    AuditCommand(
        "Sintassi",
        "Compilazione moduli critici",
        [
            _python(),
            "-m",
            "py_compile",
            "web/services/telematico_runtime.py",
            "web/services/fascicoli_runtime.py",
            "web/bootstrap/portali_acquisizione_routes.py",
            "pct/database.py",
            "web/bootstrap/admin_database_routes.py",
            "web/services/react_admin_database_bridge.py",
            "pct/pec_legal_workflow.py",
            "pct/pec_pipeline.py",
            "pct/notifiche_legali.py",
        ],
    ),
    AuditCommand("Frontend", "Typecheck React", [_npm(), "--prefix", "frontend", "run", "typecheck"]),
    AuditCommand("Frontend", "Build Vite", [_npm(), "--prefix", "frontend", "run", "build"]),
    AuditCommand(
        "Step 7 PST/Local Signer",
        "Import documenti reali, catalogo e contenuto mancante",
        [
            _python(),
            "-m",
            "pytest",
            "tests/test_polisweb.py",
            "-k",
            "lotto_otto_documenti or blocca_file_senza_contenuto or salva_lotto_sette_documenti or "
            "blocca_catalogo_senza_file or parziale_aggiorna_pratica_esistente",
            "-q",
        ],
    ),
    AuditCommand(
        "SQLite",
        "Pre-verifica, riconciliazione e blocco anti-perdita",
        [_python(), "-m", "pytest", "tests/test_database.py", "-k", "sqlite or admin_database", "-q"],
    ),
    AuditCommand(
        "PEC legale",
        "Classificazione PEC, registri, eventi e pipeline",
        [
            _python(),
            "-m",
            "pytest",
            "tests/test_pec_legal_workflow.py",
            "tests/test_pec_audit_pipeline.py",
            "-k",
            "pec or deposit_lifecycle or react_email_bridge_lists",
            "-q",
        ],
    ),
    AuditCommand(
        "Attestazione conformità",
        "Modello autocompilante e DOCX generato",
        [_python(), "-m", "pytest", "tests/test_notifiche_legali.py", "-k", "attestazione_conformita", "-q"],
    ),
    AuditCommand(
        "React shell",
        "Contratti UI amministrazione database e PST",
        [
            _python(),
            "-m",
            "pytest",
            "tests/test_react_shell.py",
            "-k",
            "admin_database or portale_acquisizione or react_wizard_pst",
            "-q",
        ],
    ),
    AuditCommand("UTF-8", "Presidio testi italiani", [_python(), "-m", "pytest", "tests/test_utf8_integrity.py", "-q", "--tb=short"]),
    AuditCommand("Git", "Whitespace e patch check", ["git", "diff", "--check"]),
]


def run_command(item: AuditCommand) -> dict[str, object]:
    started = datetime.now()
    completed = subprocess.run(
        item.command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = (datetime.now() - started).total_seconds()
    return {
        "area": item.area,
        "label": item.label,
        "command": item.command,
        "critical": item.critical,
        "returncode": completed.returncode,
        "elapsed_seconds": round(elapsed, 2),
        "stdout": completed.stdout[-6000:],
        "stderr": completed.stderr[-6000:],
    }


def run_coverage() -> dict[str, object]:
    data_file = ARTIFACT_DIR / ".coverage-pst-sqlite-pec"
    run = subprocess.run(
        [
            _python(),
            "-m",
            "coverage",
            "run",
            f"--data-file={data_file}",
            "-m",
            "pytest",
            "tests/test_pec_legal_workflow.py",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = subprocess.run(
        [
            _python(),
            "-m",
            "coverage",
            "report",
            f"--data-file={data_file}",
            "--include=pct/pec_legal_workflow.py",
            "-m",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        data_file.unlink(missing_ok=True)
    except OSError:
        pass
    ok = run.returncode == 0 and report.returncode == 0 and "100%" in report.stdout
    return {
        "area": "Copertura",
        "label": "Copertura 100% classificatore PEC legale",
        "command": "coverage run/report tests/test_pec_legal_workflow.py --include=pct/pec_legal_workflow.py",
        "returncode": 0 if ok else 1,
        "stdout": (run.stdout + "\n" + report.stdout)[-6000:],
        "stderr": (run.stderr + "\n" + report.stderr)[-6000:],
        "coverage_target": "pct/pec_legal_workflow.py",
        "coverage_required": "100%",
    }


def git_snapshot() -> dict[str, str]:
    def read(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout.strip()

    return {
        "head": read("rev-parse", "HEAD"),
        "branch": read("branch", "--show-current"),
        "changed_files": read("diff", "--name-only"),
        "status": read("status", "--short"),
    }


def cleanup_frontend_build_artifacts() -> None:
    """Rimuove gli asset Vite generati localmente durante l'audit."""

    subprocess.run(
        ["git", "restore", "--", "web/static/react/.vite/manifest.json", "web/static/react/index.html"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    subprocess.run(
        ["git", "clean", "-fd", "--", "web/static/react/assets"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def render_markdown(results: list[dict[str, object]], coverage: dict[str, object], snapshot: dict[str, str]) -> str:
    all_results = [*results, coverage]
    failed = [item for item in all_results if int(item.get("returncode", 1)) != 0]
    lines = [
        "# Audit finale PST / SQLite / PEC",
        "",
        f"Generato: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Branch: `{snapshot['branch']}`",
        f"Commit di partenza: `{snapshot['head']}`",
        f"Esito complessivo: {'NON SUPERATO' if failed else 'SUPERATO'}",
        "",
        "## Nota copertura",
        "",
        "Il report non dichiara copertura globale 100% del progetto storico. "
        "La soglia 100% viene applicata al nuovo classificatore PEC legale, "
        "mentre Step 7, SQLite, UI React e attestazione sono presidiati da fixture mirate e gate di regressione.",
        "",
        "## Comandi",
        "",
        "| Area | Verifica | Esito | Secondi |",
        "| --- | --- | --- | --- |",
    ]
    for item in all_results:
        status = "OK" if int(item.get("returncode", 1)) == 0 else "ERRORE"
        elapsed = item.get("elapsed_seconds", "")
        lines.append(f"| {item['area']} | {item['label']} | {status} | {elapsed} |")
    lines.extend(["", "## File modificati", "", "```text", snapshot["changed_files"] or "(nessun diff)", "```", ""])
    if failed:
        lines.extend(["## Errori", ""])
        for item in failed:
            lines.extend(
                [
                    f"### {item['area']} - {item['label']}",
                    "",
                    "```text",
                    str(item.get("stdout", "")).strip(),
                    str(item.get("stderr", "")).strip(),
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "## Esito operativo",
                "",
                "- Step 7 PST/Local Signer: fixture di importazione reale, catalogo e contenuto mancante eseguite.",
                "- SQLite: pre-verifica, riconciliazione e blocco anti-perdita eseguiti.",
                "- PEC: registri, famiglie, eventi e correlazione eseguiti.",
                "- UI React: typecheck, build e contratti mirati eseguiti.",
                "- Attestazione: payload e DOCX autocompilante verificati.",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit finale PST, SQLite, PEC e attestazione conformità.")
    parser.add_argument("--json", action="store_true", help="Scrive anche il report JSON dettagliato.")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_command(item) for item in COMMANDS]
    coverage = run_coverage()
    cleanup_frontend_build_artifacts()
    snapshot = git_snapshot()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    md_path = ARTIFACT_DIR / f"finale-pst-sqlite-pec-{timestamp}.md"
    md_path.write_text(render_markdown(results, coverage, snapshot), encoding="utf-8")
    if args.json:
        json_path = ARTIFACT_DIR / f"finale-pst-sqlite-pec-{timestamp}.json"
        json_path.write_text(
            json.dumps({"results": results, "coverage": coverage, "git": snapshot}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json_path)
    print(md_path)
    failed = [item for item in [*results, coverage] if int(item.get("returncode", 1)) != 0]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
