"""La cache della Lettura del fascicolo, invalidabile per fascicolo.

La lettura completa attraversa documenti, PEC, agenda, presìdi e archivio. Sul
server ci sono più worker: una cache solo in memoria rende veloce un worker ma
lascia gli altri a ricalcolare lo stesso payload. Questa cache conserva i byte
JSON già serializzati anche su disco, dentro l'istanza dell'applicazione, così i
fascicoli già letti si aprono rapidamente e documenti/PEC invalidano comunque
la voce del fascicolo.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from flask import current_app, has_app_context

from web.services.react_payload_cache import ReactPayloadTTLCache


class LetturaPayloadCache:
    """Cache JSON condivisa tra worker per la lettura del fascicolo."""

    def __init__(self, *, ttl_seconds: float = 24 * 60 * 60.0, max_entries: int = 512) -> None:
        self.ttl_seconds = max(0.0, float(ttl_seconds or 0.0))
        self._memory = ReactPayloadTTLCache(ttl_seconds=ttl_seconds, max_entries=max_entries)

    @property
    def enabled(self) -> bool:
        return self.ttl_seconds > 0

    def _directory(self) -> Path | None:
        if not has_app_context():
            return None
        configured = str(current_app.config.get("LETTURA_FASCICOLO_CACHE_DIR") or "").strip()
        base = Path(configured) if configured else Path(current_app.instance_path) / "cache" / "lettura-fascicolo"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        return base

    def _name(self, key: tuple) -> str:
        raw = json.dumps(list(key), ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


    def _db_parts(self, key: tuple) -> tuple[str, str, str] | None:
        if len(key) != 3 or key[0] != "lettura":
            return None
        tenant_version = str(key[1] or "")
        tenant = tenant_version.split("@", 1)[0].strip() or "single-studio"
        fascicolo_id = str(key[2] or "").strip()
        cache_key = self._name(key)
        if not fascicolo_id:
            return None
        return tenant, fascicolo_id, cache_key

    def _db_get(self, key: tuple) -> bytes | None:
        parts = self._db_parts(key)
        if parts is None or not has_app_context():
            return None
        try:
            from web.services.registro_letture_runtime import registro_corrente

            payload = registro_corrente().payload_cache_get(*parts)
            return payload.encode("utf-8") if payload else None
        except Exception:
            return None

    def _db_set(self, key: tuple, payload: bytes) -> None:
        parts = self._db_parts(key)
        if parts is None or not has_app_context():
            return
        try:
            from web.services.registro_letture_runtime import registro_corrente

            expires = datetime.fromtimestamp(time.time() + self.ttl_seconds, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            registro_corrente().payload_cache_set(*parts, payload.decode("utf-8"), expires_at=expires)
        except Exception:
            return

    def _db_delete_key(self, key: tuple) -> None:
        parts = self._db_parts(key)
        if parts is None or not has_app_context():
            return
        try:
            from web.services.registro_letture_runtime import registro_corrente

            tenant, fascicolo_id, cache_key = parts
            registro_corrente().payload_cache_delete(tenant, fascicolo_id, cache_key=cache_key)
        except Exception:
            return

    def _db_delete_fascicolo_corrente(self, fascicolo_id: str) -> int:
        if not has_app_context():
            return 0
        try:
            from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

            return int(registro_corrente().payload_cache_delete(tenant_corrente(), str(fascicolo_id or "")))
        except Exception:
            return 0

    def _paths(self, key: tuple) -> tuple[Path, Path] | None:
        directory = self._directory()
        if directory is None:
            return None
        name = self._name(key)
        return directory / f"{name}.json", directory / f"{name}.meta.json"

    def get(self, key: tuple) -> bytes | None:
        if not self.enabled:
            return None
        cached = self._memory.get(key)
        if cached is not None:
            return cached
        db_payload = self._db_get(key)
        if db_payload is not None:
            self._memory.set(key, db_payload)
            return db_payload
        paths = self._paths(key)
        if paths is None:
            return None
        data_path, meta_path = paths
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if float(meta.get("expires_at") or 0) < time.time():
                self.invalidate(key)
                return None
            payload = data_path.read_bytes()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        self._memory.set(key, payload)
        self._db_set(key, payload)
        return payload

    def set(self, key: tuple, payload: bytes) -> None:
        self._memory.set(key, payload)
        if isinstance(payload, (bytes, bytearray)):
            self._db_set(key, bytes(payload))
        if not self.enabled or not isinstance(payload, (bytes, bytearray)):
            return
        paths = self._paths(key)
        if paths is None:
            return
        data_path, meta_path = paths
        token = f"{os.getpid()}-{time.time_ns()}"
        tmp_data = data_path.with_name(f".{data_path.name}.{token}.tmp")
        tmp_meta = meta_path.with_name(f".{meta_path.name}.{token}.tmp")
        meta = {"key": list(key), "expires_at": time.time() + self.ttl_seconds, "created_at": time.time()}
        try:
            tmp_data.write_bytes(bytes(payload))
            tmp_meta.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp_data, data_path)
            os.replace(tmp_meta, meta_path)
        except OSError:
            for tmp in (tmp_data, tmp_meta):
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    def clear(self) -> None:
        self._memory.clear()
        directory = self._directory()
        if directory is None:
            return
        for path in directory.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                pass

    def invalidate(self, key: tuple) -> None:
        self._memory.invalidate(key)
        self._db_delete_key(key)
        paths = self._paths(key)
        if paths is None:
            return
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def invalidate_where(self, predicate: Callable[[tuple], bool]) -> int:
        removed = self._memory.invalidate_where(predicate)
        directory = self._directory()
        if directory is None:
            return removed
        for meta_path in directory.glob("*.meta.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                key = tuple(meta.get("key") or ())
            except (OSError, TypeError, json.JSONDecodeError):
                continue
            if not predicate(key):
                continue
            data_path = directory / meta_path.name.replace(".meta.json", ".json")
            for path in (meta_path, data_path):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            removed += 1
        return removed

    def __len__(self) -> int:
        return len(self._memory)


LETTURA_CACHE = LetturaPayloadCache(ttl_seconds=24 * 60 * 60.0, max_entries=512)


def chiave_lettura(tenant_id: str, fascicolo_id: str) -> tuple:
    from pct.fascicolo_lettura import VERSIONE_LETTURA

    return ("lettura", f"{tenant_id or 'single-studio'}@{VERSIONE_LETTURA}", str(fascicolo_id or ""))


def invalida_lettura(fascicolo_id: str) -> int:
    """Invalida la lettura del fascicolo per qualunque studio: la chiave è per fascicolo."""
    target = str(fascicolo_id or "")
    if not target:
        return 0
    removed = LETTURA_CACHE.invalidate_where(lambda key: len(key) == 3 and key[0] == "lettura" and key[2] == target)
    removed += LETTURA_CACHE._db_delete_fascicolo_corrente(target)
    return removed


__all__ = ["LETTURA_CACHE", "chiave_lettura", "invalida_lettura"]
