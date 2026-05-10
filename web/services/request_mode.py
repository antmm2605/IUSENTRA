from __future__ import annotations

from flask import request


def richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def richiede_json() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in (
        request.headers.get("Accept") or ""
    )
