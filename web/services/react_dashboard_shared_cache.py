"""Ultimo quadro valido della Panoramica condiviso tra i worker.

La cache breve di ``react_dashboard_cache`` vive nel singolo worker Gunicorn:
con più worker e dopo ogni riavvio la prima pagina dopo il login ricalcolava
l'intero quadro operativo. Qui l'ultimo quadro valido di ogni utente viene
conservato in Redis (ricaduta in memoria del worker se Redis non risponde), così
la Panoramica può mostrarlo subito, dichiarandone l'ora, mentre il quadro
aggiornato viene ricalcolato.

La chiave comprende studio e utente: un quadro non è mai servito a un altro
utente o a un altro studio.
"""

from __future__ import annotations

import hashlib
import os
import time
from threading import Lock
from typing import Any

from core.cache import CacheClient

# Conservazione della voce nell'archivio condiviso.
DASHBOARD_SHARED_RETENTION_SECONDS = 12 * 3600
# Età massima di un quadro mostrato in attesa del ricalcolo (sempre dello stesso giorno).
DASHBOARD_STALE_MAX_SECONDS = 8 * 3600

_KEY_PREFIX = "iusentra:panoramica:v1:"
_INVALIDATION_KEY = f"{_KEY_PREFIX}invalidata"
_CLIENT: CacheClient | None = None
_CLIENT_LOCK = Lock()


def _client() -> CacheClient | None:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            try:
                _CLIENT = CacheClient(
                    os.getenv("REDIS_URL", "") or os.getenv("PCT_REDIS_URL", ""),
                    default_ttl=int(DASHBOARD_SHARED_RETENTION_SECONDS),
                )
            except Exception:
                return None
    return _CLIENT


def _entry_key(stable_key: str) -> str:
    digest = hashlib.sha256(str(stable_key or "default").encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}{digest}"


def read_shared_dashboard(stable_key: str) -> dict[str, Any] | None:
    client = _client()
    if client is None:
        return None
    try:
        entry = client.get(_entry_key(stable_key))
    except Exception:
        return None
    if not isinstance(entry, dict) or not isinstance(entry.get("payload"), dict):
        return None
    return entry


def write_shared_dashboard(stable_key: str, cache_key: str, payload: dict[str, Any], day: str) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.set(
            _entry_key(stable_key),
            {"cache_key": str(cache_key), "stored_at": time.time(), "day": str(day), "payload": payload},
            ttl=int(DASHBOARD_SHARED_RETENTION_SECONDS),
        )
    except Exception:
        return


def invalidate_shared_dashboards() -> None:
    """Dopo una scrittura nessun worker considera più «fresco» un quadro precedente."""

    client = _client()
    if client is None:
        return
    try:
        client.set(_INVALIDATION_KEY, {"at": time.time()}, ttl=int(DASHBOARD_SHARED_RETENTION_SECONDS))
    except Exception:
        return


def shared_invalidated_at() -> float:
    client = _client()
    if client is None:
        return 0.0
    try:
        entry = client.get(_INVALIDATION_KEY)
    except Exception:
        return 0.0
    if isinstance(entry, dict):
        try:
            return float(entry.get("at") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def reset_shared_dashboard_client() -> None:
    """Solo per i test: ricrea il client alla prossima lettura."""

    global _CLIENT
    with _CLIENT_LOCK:
        _CLIENT = None
