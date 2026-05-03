"""Run the Codex quality gate checks for IUSENTRA."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print("ERRORE: impossibile determinare la root git.")
        sys.exit(1)
    return Path(result.stdout.strip()).resolve()


def run_check(label: str, command: list[str], root: Path) -> int:
    print(f"\n== {label} ==", flush=True)
    result = subprocess.run(command, cwd=root, text=True, check=False)
    if result.returncode == 0:
        print(f"OK: {label}", flush=True)
    else:
        print(f"FAIL: {label} (exit {result.returncode})", flush=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue i controlli Codex Harness.")
    parser.add_argument("--mode", default="dev-tooling", choices=["dev-tooling", "docs", "ui-support", "code"])
    args = parser.parse_args()

    root = repo_root()
    harness = root / "tools" / "codex_harness"
    checks = [
        (
            "Scope",
            [sys.executable, str(harness / "check_codex_scope.py"), "--mode", args.mode],
        ),
        (
            "Dipendenze runtime",
            [sys.executable, str(harness / "check_runtime_dependencies.py")],
        ),
        (
            "Guardrail AGENTS.md",
            [sys.executable, str(harness / "check_agents_guardrails.py")],
        ),
        (
            "Open Design support",
            [sys.executable, str(harness / "check_open_design_support.py")],
        ),
    ]

    failures = 0
    for label, command in checks:
        if run_check(label, command, root) != 0:
            failures += 1

    print("\nRiepilogo Codex quality gate", flush=True)
    if failures:
        print(f"FAIL: {failures} controllo/i non superati.", flush=True)
        return 1

    print("OK: tutti i controlli superati.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
