"""Check that runtime dependency manifests were not changed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


DEPENDENCY_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements/base.txt",
    "requirements/dev.txt",
    "pyproject.toml",
    "setup.py",
    "package.json",
    "pnpm-lock.yaml",
    "package-lock.json",
}


def repo_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print("ERRORE: impossibile determinare la root git.")
        sys.exit(1)
    return Path(result.stdout.strip()).resolve()


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().strip('"')


def status_path(line: str) -> str:
    candidate = line[3:] if len(line) > 3 else line
    if " -> " in candidate:
        candidate = candidate.split(" -> ", 1)[1]
    return normalize(candidate)


def git_lines(args: list[str], root: Path) -> list[str]:
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"ERRORE comando git: {' '.join(args)}")
        print(result.stderr.strip())
        sys.exit(1)
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(root: Path) -> set[str]:
    files = {normalize(line) for line in git_lines(["git", "diff", "--name-only"], root)}
    files.update(status_path(line) for line in git_lines(["git", "status", "--short"], root))
    return files


def main() -> int:
    root = repo_root()
    changed = changed_files(root)
    violations = sorted(changed.intersection(DEPENDENCY_FILES))

    print("Runtime dependency check")
    if violations:
        print("VIOLAZIONE: file dipendenze/runtime modificati:")
        for path in violations:
            print(f"- {path}")
        return 1

    print("OK: nessuna dipendenza runtime modificata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
