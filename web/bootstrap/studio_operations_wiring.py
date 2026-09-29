"""Wiring delle superfici operative di studio: CTU, prima nota, contabilità,
antiriciclaggio del cliente e recupero crediti in serie.

Modulo separato da ``core_surface_wiring`` per mantenere i moduli di wiring
entro il limite di governabilita' (250 righe).
"""

from __future__ import annotations

from typing import Any

from flask import Flask

from web.bootstrap.antiriciclaggio_cliente_routes import register_antiriciclaggio_cliente_routes
from web.bootstrap.contabilita_routes import register_contabilita_routes
from web.bootstrap.ctu_routes import register_ctu_routes
from web.bootstrap.prima_nota_routes import register_prima_nota_routes
from web.bootstrap.recupero_crediti_routes import register_recupero_crediti_routes


def register_studio_operations(app: Flask, core: dict[str, Any]) -> None:
    register_ctu_routes(app, core)
    register_prima_nota_routes(app, core)
    register_contabilita_routes(app, core)
    register_antiriciclaggio_cliente_routes(app, core)
    register_recupero_crediti_routes(app, core)
