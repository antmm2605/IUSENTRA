"""Shell React progressiva per IUSENTRA.

La shell vive sotto ``/app-v2`` e governa le superfici già migrate mantenendo
separati i servizi Flask di scrittura, audit e validazione.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from flask import Blueprint, current_app, make_response, render_template

react_shell = Blueprint("react_shell", __name__)


def _react_static_dir() -> Path:
    return Path(current_app.static_folder or "web/static") / "react"


def _vite_entry() -> dict[str, Any]:
    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    if not manifest_path.exists():
        return {
            "ready": False,
            "js": [],
            "css": [],
            "error": "Build React non trovata. Esegui: cd frontend; npm ci; npm run build",
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        current_app.logger.exception("Manifest React non leggibile: %s", exc)
        return {
            "ready": False,
            "js": [],
            "css": [],
            "error": "Manifest React non leggibile. Rigenera la build frontend.",
        }

    entry = manifest.get("src/main.tsx") or next(
        (value for value in manifest.values() if value.get("isEntry")),
        None,
    )
    if not entry:
        return {
            "ready": False,
            "js": [],
            "css": [],
            "error": "Manifest Vite presente ma entry src/main.tsx non trovata.",
        }

    return {
        "ready": True,
        "js": [f"/static/react/{entry['file']}"],
        "css": [f"/static/react/{path}" for path in entry.get("css", [])],
        "error": "",
    }


@react_shell.get("/app-v2")
@react_shell.get("/app-v2/")
@react_shell.get("/app-v2/<path:spa_path>")
def react_app(spa_path: str = ""):
    """Serve la shell SPA React per le superfici migrate."""

    return render_react_shell_response(spa_path)


def render_react_shell_response(spa_path: str = "", *, bootstrap_texts: Iterable[Any] | None = None):
    """Render condiviso per le superfici migrate a React.

    Alcune route operative ufficiali, in GET, mostrano la shell React.
    I POST continuano a passare dai servizi Flask già auditati.
    """

    response = make_response(render_template(
        "react_shell.html",
        react_assets=_vite_entry(),
        react_spa_path=spa_path,
        react_bootstrap_texts=[str(item) for item in (bootstrap_texts or []) if str(item or "").strip()],
    ))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response
