"""Bounded cache of mirror statistics, invalidated by actual file changes.

Only counts and file metadata are retained, never document contents. Active
SQL counts and usage reports always remain outside this cache.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from threading import Lock
from time import monotonic

_cache: OrderedDict[tuple, tuple[tuple, float, dict]] = OrderedDict()
_lock = Lock()


def _signature(database):
    paths = getattr(database, "percorsi", None)
    if not isinstance(paths, dict) or not paths:
        return None
    signature = []
    for name, value in sorted(paths.items()):
        path = Path(value).resolve()
        # SQLite readers may see committed changes in a WAL before checkpoint.
        for current in (path, Path(str(path) + "-wal")) if path.suffix in {".db", ".sqlite", ".sqlite3"} else (path,):
            try:
                stat = current.stat()
                stamp = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            except FileNotFoundError:
                stamp = None
            except OSError:
                return None
            signature.append((name, str(current), stamp))
    return tuple(signature)


def mirror_statistics(database):
    signature = _signature(database)
    if signature is not None:
        identity = tuple((name, path) for name, path, _ in signature)
        with _lock:
            entry = _cache.get(identity)
            if entry and entry[0] == signature and monotonic() - entry[1] < 30:
                _cache.move_to_end(identity)
                return deepcopy(entry[2])
            # A reverted fingerprint must never resurrect older statistics.
            _cache.pop(identity, None)
    result = database.statistiche()
    # Never retain errors or a result whose files changed during the read.
    if signature is not None and signature == _signature(database) and not any(
        row.get("stato") == "ERRORE" for row in result.get("moduli", [])
    ):
        with _lock:
            _cache[identity] = (signature, monotonic(), deepcopy(result))
            _cache.move_to_end(identity)
            while len(_cache) > 16:
                _cache.popitem(last=False)
    return result
