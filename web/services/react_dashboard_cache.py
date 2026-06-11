"""Cache breve per il payload della Panoramica React."""

from __future__ import annotations

from copy import deepcopy
from threading import Event, RLock
from time import monotonic
from typing import Any, Callable

DASHBOARD_CACHE_TTL_SECONDS = 60.0
_LOCK = RLock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_IN_FLIGHT: dict[str, Event] = {}


def _cached_payload_if_fresh(key: str, now: float) -> dict[str, Any] | None:
    cached = _CACHE.get(key)
    if cached and cached[0] > now:
        return deepcopy(cached[1])
    return None


def get_dashboard_payload_cached(
    cache_key: str,
    builder: Callable[[], dict[str, Any]],
    *,
    refresh: bool = False,
    ttl_seconds: float = DASHBOARD_CACHE_TTL_SECONDS,
) -> tuple[dict[str, Any], bool]:
    """Restituisce payload e flag cache-hit per evitare ricalcoli ravvicinati."""
    now = monotonic()
    key = str(cache_key or "default")
    if not refresh:
        with _LOCK:
            cached_payload = _cached_payload_if_fresh(key, now)
            if cached_payload is not None:
                return cached_payload, True

    waiter: Event | None = None
    while True:
        with _LOCK:
            if not refresh:
                cached_payload = _cached_payload_if_fresh(key, monotonic())
                if cached_payload is not None:
                    return cached_payload, True
            waiter = _IN_FLIGHT.get(key)
            if waiter is None:
                waiter = Event()
                _IN_FLIGHT[key] = waiter
                break

        waiter.wait(timeout=max(1.0, min(float(ttl_seconds or DASHBOARD_CACHE_TTL_SECONDS), 30.0)))
        refresh = False

    try:
        payload = builder()
    except Exception:
        with _LOCK:
            active = _IN_FLIGHT.pop(key, None)
            if active is not None:
                active.set()
        raise

    with _LOCK:
        now = monotonic()
        # Spurgo delle voci scadute: con chiavi per utente/giorno la mappa
        # crescerebbe lentamente ma senza limite nel processo.
        for stale_key in [existing for existing, (expires_at, _) in _CACHE.items() if expires_at <= now]:
            _CACHE.pop(stale_key, None)
        _CACHE[key] = (now + max(1.0, float(ttl_seconds or DASHBOARD_CACHE_TTL_SECONDS)), deepcopy(payload))
        active = _IN_FLIGHT.pop(key, None)
        if active is not None:
            active.set()
    return payload, False


def clear_dashboard_payload_cache() -> None:
    """Svuota la cache della Panoramica React nei test e nei refresh forzati."""
    with _LOCK:
        _CACHE.clear()


def invalidate_dashboard_payload_cache(prefix: str) -> None:
    """Invalida le voci con chiave che inizia per `prefix` (es. dopo una scrittura)."""
    cleaned = str(prefix or "")
    if not cleaned:
        return
    with _LOCK:
        for key in [item for item in _CACHE if item.startswith(cleaned)]:
            _CACHE.pop(key, None)
