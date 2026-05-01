"""Rotte React del blocco finale Studio / Amministrazione."""

from __future__ import annotations

from flask import Flask


FINAL_REACT_ROUTES: dict[str, str] = {
    # Nessuna rotta finale viene registrata qui finche' la rispettiva pagina
    # React non replica integralmente form, POST, download, wizard e controlli
    # della superficie storica. Evita che una card React sostituisca moduli
    # operativi come Preventivi, Tariffario, Portali, Impostazioni o Admin.
}

FINAL_REACT_PERMISSIONS: dict[str, str] = {
}


def register_react_final_block_routes(app: Flask) -> None:
    """Non registra route card-only: si mantengono le superfici operative."""

    return None
