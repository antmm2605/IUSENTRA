from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VERSION_FILE = REPO_ROOT / "pct" / "__init__.py"

_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')


def read_version() -> str:
    match = _VERSION_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError("Versione package non trovata in pct/__init__.py")
    return match.group(1)


def _iter_requirement_lines(path: Path, *, seen_files: set[Path] | None = None) -> list[str]:
    resolved = path.resolve()
    visited = seen_files if seen_files is not None else set()
    if resolved in visited:
        raise RuntimeError(f"Include requirements circolare rilevata: {resolved}")
    visited.add(resolved)
    values: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            include_name = line[3:].strip()
            values.extend(_iter_requirement_lines(path.parent / include_name, seen_files=visited))
            continue
        if line not in values:
            values.append(line)
    return values


def read_requirements(relative_path: str) -> list[str]:
    return _iter_requirement_lines((REPO_ROOT / relative_path).resolve())


def runtime_requirements() -> list[str]:
    return read_requirements("requirements/base.txt")


def dev_requirements() -> list[str]:
    return read_requirements("requirements/dev.txt")


def extras_requirements() -> dict[str, list[str]]:
    return {
        "pdf": read_requirements("requirements/pdf.txt"),
        "lex-docling": read_requirements("requirements/lex-docling.txt"),
        "pades": read_requirements("requirements/pades.txt"),
        "pkcs11": read_requirements("requirements/pkcs11.txt"),
    }


def render_flat_requirements(header: str, values: list[str]) -> str:
    lines = [header.rstrip(), ""]
    lines.extend(values)
    return "\n".join(lines).rstrip() + "\n"
