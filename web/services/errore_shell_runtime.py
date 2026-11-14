"""Pagine d'errore dell'applicazione.

* 403 e 404: pagina minima che monta ``ErroreApp`` (React) fuori dalla cornice dello studio, per
  utenti collegati e non. Il testo essenziale è già nel documento, così resta leggibile anche
  se il bundle non parte.
* 500 e «Nessuna connessione»: HTML statico autonomo in ``web/static/errori/`` (niente Jinja,
  niente React), perché devono apparire anche quando il resto dell'applicazione è guasto.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app, g, make_response, render_template

COMPONENTE_ERRORE = "src/components/ErroreApp.tsx"

ERRORI_REACT: dict[int, dict[str, str]] = {
    403: {
        "titolo": "Accesso negato",
        "messaggio": "Non hai i permessi necessari per aprire questa pagina. Se ti servono, chiedili al titolare dello studio.",
    },
    404: {
        "titolo": "Pagina non trovata",
        "messaggio": "La pagina che cerchi non esiste o è stata spostata. Controlla l’indirizzo o riparti dalla panoramica.",
    },
}

_PAGINA_500_RISERVA = (
    "<!doctype html><html lang=\"it\"><head><meta charset=\"utf-8\"><title>Errore del server - IUSENTRA</title></head>"
    "<body><h1>Errore interno del server</h1><p>Riprova tra qualche istante.</p><p><a href=\"/\">Torna alla panoramica</a></p></body></html>"
)


def _cartella_errori() -> Path:
    return Path(current_app.root_path) / "static" / "errori"


def pagina_statica(nome: str) -> str:
    """Contenuto di una pagina statica d'errore; mai un'eccezione (serve proprio quando tutto è guasto)."""
    try:
        return (_cartella_errori() / nome).read_text(encoding="utf-8")
    except OSError:
        return _PAGINA_500_RISERVA


def risposta_statica(nome: str, status: int):
    response = make_response(pagina_statica(nome), status)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _asset_errore() -> dict[str, Any]:
    from web.blueprints.react_shell import _cached_route_assets, _load_manifest, _react_static_dir, _vite_entry

    assets = _vite_entry("/")
    if not assets.get("ready"):
        return assets
    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest and COMPONENTE_ERRORE in manifest:
        route = _cached_route_assets(manifest_path, manifest, COMPONENTE_ERRORE)
        assets["preload_js"] = route["js"]
        assets["page_css"] = route["css"]
    return assets


def render_errore_shell(codice: int):
    """Pagina React d'errore (403/404) con lo stato HTTP corretto."""
    testi = ERRORI_REACT[codice]
    autenticato = getattr(g, "utente_corrente", None) is not None
    try:
        html = render_template(
            "errore_shell.html",
            react_assets=_asset_errore(),
            codice=codice,
            titolo=testi["titolo"],
            messaggio=testi["messaggio"],
            autenticato=autenticato,
        )
    except Exception:  # una pagina d'errore non può fallire a sua volta
        current_app.logger.exception("Pagina d'errore %s non disponibile: risposta statica", codice)
        html = (
            f"<!doctype html><html lang=\"it\"><head><meta charset=\"utf-8\"><title>{testi['titolo']} - IUSENTRA</title></head>"
            f"<body><h1>{testi['titolo']}</h1><p>{testi['messaggio']}</p><p><a href=\"/\">Torna alla panoramica</a></p></body></html>"
        )
    response = make_response(html, codice)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


__all__ = ["ERRORI_REACT", "pagina_statica", "render_errore_shell", "risposta_statica"]
