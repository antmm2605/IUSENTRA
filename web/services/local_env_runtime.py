"""Caricamento prudente delle variabili locali prima del bootstrap runtime."""

from __future__ import annotations

import os
from pathlib import Path


def load_local_env_file() -> None:
    """Carica i valori root .env necessari prima di decrittare la configurazione."""

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip('"').strip("'")
    except OSError:
        return
