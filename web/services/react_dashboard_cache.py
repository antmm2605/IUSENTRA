"""Cache breve per il payload della Panoramica React."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from time import monotonic
from typing import Any, Callable

_DEFAULT_TTL_SECONDS = 20.0
_LOCK = RLock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def get_dashboard_payload_cached(
    cache_key: str,
    builder: Callable[[], dict[str, Any]],
    *,
    refresh: bool = False,
    ttl_seconds: float = _DEFAULT_TTL_SECONDS,
) -> tuple[dict[str, Any], bool]:
    """Restituisce payload e flag cache-hit per evitare ricalcoli ravvicinati."""
    now = monotonic()
    key = str(cache_key or "default")
    if not refresh:
        with _LOCK:
            cached = _CACHE.get(key)
            if cached and cached[0] > now:
                return deepcopy(cached[1]), True

    payload = builder()
    with _LOCK:
        _CACHE[key] = (now + max(1.0, float(ttl_seconds or _DEFAULT_TTL_SECONDS)), deepcopy(payload))
    return payload, False


def clear_dashboard_payload_cache() -> None:
    """Svuota la cache della Panoramica React nei test e nei refresh forzati."""
    with _LOCK:
        _CACHE.clear()
