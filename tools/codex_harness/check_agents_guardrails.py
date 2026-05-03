"""Check that AGENTS.md still contains required guardrail phrases."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


KEYWORDS = [
    "Storage SQL obbligatorio",
    "Portale Servizi Telematici",
    "Lex AI",
    "CI, coverage",
    "MetaHarness",
    "Autoresearch-lite",
    "Open Design",
]


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


def load_policy(root: Path) -> dict:
    policy_path = root / "tools" / "codex_harness" / "policy.json"
    return json.loads(policy_path.read_text(encoding="utf-8"))


def main() -> int:
    root = repo_root()
    print("AGENTS guardrails check")
    if "AGENTS.md" not in changed_files(root):
        print("OK: AGENTS.md non modificato.")
        return 0

    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    policy = load_policy(root)
    required = list(dict.fromkeys(policy.get("agents_required_phrases", []) + KEYWORDS))
    missing = [phrase for phrase in required if phrase not in text]

    if missing:
        print("VIOLAZIONE: AGENTS.md non contiene piu' frasi obbligatorie:")
        for phrase in missing:
            print(f"- {phrase}")
        return 1

    print("OK: AGENTS.md conserva i guardrail richiesti.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
