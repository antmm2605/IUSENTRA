"""
pct/cache.py — Cache JSON per-processo con invalidazione via mtime.

Ogni worker Gunicorn mantiene un dizionario in memoria:
  { path_assoluto: (mtime_float, dati_python) }

Ad ogni lettura viene eseguita solo una syscall stat() per confrontare mtime.
Se il file non è cambiato dall'ultima lettura, i dati vengono restituiti dalla
cache senza aprire né parsare il file.

Quando si scrive con `cache.save()`, la cache viene aggiornata immediatamente
→ nessuna lettura stantia all'interno dello stesso processo/worker.

Thread-safety: le operazioni su dict Python sono atomiche sotto GIL; il lock
è presente per correttezza formale in presenza di worker gevent multi-greenlet.

Utilizzo tipico:

    from pct import cache as _cache

    # Lettura con fallback
    raw = _cache.load(self.db_path, default={})

    # Scrittura (aggiorna anche la cache)
    _cache.save(self.db_path, {k: v.to_dict() for k, v in self._items.items()})

    # Invalidazione esplicita (raro — di solito non necessaria)
    _cache.invalidate(self.db_path)
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

# ------------------------------------------------------------------ stato globale

_store: Dict[str, Tuple[float, Any]] = {}
_lock = threading.Lock()

# ------------------------------------------------------------------ API pubblica


def load(
    path: Union[str, Path],
    default: Any = None,
) -> Any:
    """
    Carica JSON da `path` usando la cache per-processo.

    - Se il file non esiste, restituisce `default` (o `{}` se None).
    - Se `mtime` non è cambiato rispetto all'ultima lettura, restituisce
      i dati già in memoria senza aprire il file.
    - In caso di errore di parsing, restituisce `default`.
    """
    p = Path(path)
    fallback = {} if default is None else default

    if not p.exists():
        return fallback

    try:
        mtime = p.stat().st_mtime
    except OSError:
        return fallback

    with _lock:
        entry = _store.get(str(p))
        if entry is not None and entry[0] == mtime:
            return entry[1]

    # Lettura fuori dal lock per non bloccare altri greenlet/thread
    try:
        with p.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return fallback

    with _lock:
        _store[str(p)] = (mtime, data)

    return data


def save(
    path: Union[str, Path],
    data: Any,
    indent: Optional[int] = 2,
) -> None:
    """
    Serializza `data` come JSON su `path` e aggiorna la cache.

    `indent=2` mantiene la leggibilità umana per i file piccoli/medi.
    Passa `indent=None` per file grandi dove le performance contano più
    della leggibilità (es. normative_tables, assistente_redazionale).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    p.write_text(text, encoding="utf-8")

    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = 0.0

    with _lock:
        _store[str(p)] = (mtime, data)


def invalidate(path: Union[str, Path]) -> None:
    """Rimuove un path dalla cache (forza rilettura al prossimo accesso)."""
    with _lock:
        _store.pop(str(Path(path)), None)


def clear() -> None:
    """Svuota l'intera cache (utile nei test)."""
    with _lock:
        _store.clear()


def stats() -> Dict[str, Any]:
    """Restituisce statistiche sulla cache (per debug/admin)."""
    with _lock:
        entries = list(_store.items())
    total_size = sum(
        len(json.dumps(v, default=str)) for _, (_, v) in entries
    )
    return {
        "entries": len(entries),
        "total_bytes_estimated": total_size,
        "paths": [k for k, _ in entries],
    }
