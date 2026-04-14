"""Cache governabile per accelerare il contesto di Lex senza perdere precisione."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any, TypeVar


T = TypeVar("T")

_MAX_CACHE_ENTRIES = 256
_CACHE_LOCK = Lock()


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    value: Any


_CACHE: dict[str, _CacheEntry] = {}


def _stable_token(namespace: str, key_parts: Iterable[object]) -> str:
    raw = "|".join(str(part) for part in key_parts)
    digest = sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"{namespace}:{digest}"


def _prune_cache(now: float) -> None:
    expired = [key for key, entry in _CACHE.items() if entry.expires_at <= now]
    for key in expired:
        _CACHE.pop(key, None)

    if len(_CACHE) <= _MAX_CACHE_ENTRIES:
        return

    overflow = len(_CACHE) - _MAX_CACHE_ENTRIES
    oldest_keys = sorted(_CACHE, key=lambda key: _CACHE[key].expires_at)[:overflow]
    for key in oldest_keys:
        _CACHE.pop(key, None)


def clear_cached_values(namespace: str | None = None) -> None:
    """Utility di test e manutenzione per ripulire la cache Lex."""
    with _CACHE_LOCK:
        if not namespace:
            _CACHE.clear()
            return
        prefix = f"{namespace}:"
        for key in [item for item in _CACHE if item.startswith(prefix)]:
            _CACHE.pop(key, None)


def cached_compute(
    namespace: str,
    key_parts: Iterable[object],
    ttl_seconds: int,
    builder: Callable[[], T],
) -> T:
    """Restituisce un valore in cache con TTL breve e pruning automatico."""
    ttl = max(int(ttl_seconds or 0), 1)
    token = _stable_token(namespace, key_parts)
    now = monotonic()

    with _CACHE_LOCK:
        cached = _CACHE.get(token)
        if cached and cached.expires_at > now:
            return cached.value

    value = builder()

    with _CACHE_LOCK:
        _CACHE[token] = _CacheEntry(expires_at=now + ttl, value=value)
        _prune_cache(now)

    return value


def build_file_fingerprint(paths: Iterable[str]) -> str:
    """Produce una fingerprint stabile dei file che alimentano il contesto."""
    chunks: list[str] = []
    for raw_path in paths:
        path_str = str(raw_path or "").strip()
        if not path_str:
            continue
        path = Path(path_str)
        try:
            stat = path.stat()
            chunks.append(f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}")
        except FileNotFoundError:
            chunks.append(f"{path.resolve()}:missing")

    if not chunks:
        return "static"
    return sha1("\n".join(chunks).encode("utf-8"), usedforsecurity=False).hexdigest()


def question_signature(question: str, *, limit: int = 10) -> str:
    """Compatta una domanda in una firma breve riutilizzabile dalla cache."""
    normalized = " ".join(str(question or "").lower().replace("/", " ").replace("-", " ").split())
    if not normalized:
        return "__vuota__"

    terms: list[str] = []
    seen: set[str] = set()
    for raw in normalized.split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) >= limit:
            break

    if not terms:
        return normalized[:80]
    return "|".join(terms)
