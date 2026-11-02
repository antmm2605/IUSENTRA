"""Chiavi di cache breve per payload React costosi (ADM-29).

Una pagina che rifà a ogni apertura lo stesso lavoro (cabina telematica,
gestione database) può riusare la risposta già costruita solo se nulla è
cambiato: la chiave unisce lo studio, l'utente autorizzato, le revisioni
operative dei domini letti e l'identità dei file SQLite coinvolti (database e
WAL). Qualsiasi scrittura cambia la chiave; un errore nel calcolarla disattiva
il riuso invece di rischiare un dato vecchio. Il contenuto sta nella
``ReactPayloadTTLCache`` del chiamante, che memorizza solo costruzioni riuscite.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from flask import current_app, g


def file_signature(paths: Iterable[str | Path]) -> tuple | None:
    """Identità dei file (inode, dimensione, mtime, ctime), WAL SQLite compreso."""
    signature: list[tuple] = []
    for value in paths:
        if not value:
            continue
        path = Path(value)
        candidates = [path]
        if path.suffix in {".db", ".sqlite", ".sqlite3"}:
            candidates.append(Path(str(path) + "-wal"))
        for current in candidates:
            try:
                stat = current.stat()
                signature.append((str(current), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
            except FileNotFoundError:
                signature.append((str(current), None))
            except OSError:
                return None
    return tuple(signature)


def revision_cache_key(name: str, *, domains: Iterable[str], files: Iterable[str | Path] = ()) -> tuple[Any, ...] | None:
    """Chiave di riuso o ``None`` se le revisioni non sono confermabili."""
    from web.services.operational_read_revision import read_authorized_revision_snapshot

    user = g.get("utente_corrente")
    if user is None:
        return None
    try:
        snapshot = read_authorized_revision_snapshot(user, requested_domains=set(domains))
        context = snapshot.get("context")
        revisions = snapshot.get("revisions")
        signature = file_signature(files)
    except Exception:
        current_app.logger.warning("Cache %s non riutilizzata: revisione non disponibile", name)
        return None
    if not context or revisions is None or signature is None:
        return None
    return (name, context, tuple(sorted(dict(revisions).items())), signature)
