"""Claude Code hooks for the IUSENTRA repository.

The hooks are intentionally small and repository-local. They avoid absolute
paths so Claude Code and Codex can work in the same checkout.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / ".claude" / "hooks.log"
VERSION_PATH = ROOT / "pct" / "__init__.py"
RAILWAY_PATH = ROOT / "railway.toml"


def _append_log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")


def _read_version() -> str | None:
    try:
        text = VERSION_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else None


def session_start() -> int:
    version = _read_version()
    label = f"IUSENTRA v{version}" if version else "IUSENTRA"
    print(f"[claude-code] {label} pronto in {ROOT}")
    print("[claude-code] Leggere AGENTS.md come fonte canonica prima di modificare.")
    _append_log(f"session-start {label}")
    return 0


def _tool_file_path(payload: dict[str, object]) -> Path | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    path = Path(file_path)
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.resolve()
    except OSError:
        return path


def _sync_railway_version(version: str) -> bool:
    try:
        text = RAILWAY_PATH.read_text(encoding="utf-8")
    except OSError:
        return False
    updated = re.sub(r"^#  version: .*$", f"#  version: {version}", text, flags=re.MULTILINE)
    if updated == text:
        return False
    RAILWAY_PATH.write_text(updated, encoding="utf-8")
    return True


def post_tool_use() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    path = _tool_file_path(payload)
    if path and path == VERSION_PATH.resolve():
        version = _read_version()
        if version and _sync_railway_version(version):
            message = f"railway.toml sincronizzato a v{version}"
            print(f"[claude-code] {message}")
            _append_log(message)
    return 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "session-start":
        return session_start()
    if command == "post-tool-use":
        return post_tool_use()
    print("Uso: hooks.py session-start|post-tool-use", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
