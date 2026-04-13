"""Guardrail per ambienti cloud-hosted come Railway."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from flask import Flask
from pct.runtime_env import is_managed_cloud_runtime


def _ephemeral_local_ai_root() -> Path:
    base = Path(os.getenv("PCT_EPHEMERAL_RUNTIME_DIR", "/tmp/hacs-runtime"))
    return base / "local_ai"


def _remove_tree(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        return


def prune_hosted_local_ai_persistent_artifacts(app: Flask) -> None:
    if not is_managed_cloud_runtime():
        return

    targets: list[Path] = [
        Path("/data/intelligence/models"),
        Path("/data/intelligence/runtime"),
        Path("/data/intelligence/downloads"),
    ]
    targets.extend(Path("/data/tenants").glob("*/intelligence/models"))
    targets.extend(Path("/data/tenants").glob("*/intelligence/runtime"))
    targets.extend(Path("/data/tenants").glob("*/intelligence/downloads"))

    removed: list[str] = []
    for target in targets:
        if target.exists():
            _remove_tree(target)
            removed.append(str(target))

    if removed:
        app.logger.warning(
            "Pruning AI locale persistente su runtime cloud-hosted: %s",
            ", ".join(removed),
        )


def apply_hosted_local_ai_safety_overrides(app: Flask, cfg: dict | None = None) -> None:
    if not is_managed_cloud_runtime():
        return

    root = _ephemeral_local_ai_root()
    db_path = root / "local_ai.db"
    models_dir = root / "models"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    if "PCT_LOCAL_AI_DB" not in os.environ:
        app.config["LOCAL_AI_DB"] = str(db_path)
    if "PCT_LOCAL_AI_MODELS_DIR" not in os.environ:
        app.config["LOCAL_AI_MODELS_DIR"] = str(models_dir)
    if "PCT_LOCAL_AI_AUTO_BOOTSTRAP" not in os.environ:
        app.config["LOCAL_AI_AUTO_BOOTSTRAP"] = False

    prune_hosted_local_ai_persistent_artifacts(app)
