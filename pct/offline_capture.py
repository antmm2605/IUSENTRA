"""Contesto interno di cattura per i repository abilitati alla replica.

Il runtime deve impostarlo solo dopo verifica della configurazione del nodo,
tenant e utente. Non ricavarlo da intestazioni o campi della richiesta.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from collections.abc import Callable

from pct.offline_change_log import append_change
from pct.offline_replication import _identifier, _execute


@dataclass(frozen=True)
class CaptureContext:
    tenant: str
    actor: str
    device: str
    domains: frozenset[str]


_context: ContextVar[CaptureContext | None] = ContextVar("offline_capture", default=None)


def prepare_node_schema(conn):
    """Migrazione esplicita: non associa o abilita alcuno studio."""
    _execute(conn, """CREATE TABLE IF NOT EXISTS offline_node_owner (
        singleton INTEGER PRIMARY KEY CHECK (singleton=1),
        tenant_id TEXT NOT NULL, device_id TEXT NOT NULL)""")


def bind_node(conn, *, tenant: str, device: str):
    """Associazione immutabile del database locale dopo autorizzazione online.

    Un database esistente non può essere riassegnato a un altro studio o PC.
    Il chiamante completa bootstrap e verifiche prima di abilitare il runtime.
    """
    _identifier(tenant)
    _identifier(device)
    _execute(conn, """INSERT INTO offline_node_owner(singleton,tenant_id,device_id)
        VALUES (1,?,?) ON CONFLICT (singleton) DO NOTHING""", (tenant, device))
    row = _execute(conn, "SELECT tenant_id,device_id FROM offline_node_owner WHERE singleton=1").fetchone()
    if row is None or (row[0], row[1]) != (tenant, device):
        raise PermissionError("Archivio già associato a un altro studio o PC.")


@contextmanager
def capture_writes(context: CaptureContext):
    for value in (context.tenant, context.actor, context.device, *context.domains):
        _identifier(value)
    token = _context.set(context)
    try:
        yield
    finally:
        _context.reset(token)


def capture_callback(domain: str, changes: dict[str, tuple[dict | None, dict | None]] | Callable):
    """Restituisce un hook SQL per le sole righe realmente modificate.

    Gli ID vengono assegnati prima di entrare nel ciclo di retry del backend.
    Nessuno schema è creato dal comando: l'associazione del nodo deve aver
    completato la migrazione esplicita prima di abilitare la cattura.
    """
    context = _context.get()
    if context is None:
        return None
    if domain not in context.domains:
        raise RuntimeError("Salvataggio non coperto dagli adapter di sincronizzazione del nodo.")
    # Copia immutabile dei valori del comando: successivi cambi di oggetti
    # Python non possono alterare il contenuto del retry.
    values = changes() if callable(changes) else changes
    snapshot = json.loads(json.dumps(values, sort_keys=True, ensure_ascii=False, allow_nan=False))
    operation_ids = {key: uuid.uuid4().hex for key in snapshot}

    def record(conn):
        owner = _execute(conn, "SELECT tenant_id,device_id FROM offline_node_owner WHERE singleton=1").fetchone()
        if owner is None or (owner[0], owner[1]) != (context.tenant, context.device):
            raise PermissionError("Contesto di replica discordante dal proprietario dell'archivio.")
        for key, (before, after) in snapshot.items():
            if before == after:
                continue
            base = hashlib.sha256(json.dumps(before, sort_keys=True, separators=(",", ":"),
                                            ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            append_change(conn, tenant=context.tenant, operation_id=operation_ids[key],
                          domain=domain, resource_id=key, actor=context.actor,
                          source_device=context.device, base_revision=base,
                          content={"before": before, "after": after}, allowed_domains=context.domains)

    return record
