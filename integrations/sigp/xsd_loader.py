"""Loader degli XSD ufficiali SIGP."""

from __future__ import annotations

from pathlib import Path

from .registry import SigpSchemaVersion, get_active_sigp_schema


def get_sigp_main_xsd_path(schema: SigpSchemaVersion | None = None) -> Path:
    active = schema or get_active_sigp_schema()
    return active.root_dir / active.main_xsd


def require_sigp_main_xsd_path(schema: SigpSchemaVersion | None = None) -> Path:
    xsd_path = get_sigp_main_xsd_path(schema)
    if not xsd_path.exists():
        raise FileNotFoundError(
            f"Schema XSD SIGP non trovato: {xsd_path}. "
            "Scaricare gli XSD ufficiali dal PST e aggiornare il registry se il nome principale cambia."
        )
    return xsd_path


def sigp_schema_status() -> dict:
    schema = get_active_sigp_schema()
    xsd_path = get_sigp_main_xsd_path(schema)
    return {
        "version": schema.version,
        "label": schema.label,
        "main_xsd": schema.main_xsd,
        "root_dir": str(schema.root_dir),
        "xsd_path": str(xsd_path),
        "available": xsd_path.exists(),
        "active": schema.active,
        "fonte": schema.fonte,
        "data_pubblicazione": schema.data_pubblicazione,
    }
