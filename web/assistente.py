"""Compatibilita' legacy: il pannello admin vive in ``web.blueprints.admin``."""

from __future__ import annotations

from web.blueprints.admin import admin_bp, superadmin_required

__all__ = ["admin_bp", "superadmin_required"]
