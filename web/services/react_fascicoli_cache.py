"""Shared cache invalidation helpers for the React fascicoli list."""

from __future__ import annotations


def clear_react_fascicoli_list_cache() -> None:
    try:
        from web.blueprints.api_v1_react import clear_react_fascicoli_list_payload_cache

        clear_react_fascicoli_list_payload_cache()
    except Exception:
        return
