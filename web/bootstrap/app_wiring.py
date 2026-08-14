"""Wiring centrale dei moduli Flask estratto da web.app."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask

from web.bootstrap.core_surface_wiring import register_core_surfaces
from web.bootstrap.fascicoli_surface_wiring import register_fascicoli_surfaces
from web.bootstrap.register_blueprints import register_blueprints
from web.bootstrap.react_route_gate import register_react_route_gate
from web.bootstrap.studio_operations_wiring import register_studio_operations
from web.bootstrap.telematico_surface_wiring import register_telematico_surfaces
from web.services.support_runtime import register_support_websocket


def register_app_wiring(
    app: Flask,
    *,
    app_version: str,
    core: dict[str, Any],
    fascicoli: dict[str, Any],
    telematico: dict[str, Any],
    pdp_penale: dict[str, Any],
    ocr_runtime: Any,
    get_local_ai_service: Callable[[], Any],
) -> None:
    """Registra superfici verticali, blueprint modulari e wiring template."""

    register_core_surfaces(
        app,
        app_version=app_version,
        core=core,
        fascicoli=fascicoli,
        ocr_runtime=ocr_runtime,
        get_local_ai_service=get_local_ai_service,
    )
    register_fascicoli_surfaces(
        app,
        core=core,
        fascicoli=fascicoli,
        telematico=telematico,
        pdp_penale=pdp_penale,
        ocr_runtime=ocr_runtime,
    )
    register_telematico_surfaces(
        app,
        core=core,
        fascicoli=fascicoli,
        telematico=telematico,
        pdp_penale=pdp_penale,
    )
    register_studio_operations(app, core)
    register_blueprints(app)
    register_react_route_gate(app)
    register_support_websocket(app)
