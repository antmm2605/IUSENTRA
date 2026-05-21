"""Controlli condivisi per percorsi runtime usati da storage e migrazioni."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable


class UnsafeRuntimePath(ValueError):
    """Percorso fuori dalle radici runtime consentite."""


def _candidate_roots(extra_roots: Iterable[str | Path] = ()) -> list[Path]:
    roots: list[Path] = []
    for value in (
        os.getenv("IUSENTRA_DATA_DIR"),
        os.getenv("PCT_DATA_ROOT"),
        os.getenv("PCT_TENANTS_ROOT"),
        "./data",
        "/data",
        tempfile.gettempdir(),
        Path.cwd(),
        *extra_roots,
    ):
        if not value:
            continue
        try:
            roots.append(Path(value).expanduser().resolve())
        except (OSError, RuntimeError, ValueError):
            continue
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        marker = os.path.normcase(str(root))
        if marker not in seen:
            seen.add(marker)
            unique.append(root)
    return unique


def _under_root(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(root)]) == str(root)
    except ValueError:
        return False


def resolve_runtime_path(
    value: str | Path,
    *,
    allowed_suffixes: set[str] | None = None,
    extra_roots: Iterable[str | Path] = (),
) -> Path:
    """Restituisce un percorso assoluto solo se resta in una radice runtime nota."""

    raw = os.fspath(value or "").strip()
    if not raw or "\x00" in raw:
        raise UnsafeRuntimePath("Percorso runtime non valido.")
    candidate = Path(raw).expanduser().resolve()
    if allowed_suffixes is not None and candidate.suffix.lower() not in allowed_suffixes:
        raise UnsafeRuntimePath("Estensione del percorso runtime non consentita.")
    for root in _candidate_roots(extra_roots):
        if _under_root(candidate, root):
            return candidate
    raise UnsafeRuntimePath("Percorso runtime fuori dalle radici consentite.")


def resolve_sqlite_path(value: str | Path, *, extra_roots: Iterable[str | Path] = ()) -> Path:
    return resolve_runtime_path(value, allowed_suffixes={".db", ".sqlite", ".sqlite3"}, extra_roots=extra_roots)
