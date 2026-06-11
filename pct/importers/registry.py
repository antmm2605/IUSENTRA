"""Registro degli adapter di import del Migration Center."""

from __future__ import annotations

from .adapters.generic_csv import GenericCsvAdapter
from .base import ImportAdapter, ImportError_

_REGISTRY: dict[str, type] = {}


def register_adapter(adapter_cls: type) -> None:
    name = getattr(adapter_cls, "name", "")
    if not name:
        raise ImportError_("Adapter senza attributo 'name'.")
    _REGISTRY[str(name)] = adapter_cls


def get_adapter(name: str) -> ImportAdapter:
    adapter_cls = _REGISTRY.get(str(name or "").strip())
    if adapter_cls is None:
        raise ImportError_(f"Adapter di import sconosciuto: {name!r}.")
    return adapter_cls()


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


# Adapter disponibili da subito. I connettori gestionali (Cliens, Kleos, Netlex,
# EasyLex, Quadra, Studio Telematico) si registrano qui nei PR successivi.
register_adapter(GenericCsvAdapter)


__all__ = ["register_adapter", "get_adapter", "available_adapters"]
