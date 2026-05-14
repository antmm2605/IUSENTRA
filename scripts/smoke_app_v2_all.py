from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SmokeCommand:
    label: str
    args: tuple[str, ...]
    kind: str


def _script(name: str) -> str:
    return str(REPO_ROOT / "scripts" / name)


def _command_plan(base_url: str, require_credentials: bool) -> dict[str, tuple[SmokeCommand, ...]]:
    require_arg = ("--require-credentials",) if require_credentials else ()
    return {
        "inventory": (
            SmokeCommand("pagine App V2", (_script("smoke_app_v2_pages.py"), "--list"), "inventory"),
            SmokeCommand("routing App V2", (_script("smoke_app_v2_routing.py"), "--list"), "inventory"),
            SmokeCommand("workflow App V2", (_script("smoke_app_v2_workflows.py"), "--list"), "inventory"),
        ),
        "security": (
            SmokeCommand(
                "sicurezza backend",
                (_script("smoke_backend_security.py"), "--base-url", base_url, *require_arg),
                "security",
            ),
        ),
        "pages": (
            SmokeCommand(
                "pagine App V2 HTTP",
                (_script("smoke_app_v2_pages.py"), "--base-url", base_url, *require_arg),
                "pages",
            ),
        ),
        "routing": (
            SmokeCommand(
                "routing App V2 HTTP",
                (_script("smoke_app_v2_routing.py"), "--base-url", base_url, *require_arg),
                "routing",
            ),
        ),
        "workflows": (
            SmokeCommand(
                "workflow App V2 HTTP",
                (_script("smoke_app_v2_workflows.py"), "--base-url", base_url, *require_arg),
                "workflows",
            ),
        ),
        "contracts": (
            SmokeCommand(
                "validazione OpenAPI",
                (_script("validate_openapi.py"), str(REPO_ROOT / "docs" / "openapi.yaml")),
                "contracts",
            ),
            SmokeCommand(
                "provider verification OpenAPI",
                (_script("verify_openapi_provider.py"),),
                "contracts",
            ),
        ),
    }


def _selected_commands(base_url: str, subset: str, require_credentials: bool) -> list[SmokeCommand]:
    plan = _command_plan(base_url, require_credentials)
    if subset == "all":
        order = ("inventory", "security", "pages", "routing", "workflows", "contracts")
    else:
        order = (subset,)
    commands: list[SmokeCommand] = []
    for key in order:
        commands.extend(plan[key])
    return commands


def _sanitized_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    return env


def _run_command(command: SmokeCommand, *, timeout: int) -> int:
    display = " ".join(
        [sys.executable, *[Path(arg).relative_to(REPO_ROOT).as_posix() if arg.startswith(str(REPO_ROOT)) else arg for arg in command.args]]
    )
    print(f"\n== {command.label} ==")
    print(display)
    result = subprocess.run(
        [sys.executable, *command.args],
        cwd=REPO_ROOT,
        env=_sanitized_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        print(f"ERRORE {command.label}: exit {result.returncode}", file=sys.stderr)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke orchestrator App V2 fase 10.")
    parser.add_argument("--base-url", default=os.getenv("IUSENTRA_BASE_URL", "http://127.0.0.1:8080"))
    parser.add_argument(
        "--subset",
        choices=("all", "inventory", "security", "pages", "routing", "workflows", "contracts"),
        default="all",
    )
    parser.add_argument("--require-credentials", action="store_true")
    parser.add_argument("--timeout", type=int, default=240, help="Timeout per sotto-comando in secondi.")
    args = parser.parse_args(argv)

    failures: list[tuple[str, int]] = []
    for command in _selected_commands(args.base_url, args.subset, args.require_credentials):
        try:
            code = _run_command(command, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"ERRORE {command.label}: timeout dopo {args.timeout}s", file=sys.stderr)
            code = 124
        if code != 0:
            failures.append((command.label, code))

    if failures:
        print("\nSmoke App V2 fase 10 fallito:")
        for label, code in failures:
            print(f"- {label}: exit {code}")
        return 1
    print("\nSmoke App V2 fase 10 completato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
