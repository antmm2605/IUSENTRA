"""Consultazione del repository posta senza costruire o caricare il gestore MIME."""
from contextlib import contextmanager
from pathlib import Path

from pct.email_mailbox_repository import EmailMailboxRepository
from web.services.email_storage_runtime import _context_for_path
from web.services.studio_readonly import request_studio_reader, worker_studio_writer


@contextmanager
def _mailbox_connection(db_path, *, expected_tenant: str, writable=False):
    path = Path(db_path).resolve()
    owner, root = _context_for_path(path)
    kind = {'casella.json': 'pec', 'ordinaria.json': 'ordinary'}.get(path.name)
    if kind is None or path.parent != root / 'email':
        raise ValueError('Percorso della casella non riconosciuto.')
    tenant_key = owner.slug if owner is not None else 'single-tenant'
    allowed = {tenant_key}
    if owner is not None:
        allowed.add(str(owner.id))
    if expected_tenant and expected_tenant not in allowed:
        raise PermissionError('La casella richiesta non appartiene allo studio corrente.')
    connection = worker_studio_writer if writable else request_studio_reader
    with connection(str(path)) as backend:
        repository = EmailMailboxRepository(backend, tenant_key, kind)
        repository._assert_initialized()
        yield repository


@contextmanager
def mailbox_reader(db_path, *, expected_tenant: str):
    with _mailbox_connection(db_path, expected_tenant=expected_tenant) as repository:
        yield repository


@contextmanager
def mailbox_projection_worker(db_path, *, expected_tenant: str):
    with _mailbox_connection(db_path, expected_tenant=expected_tenant, writable=True) as repository:
        yield repository
