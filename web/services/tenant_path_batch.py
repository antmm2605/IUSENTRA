"""Risoluzione fisica in gruppo dei percorsi privati, senza cache tra richieste."""
from __future__ import annotations

import os
import stat
from pathlib import Path


def resolve_private_paths(paths: dict[str, str], root: Path) -> dict[str, Path]:
    """Controlla ogni componente condiviso una volta nel medesimo gruppo."""
    resolved = {}
    prefixes: dict[Path, Path] = {}
    for key, value in paths.items():
        path = Path(value).expanduser()
        if os.name != 'posix' or not path.is_absolute() or '..' in path.parts:
            resolved[key] = path.resolve()
            continue
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            # Anche un alias esterno va risolto fisicamente, prima del controllo.
            resolved[key] = path.resolve()
            continue
        logical = physical = root
        for part in parts:
            logical = logical / part
            if logical not in prefixes:
                candidate = physical / part
                try:
                    mode = candidate.lstat().st_mode
                except (FileNotFoundError, NotADirectoryError):
                    prefixes[logical] = candidate
                else:
                    prefixes[logical] = candidate.resolve() if stat.S_ISLNK(mode) else candidate
            physical = prefixes[logical]
        resolved[key] = physical
    return resolved
