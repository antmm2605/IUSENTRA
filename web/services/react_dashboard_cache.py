"""Cache breve per il payload della Panoramica React."""

from __future__ import annotations

from copy import deepcopy
from threading import Event, RLock
from time import monotonic
from time import time as wall_time
from typing import Any, Callable

from web.services.react_dashboard_shared_cache import (
    DASHBOARD_STALE_MAX_SECONDS,
    invalidate_shared_dashboards,
    read_shared_dashboard,
    shared_invalidated_at,
    write_shared_dashboard,
)

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
    invalidate_shared_dashboards()


def invalidate_dashboard_payload_cache(prefix: str) -> None:
    """Invalida le voci con chiave che inizia per `prefix` (es. dopo una scrittura)."""
    cleaned = str(prefix or "")
    if not cleaned:
        return
    with _LOCK:
        for key in [item for item in _CACHE if item.startswith(cleaned)]:
            _CACHE.pop(key, None)
    invalidate_shared_dashboards()


def get_dashboard_payload_swr(
    cache_key: str,
    stable_key: str,
    builder: Callable[[], dict[str, Any]],
    *,
    day: str,
    refresh: bool = False,
    allow_stale: bool = True,
    ttl_seconds: float = DASHBOARD_CACHE_TTL_SECONDS,
    stale_max_seconds: float = DASHBOARD_STALE_MAX_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Quadro della Panoramica con ricaduta sull'ultimo quadro valido dell'utente.

    Ordine: cache del worker ancora fresca → quadro fresco costruito da un altro
    worker → (se ammesso) ultimo quadro valido dello stesso giorno, dichiarato
    ``stale`` perché il client lo riallinei subito → ricalcolo completo.
    """

    meta: dict[str, Any] = {"hit": False, "stale": False, "shared": False, "age_seconds": 0}
    if not refresh:
        with _LOCK:
            cached_payload = _cached_payload_if_fresh(str(cache_key or "default"), monotonic())
        if cached_payload is not None:
            meta["hit"] = True
            return cached_payload, meta

        entry = read_shared_dashboard(stable_key)
        if entry is not None:
            try:
                stored_at = float(entry.get("stored_at") or 0.0)
            except (TypeError, ValueError):
                stored_at = 0.0
            age = max(0.0, wall_time() - stored_at)
            same_day = str(entry.get("day") or "") == str(day)
            invalidated = shared_invalidated_at() >= stored_at
            if (
                same_day
                and not invalidated
                and str(entry.get("cache_key") or "") == str(cache_key)
                and age <= float(ttl_seconds or DASHBOARD_CACHE_TTL_SECONDS)
            ):
                payload = dict(entry["payload"])
                with _LOCK:
                    _CACHE[str(cache_key or "default")] = (
                        monotonic() + max(1.0, float(ttl_seconds) - age),
                        deepcopy(payload),
                    )
                meta.update({"hit": True, "shared": True, "age_seconds": int(age)})
                return payload, meta
            # Dopo una scrittura esplicita (cache invalidata) si ricalcola: il
            # quadro precedente non va mostrato nemmeno come «in aggiornamento».
            if allow_stale and same_day and not invalidated and age <= float(stale_max_seconds):
                meta.update({"hit": True, "stale": True, "shared": True, "age_seconds": int(age)})
                return dict(entry["payload"]), meta

    payload, cache_hit = get_dashboard_payload_cached(cache_key, builder, refresh=refresh, ttl_seconds=ttl_seconds)
    meta["hit"] = bool(cache_hit)
    if not cache_hit and str(payload.get("status") or "") != "errore":
        write_shared_dashboard(stable_key, cache_key, payload, day)
    return payload, meta
