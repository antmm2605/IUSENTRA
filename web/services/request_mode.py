from __future__ import annotations

from flask import request


def richiede_json() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in (
        request.headers.get("Accept") or ""
    )
