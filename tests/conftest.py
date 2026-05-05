"""Configurazione pytest condivisa.

Su Windows alcune combinazioni Python/pytest lasciano `pytest-current` come
directory reparse point non eliminabile con `Path.unlink()`. Il problema emerge
solo in cleanup atexit e sporca l'output pur con test verdi. Questa patch usa
la rimozione corretta per link a directory e degrada silenziosamente solo se il
link e' gia' gestito/lockato dal sistema operativo.
"""

from __future__ import annotations

import os
from pathlib import Path


if os.name == "nt":
    import _pytest.pathlib as _pytest_pathlib

    def _cleanup_dead_symlinks_windows(root: Path) -> None:
        for leftover in root.iterdir():
            try:
                if not leftover.is_symlink() or leftover.resolve().exists():
                    continue
            except OSError:
                continue
            try:
                leftover.unlink()
            except PermissionError:
                try:
                    os.rmdir(leftover)
                except OSError:
                    pass
            except FileNotFoundError:
                pass

    _pytest_pathlib.cleanup_dead_symlinks = _cleanup_dead_symlinks_windows
