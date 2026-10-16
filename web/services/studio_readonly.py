"""Connessioni consultive native, isolate dalle sessioni che salvano dati."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from flask import current_app, g, has_request_context

from pct.core_storage_backend import build_core_storage_backend
from pct.tenant import DbMode
from web.services.storage_runtime import get_request_storage_runtime
from web.services.tenant_isolation_runtime import assert_tenant_data_path


@contextmanager
def _request_studio_connection(anchor_path: str, *, readonly: bool):
    """Il chiamante applica RBAC; qui si preservano studio, backend e sola lettura.

    Non usa i singleton scrivibili e non prepara schemi o importa mirror. La
    connessione privata viene chiusa anche quando una selezione fallisce.
    """
    if not has_request_context():
        raise RuntimeError('Contesto della consultazione non disponibile.')
    multi = bool(current_app.config.get('MULTI_TENANT') or getattr(g, 'multi_tenant_enabled', False))
    tenant = getattr(g, 'tenant', None)
    if getattr(g, 'tenant_context_missing', False) or (multi and tenant is None):
        raise PermissionError('Contesto studio non disponibile per la consultazione.')
    profile = get_request_storage_runtime(anchor_path)
    if multi:
        assert_tenant_data_path(profile.studio_db_path, key='STUDIO_DB')
    if profile.external_sql_configured and profile.effective_mode != profile.selected_mode:
        raise RuntimeError('Archivio SQL configurato non disponibile: nessuna lettura da copie storiche.')
    if profile.effective_mode == DbMode.POSTGRESQL:
        config = getattr(tenant, 'database', None)
    elif profile.uses_sqlite:
        if not Path(profile.studio_db_path).is_file():
            raise RuntimeError('Archivio SQL non inizializzato: la consultazione non crea dati.')
        config = SimpleNamespace(mode=DbMode.SQLITE)
    else:
        raise RuntimeError('La consultazione richiede il catalogo SQL dello studio.')
    backend = build_core_storage_backend(config, studio_db_path=profile.studio_db_path, readonly=readonly, initialize_schema=False)
    if backend is None:
        raise RuntimeError('Archivio SQL dello studio non disponibile.')
    try:
        yield backend
    finally:
        backend.chiudi()


@contextmanager
def request_studio_reader(anchor_path: str):
    with _request_studio_connection(anchor_path, readonly=True) as backend:
        yield backend


@contextmanager
def worker_studio_writer(anchor_path: str):
    """Sessione privata per consegne interne; mai dal comando di consultazione."""
    with _request_studio_connection(anchor_path, readonly=False) as backend:
        yield backend


@contextmanager
def borrowed_studio_backend(database, anchor_path):
    """I servizi nativi annidati riusano la connessione consultiva già risolta."""
    from web.services.storage_runtime import runtime_backend_cache_key
    profile = get_request_storage_runtime(anchor_path)
    missing = object()
    previous = {name: getattr(g, name, missing) for name in ('_runtime_studio_db', '_runtime_studio_db_key')}
    g._runtime_studio_db = database
    g._runtime_studio_db_key = runtime_backend_cache_key(profile)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is missing:
                g.pop(name, None)
            else:
                setattr(g, name, value)
