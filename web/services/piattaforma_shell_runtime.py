"""Pagina del pannello di piattaforma servita dall'applicazione React.

Il pannello del superamministratore non usa la cornice dello studio (menu dei
moduli, barra con notifiche e scadenze dello studio): monta un'applicazione
React propria (`PiattaformaApp`) in una pagina minima. Le viste storiche
restano raggiungibili con `?_legacy=1` finché non si eliminano.
"""

from __future__ import annotations

from flask import render_template, request

VALORI_LEGACY = {"1", "true", "si", "yes", "on"}


def vista_classica_richiesta() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in VALORI_LEGACY


def render_piattaforma_shell(pagina: str, titolo: str, parametri: dict[str, str] | None = None):
    """Pagina React del pannello. `parametri` sono le parti dell'indirizzo (es. lo
    studio di `/admin/studi/<slug>`): l'applicazione li passa ai dati e alle azioni."""
    from web.blueprints.react_shell import _vite_entry

    return render_template(
        "piattaforma_shell.html",
        react_assets=_vite_entry(request.path),
        pagina=pagina,
        titolo=titolo,
        parametri=dict(parametri or {}),
    )


__all__ = ["render_piattaforma_shell", "vista_classica_richiesta"]
