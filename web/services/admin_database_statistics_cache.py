"""Bounded cache of the /admin/database statistics, invalidated by file changes.

Only counts and file metadata are retained, never document contents. Every
entry is keyed by the identity (inode, size, mtime, ctime) of the files it was
computed from, SQLite WAL included: any write changes the key, so a reused
value always describes the files as they are now. ADM-29: the SQL table counts
and the audit usage report follow the same rule instead of being recomputed on
every page open; errors are never retained.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from threading import Lock
from os import getenv
from time import monotonic

_cache: OrderedDict[tuple, tuple[tuple, float, dict]] = OrderedDict()
_lock = Lock()
# The signature already proves the files did not change; the TTL only bounds
# how long an entry may live in a worker.
_TTL_SECONDS = float(getenv("IUSENTRA_ADMIN_DATABASE_STATS_TTL_SECONDS") or 600)


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
            if entry and entry[0] == signature and monotonic() - entry[1] < _TTL_SECONDS:
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


def _file_signature(*paths):
    signature = []
    for value in paths:
        if not value:
            continue
        path = Path(value).resolve()
        for current in (path, Path(str(path) + "-wal")) if path.suffix in {".db", ".sqlite", ".sqlite3"} else (path,):
            try:
                stat = current.stat()
                stamp = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            except FileNotFoundError:
                stamp = None
            except OSError:
                return None
            signature.append((str(current), stamp))
    return tuple(signature)


def _cached(kind, paths, compute, *, keep):
    signature = _file_signature(*paths)
    if signature is not None and any(stamp is None for path, stamp in signature if not path.endswith("-wal")):
        # A missing file proves nothing: compute it live, never reuse.
        signature = None
    identity = (kind, tuple(str(path) for path in paths if path))
    if signature is not None:
        with _lock:
            entry = _cache.get(identity)
            if entry and entry[0] == signature and monotonic() - entry[1] < _TTL_SECONDS:
                _cache.move_to_end(identity)
                return deepcopy(entry[2])
            _cache.pop(identity, None)
    result = compute()
    if signature is not None and keep(result) and signature == _file_signature(*paths):
        with _lock:
            _cache[identity] = (signature, monotonic(), deepcopy(result))
            _cache.move_to_end(identity)
            while len(_cache) > 16:
                _cache.popitem(last=False)
    return result


def usage_statistics(database):
    """Audit usage report, recomputed only when the audit file changes."""
    paths = getattr(database, "percorsi", None)
    audit_path = paths.get("audit") if isinstance(paths, dict) else None
    if not audit_path:
        return database.analisi_uso()
    return _cached("usage", (audit_path,), database.analisi_uso,
                   keep=lambda result: isinstance(result, dict) and not result.get("errore"))


def sqlite_statistics(database, sqlite_path):
    """Table counts of a SQLite file, recomputed only when the file or its WAL changes."""
    if not sqlite_path:
        return database.statistiche_sqlite(sqlite_path)
    return _cached("sqlite", (sqlite_path,), lambda: database.statistiche_sqlite(sqlite_path),
                   keep=lambda result: isinstance(result, dict) and result.get("esiste")
                   and not result.get("errore") and not result.get("errori_tabelle"))
