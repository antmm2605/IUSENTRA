"""Wiring delle superfici operative di studio: CTU e prima nota.

Modulo separato da ``core_surface_wiring`` per mantenere i moduli di wiring
entro il limite di governabilita' (250 righe).
"""

from __future__ import annotations

from typing import Any

from flask import Flask

from web.bootstrap.ctu_routes import register_ctu_routes
from web.bootstrap.prima_nota_routes import register_prima_nota_routes


def register_studio_operations(app: Flask, core: dict[str, Any]) -> None:
    register_ctu_routes(app, core)
    register_prima_nota_routes(app, core)
