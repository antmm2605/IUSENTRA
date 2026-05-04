"""Bridge API/UI per Regia Operativa Fascicolo."""

from __future__ import annotations

from typing import Any, Callable

from pct.practice_engine.evaluator import build_regia_payload


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _all_conferimenti(preventivi_manager: Any) -> list[Any]:
    if hasattr(preventivi_manager, "tutti_conferimenti"):
        return list(preventivi_manager.tutti_conferimenti())
    return []


def build_react_practice_engine_payload(
    *,
    fascicolo_id: str,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_practice_engine: Callable[[], Any],
    actor: str = "",
    manual_code: str = "",
) -> dict[str, Any]:
    gf = get_fascicoli()
    fascicolo = _safe("fascicolo", lambda: gf.get(fascicolo_id), None)
    if not fascicolo:
        return {
            "source": "repository reale",
            "mock_fallback": False,
            "page_state": "non_trovato",
            "message": "Fascicolo non trovato.",
        }
    cliente = _safe("cliente", lambda: get_clienti().get(getattr(fascicolo, "id_cliente", "")), None)
    gp = get_preventivi()
    preventivi = _safe("preventivi", lambda: gp.tutti_preventivi(), [])
    conferimenti = _safe("conferimenti", lambda: _all_conferimenti(gp), [])
    parcelle = _safe("fatturazione", lambda: get_fatturazione().tutte(), [])
    return build_regia_payload(
        get_practice_engine(),
        fascicolo=fascicolo,
        cliente=cliente,
        preventivi=preventivi,
        conferimenti=conferimenti,
        parcelle=parcelle,
        fascicoli_manager=gf,
        actor=actor,
        manual_code=manual_code,
    )
