"""Catalogo unificato STRICT per ogni Template Atto.

Tutti i consumer devono passare da questo modulo per ottenere capability,
prefill, controlli Cartabia, deposito e timbro studio. Il catalogo e'
metadata-only: non risolve dati cliente/fascicolo in massa.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any, Iterable

from pct.template_atti_inventory import (
    build_template_inventory,
    template_inventory_stats,
)
from pct.template_cartabia_rules import ensure_cartabia_metadata, verifica_cartabia_template


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _key(value: Any) -> str:
    return _clean(value).upper()


def _catalog_index() -> dict[str, dict[str, Any]]:
    from pct.template_catalog_service import build_template_catalog_items

    index: dict[str, dict[str, Any]] = {}
    for item in build_template_catalog_items():
        code = _key(item.get("codice") or item.get("id") or item.get("code"))
        if code and code not in index:
            index[code] = dict(item)
        compiler = _key(item.get("link_compilatore_code"))
        if compiler and compiler not in index:
            index[compiler] = dict(item)
    return index


def attach_timbro_capability(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    # Il timbro e' centralizzato nel renderer: il template non deve essere
    # modificato manualmente per supportarlo.
    enriched["supports_timbro"] = True
    enriched["timbro_policy"] = {
        "posizione": "top_left",
        "allineamento": "left",
        "default": "prima_pagina",
        "legacy_header_policy": "replace_legacy_header",
    }
    return enriched


def attach_prefill_capability(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    bindings = enriched.get("prefill_bindings") or {}
    required = enriched.get("required_prefill_fields") or enriched.get("dati_obbligatori") or []
    enriched["supports_prefill"] = bool(bindings)
    enriched["prefill_required_fields"] = list(dict.fromkeys(required))
    enriched["prefill_binding_count"] = len(bindings) if isinstance(bindings, dict) else 0
    return enriched


def attach_cartabia_capability(item: dict[str, Any]) -> dict[str, Any]:
    enriched = ensure_cartabia_metadata(item)
    verifica = verifica_cartabia_template(enriched)
    enriched["supports_cartabia_checks"] = bool(enriched.get("cartabia_profile") and enriched.get("processo_area"))
    enriched["cartabia_verifica"] = verifica
    enriched["source_evidence_ids"] = list(enriched.get("source_evidence_ids") or [])
    if not enriched["source_evidence_ids"]:
        enriched["richiede_verifica_avvocato"] = True
        enriched["stato_conformita"] = "cartabia_review_required"
    return enriched


def attach_deposit_capability(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    depositabile = bool(enriched.get("depositabile"))
    controls = enriched.get("controlli_deposito") or enriched.get("controlli_conformita_dettaglio") or []
    enriched["supports_deposit_checks"] = (not depositabile) or bool(controls)
    enriched["deposit_check_count"] = len(controls) if isinstance(controls, list) else 0
    return enriched


def ensure_template_capabilities(item: dict[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(item)
    enriched = attach_cartabia_capability(enriched)
    enriched = attach_prefill_capability(enriched)
    enriched = attach_timbro_capability(enriched)
    enriched = attach_deposit_capability(enriched)

    compiler_code = _clean(
        enriched.get("link_compilatore_code")
        or enriched.get("fallback_compilatore_code")
        or enriched.get("code")
        or enriched.get("codice")
    )
    enriched["supports_preview"] = bool(enriched.get("has_renderer") or compiler_code or enriched.get("corpo"))
    enriched["supports_render"] = bool(enriched.get("has_renderer") or compiler_code or enriched.get("corpo"))
    enriched["supports_compiler"] = bool(compiler_code)
    enriched["link_compilatore_code"] = _clean(enriched.get("link_compilatore_code") or compiler_code)
    enriched["fallback_compilatore_code"] = _clean(enriched.get("fallback_compilatore_code") or compiler_code)

    missing: list[str] = []
    for field, label in (
        ("supports_timbro", "timbro"),
        ("supports_prefill", "prefill"),
        ("supports_cartabia_checks", "controlli_cartabia"),
        ("supports_deposit_checks", "controlli_deposito"),
        ("supports_preview", "anteprima"),
        ("supports_render", "render"),
        ("supports_compiler", "compilatore"),
    ):
        if not enriched.get(field):
            missing.append(label)
    if not enriched.get("source_evidence_ids"):
        missing.append("fonti_normative")
    enriched["missing_capabilities"] = list(dict.fromkeys(missing))
    if missing and enriched.get("stato_conformita") == "cartabia_ready":
        enriched["stato_conformita"] = "cartabia_review_required"
    return enriched


@lru_cache(maxsize=4)
def _cached_unified_catalog() -> tuple[dict[str, Any], ...]:
    records = build_template_inventory()
    catalog_index = _catalog_index()
    unified: list[dict[str, Any]] = []
    for record in records:
        code = _key(record.get("codice"))
        base = dict(record)
        if code in catalog_index:
            catalog_item = deepcopy(catalog_index[code])
            catalog_item.update(base)
            base = catalog_item
        unified.append(ensure_template_capabilities(base))
    return tuple(unified)


def build_unified_template_catalog(*, refresh: bool = False) -> list[dict[str, Any]]:
    if refresh:
        _cached_unified_catalog.cache_clear()
    return [dict(item) for item in _cached_unified_catalog()]


def iter_all_templates(*, refresh: bool = False) -> Iterable[dict[str, Any]]:
    yield from build_unified_template_catalog(refresh=refresh)


def get_unified_template_item(codice: str, *, refresh: bool = False) -> dict[str, Any] | None:
    requested = _key(codice)
    for item in iter_all_templates(refresh=refresh):
        codes = {
            _key(item.get("codice")),
            _key(item.get("original_id")),
            _key(item.get("slug")),
            _key(item.get("link_compilatore_code")),
            _key(item.get("fallback_compilatore_code")),
        }
        if requested in codes:
            return item
    return None


def get_template_source_breakdown(*, refresh: bool = False) -> dict[str, Any]:
    catalog = build_unified_template_catalog(refresh=refresh)
    return template_inventory_stats(catalog)


def invalidate_unified_template_catalog_cache() -> None:
    _cached_unified_catalog.cache_clear()


__all__ = [
    "attach_cartabia_capability",
    "attach_deposit_capability",
    "attach_prefill_capability",
    "attach_timbro_capability",
    "build_unified_template_catalog",
    "ensure_template_capabilities",
    "get_template_source_breakdown",
    "get_unified_template_item",
    "invalidate_unified_template_catalog_cache",
    "iter_all_templates",
]
