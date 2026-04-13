"""Helper condivisi per riconoscere il runtime applicativo."""

from __future__ import annotations

import os


MANAGED_CLOUD_ENV_VARS: tuple[str, ...] = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_SERVICE_ID",
    "RENDER",
    "RENDER_SERVICE_ID",
)


def is_managed_cloud_runtime() -> bool:
    """Rileva runtime cloud gestiti dove l'AI deve restare fuori dal volume persistente."""
    return any(os.getenv(name) for name in MANAGED_CLOUD_ENV_VARS)
