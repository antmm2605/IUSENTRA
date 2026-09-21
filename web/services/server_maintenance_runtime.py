"""Condivide the storage measurement between web workers for five minutes."""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any

from flask import current_app, has_app_context
from web.services.server_maintenance_surface import (
    build_server_maintenance_surface, resolve_data_root,
    resolve_external_backup_dir, storage_scan_settings,
)

_TTL = 300
_LOCK = Lock()
_CACHE: dict[str, tuple[float, dict]] = {}


def build_cached_server_maintenance_surface(config: dict[str, Any] | None = None) -> dict:
    cfg = config if config is not None else (current_app.config if has_app_context() else {})
    scope = [str(resolve_data_root(cfg)), str(resolve_external_backup_dir(cfg)), storage_scan_settings(cfg)]
    key = "iusentra:storage-snapshot:v1:" + hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and monotonic() < cached[0]:
            return deepcopy(cached[1])
        redis_client = None
        try:
            import redis
            url = cfg.get("REDIS_URL") or os.getenv("REDIS_URL")
            if url:
                redis_client = redis.Redis.from_url(url, socket_connect_timeout=0.2, socket_timeout=0.3)
                raw = redis_client.get(key)
                if raw:
                    payload = json.loads(raw)
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(payload["snapshot"]["sampled_at"])).total_seconds()
                    if 0 <= age < _TTL:
                        _CACHE[key] = (monotonic() + _TTL - age, payload)
                        return deepcopy(payload)
        except (OSError, ValueError, KeyError, TypeError):
            redis_client = None
        except Exception as exc:
            if exc.__class__.__module__.startswith("redis"):
                redis_client = None
            else:
                raise
        payload = build_server_maintenance_surface(cfg)
        payload["snapshot"] = {"sampled_at": datetime.now(timezone.utc).isoformat(), "ttl_seconds": _TTL}
        _CACHE[key] = (monotonic() + _TTL, deepcopy(payload))
        if redis_client is not None:
            try:
                redis_client.setex(key, _TTL, json.dumps(payload))
            except Exception as exc:
                if not exc.__class__.__module__.startswith("redis"):
                    raise
        return payload
