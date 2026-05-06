"""Shell React progressiva per IUSENTRA.

La shell vive sotto ``/app-v2`` e governa le superfici già migrate mantenendo
separati i servizi Flask di scrittura, audit e validazione.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, url_for

react_shell = Blueprint("react_shell", __name__)


_LEGACY_FIRST_PREFIXES = (
    "/admin/osservabilita",
    "/applicazioni",
    "/checklist",
    "/compensi-forensi",
    "/database",
    "/deposito/checklist",
    "/giurisprudenza",
    "/guida/firma-digitale",
    "/impostazioni",
    "/impostazioni-studio",
    "/legal-intelligence",
    "/notifiche",
    "/notifiche-whatsapp",
    "/pat",
    "/pdp",
    "/polisweb",
    "/portali",
    "/redazione-atti",
    "/ricerca-legale",
    "/servizi-telematici",
    "/sigit",
    "/sigp",
    "/sigp-sync",
    "/sincronizzazione-calendari",
    "/strumenti-legali",
    "/strumenti-operativi",
    "/tariffario",
    "/telematico",
    "/template-atti",
    "/tribunali",
)


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

    La shell React resta sempre disponibile sotto ``/app-v2``. Fuori da
    ``/app-v2`` le route operative storiche non vengono piu' promosse
    implicitamente: questo evita che una card React sostituisca un wizard
    completo non ancora ricostruito con parita' reale.
    """

    if _deve_mantenere_vista_classica():
        query = request.args.to_dict(flat=True)
        query["_legacy"] = "1"
        return redirect(f"{request.path}?{urlencode(query)}", code=302)

    response = make_response(render_template(
        "react_shell.html",
        react_assets=_vite_entry(),
        react_spa_path=spa_path,
        react_bootstrap=_react_bootstrap_payload(),
        react_bootstrap_texts=[str(item) for item in (bootstrap_texts or []) if str(item or "").strip()],
    ))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def _deve_mantenere_vista_classica() -> bool:
    """Blocca promozioni React non validate fuori dalla shell progressiva."""

    path = (request.path or "").rstrip("/") or "/"
    if path == "/app-v2" or path.startswith("/app-v2/"):
        return False
    forced_react = (request.args.get("_react") or "").strip().lower()
    if forced_react in {"1", "true", "si", "yes", "on"}:
        return False
    enabled = current_app.config.get("REACT_PROMOTE_LEGACY_ROUTES", False)
    if enabled:
        return False
    lower = path.lower()
    if lower.startswith("/fascicoli/") and (
        "/wizard/" in lower
        or "/deposito/" in lower
        or "/penale/pdp" in lower
    ):
        return True
    if lower.startswith("/utenti/") and lower != "/utenti/nuovo":
        return True
    if lower.startswith("/profili/"):
        return True
    if lower.startswith("/backup/"):
        return True
    if lower.startswith("/sito-studio/") and lower not in {"/sito-studio/contatti"}:
        return True
    if lower.startswith("/studio/"):
        return True
    if lower.startswith("/amministrazione/"):
        return True
    if lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova":
        return True
    if lower.startswith("/incassi-pagamenti/"):
        return True
    if lower == "/impostazioni/pagamenti" or lower.startswith("/impostazioni/pagamenti/"):
        return True
    if lower == "/impostazioni" or lower.startswith("/impostazioni/"):
        return True
    if lower == "/impostazioni-studio" or lower.startswith("/impostazioni-studio/"):
        return True
    if lower == "/sincronizzazione-calendari" or lower.startswith("/sincronizzazione-calendari/"):
        return True
    if lower.startswith("/preventivi/") and lower not in {
        "/preventivi/nuovo",
        "/preventivi/conferimento/nuovo",
    }:
        return True
    if lower == "/compensi-forensi" or lower.startswith("/compensi-forensi/"):
        return True
    if lower == "/tariffario" or lower.startswith("/tariffario/"):
        return True
    return any(lower == prefix or lower.startswith(f"{prefix}/") for prefix in _LEGACY_FIRST_PREFIXES)


def _initials(value: str) -> str:
    parts = [part for part in str(value or "").replace(".", " ").split() if part]
    return "".join(part[0] for part in parts[:2]).upper()


def _react_bootstrap_payload() -> dict[str, Any]:
    """Dati di sessione reali da usare nella shell React."""

    utente = getattr(g, "utente_corrente", None)
    if not utente:
        return {"user": None, "actions": {}}

    ruolo = getattr(getattr(utente, "ruolo", ""), "value", getattr(utente, "ruolo", ""))
    nome = str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or "").strip()
    username = str(getattr(utente, "username", "") or "").strip()
    source = username or nome
    return {
        "user": {
            "id": str(getattr(utente, "id", "") or ""),
            "username": username,
            "displayName": nome,
            "role": str(ruolo or "").strip(),
            "initials": _initials(source),
        },
        "actions": {
            "profile": url_for("profilo"),
            "logout": url_for("logout"),
        },
    }
