"""Check that Codex changes stay inside the declared task scope."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("ERRORE: impossibile determinare la root git.")
        sys.exit(1)
    return Path(result.stdout.strip()).resolve()


def load_policy(root: Path) -> dict:
    policy_path = root / "tools" / "codex_harness" / "policy.json"
    return json.loads(policy_path.read_text(encoding="utf-8"))


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().strip('"')


def git_lines(args: list[str], root: Path) -> list[str]:
    result = subprocess.run(
        args,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"ERRORE comando git: {' '.join(args)}")
        print(result.stderr.strip())
        sys.exit(1)
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def status_path(line: str) -> str:
    candidate = line[3:] if len(line) > 3 else line
    if " -> " in candidate:
        candidate = candidate.split(" -> ", 1)[1]
    return normalize(candidate)


def changed_files(root: Path) -> tuple[list[str], list[str], str]:
    staged = [normalize(line) for line in git_lines(["git", "diff", "--name-only", "--cached"], root)]
    if staged:
        unstaged: set[str] = set()
        for line in git_lines(["git", "diff", "--name-only"], root):
            path = normalize(line)
            if path not in staged:
                unstaged.add(path)
        for line in git_lines(["git", "status", "--short"], root):
            path = status_path(line)
            if path not in staged:
                unstaged.add(path)
        return sorted(set(staged)), sorted(unstaged), "staged"

    files: set[str] = set()
    for line in git_lines(["git", "diff", "--name-only"], root):
        files.add(normalize(line))
    for line in git_lines(["git", "status", "--short"], root):
        files.add(status_path(line))
    return sorted(files), [], "worktree"


def is_under(path: str, prefixes: list[str]) -> bool:
    normalized = normalize(path)
    return any(normalized.startswith(normalize(prefix)) for prefix in prefixes)


def is_allowed_dev_tooling(path: str, policy: dict) -> bool:
    return path in policy["allowed_dev_tooling_files"] or is_under(path, policy["allowed_dev_tooling_dirs"])


def check_dev_tooling(files: list[str], policy: dict) -> list[str]:
    violations: list[str] = []
    protected_files = {normalize(item) for item in policy["protected_files"]}
    for path in files:
        if path in protected_files:
            violations.append(f"File protetto modificato: {path}")
        if is_under(path, policy["protected_dirs"]):
            violations.append(f"Directory protetta modificata: {path}")
        if not is_allowed_dev_tooling(path, policy):
            violations.append(f"File fuori perimetro dev-tooling: {path}")
    return violations


def check_ui_support(files: list[str], policy: dict) -> list[str]:
    violations: list[str] = []
    protected_files = {normalize(item) for item in policy["protected_files"]}
    allowed = ["tools/open-design-support/", "tools/codex_harness/"]
    for path in files:
        if path in protected_files:
            violations.append(f"File protetto modificato: {path}")
        if is_under(path, policy["protected_dirs"]):
            violations.append(f"Directory protetta modificata: {path}")
        if not is_under(path, allowed):
            violations.append(f"File fuori perimetro ui-support: {path}")
    return violations


def check_docs(files: list[str], policy: dict) -> list[str]:
    violations: list[str] = []
    protected_files = {normalize(item) for item in policy["protected_files"]}
    allowed_dirs = ["docs/", "tools/"]
    allowed_files = {"README.md", "AGENTS.md", "agents.md", "CHANGELOG.md"}
    for path in files:
        if path in protected_files:
            violations.append(f"File protetto modificato: {path}")
        if is_under(path, policy["protected_dirs"]):
            violations.append(f"Directory protetta modificata: {path}")
        if path not in allowed_files and not is_under(path, allowed_dirs):
            violations.append(f"File fuori perimetro docs: {path}")
    return violations


def check_code(files: list[str], policy: dict) -> list[str]:
    violations: list[str] = []
    protected_files = {normalize(item) for item in policy["protected_files"]}
    for path in files:
        if path in protected_files:
            violations.append(f"File protetto modificato: {path}")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlla il perimetro delle modifiche Codex.")
    parser.add_argument("--mode", default="dev-tooling", choices=["dev-tooling", "docs", "ui-support", "code"])
    args = parser.parse_args()

    root = repo_root()
    policy = load_policy(root)
    files, ignored_unstaged, source = changed_files(root)

    print(f"Codex scope check - mode={args.mode} source={source}")
    if not files:
        print("OK: nessun file modificato.")
        return 0

    print("File modificati rilevati:")
    for path in files:
        print(f"- {path}")
    if ignored_unstaged:
        print("\nFile unstaged non inclusi nel perimetro staged:")
        for path in ignored_unstaged:
            print(f"- {path}")

    if args.mode == "dev-tooling":
        violations = check_dev_tooling(files, policy)
    elif args.mode == "ui-support":
        violations = check_ui_support(files, policy)
    elif args.mode == "docs":
        violations = check_docs(files, policy)
    else:
        violations = check_code(files, policy)

    if violations:
        print("\nVIOLAZIONI:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("OK: perimetro rispettato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
