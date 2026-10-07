"""Factory tenant-aware per il catalogo SQL della posta.

Non attivare i chiamanti finché ciascuna casella non ha una migrazione
verificata. I worker risolvono lo studio dal registry configurato, mai
inferendo PostgreSQL/SQLite dal solo nome del percorso.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from flask import current_app, g, has_app_context, has_request_context

from pct.core_storage_backend import build_core_storage_backend
from pct.storage import StudioDB
from pct.email_client import GestioneEmailRicevute
from pct.email_sql_client import GestioneEmailSQL
from pct.email_mailbox_repository import EmailMailboxRepository, KINDS, MailboxConflict, MailboxNotInitialized
from pct.tenant import StudioLegale
from web.services.storage_runtime import resolve_storage_runtime


def _registry_path():
    configured = current_app.config.get('TENANTS_REGISTRY') if has_app_context() else None
    return Path(configured or os.environ.get('PCT_TENANTS_REGISTRY') or './data/tenants.json').resolve()


def _tenant_root(tenant, registry):
    key = str(tenant.storage_key or tenant.slug).strip()
    if not key:
        raise RuntimeError('Identità dello studio non disponibile per la casella.')
    target = Path(key)
    if not target.is_absolute() and (target.name != key or key in {'.', '..'}):
        raise RuntimeError('Percorso studio non valido per la casella.')
    return target.resolve() if target.is_absolute() else (registry.parent / 'tenants' / key).resolve()


def _context_for_path(path):
    registry = _registry_path()
    tenant = getattr(g, 'tenant', None) if has_app_context() else None
    if tenant is not None:
        root = _tenant_root(tenant, registry)
        if path.parent != root / 'email':
            raise RuntimeError('La casella richiesta non appartiene allo studio corrente.')
        return tenant, root
    # Lettura puntuale del registro configurato: nessuna recovery, scansione
    # ricorsiva, creazione di studio o esposizione delle sue credenziali.
    if registry.is_file():
        entries = json.loads(registry.read_text(encoding='utf-8'))
        if not isinstance(entries, dict):
            raise RuntimeError('Registro degli studi non valido per la casella.')
        matches = []
        for data in entries.values():
            if not isinstance(data, dict):
                raise RuntimeError('Registro degli studi non valido per la casella.')
            candidate = StudioLegale.from_dict(data)
            root = _tenant_root(candidate, registry)
            if path.parent == root / 'email':
                matches.append((candidate, root))
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise RuntimeError('Più studi condividono il percorso della casella: accesso bloccato.')
    multi = has_app_context() and current_app.config.get('MULTI_TENANT')
    if multi or 'tenants' in path.parts:
        raise RuntimeError('Contesto studio non disponibile: accesso alla casella bloccato.')
    if has_request_context() and getattr(g, 'tenant_context_missing', False):
        raise RuntimeError('Contesto studio non disponibile: accesso alla casella bloccato.')
    return None, path.parent.parent


def _initialize_empty_sql_catalog(backend, tenant_key, kind, path, source_of_truth):
    # Solo un catalogo core SQL vuoto può avviare una nuova casella vuota.
    # Un catalogo storico con messaggi richiede la migrazione verificata;
    # il mirror non è mai importato né utilizzato come elenco operativo.
    count = backend.conn.execute(
        'SELECT COUNT(*) FROM moduli_json_records WHERE modulo=?', (KINDS[kind],),
    ).fetchone()[0]
    historical = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    # Il seed core storico dell'ordinaria è una lista vuota. È vuoto,
    # non una fonte da importare; qualsiasi lista popolata resta bloccata.
    empty_mirror = historical == {} or (kind == 'ordinary' and historical == [])
    if count or not empty_mirror:
        raise MailboxNotInitialized('Archivio della casella da riallineare con una migrazione verificata.')
    repository = EmailMailboxRepository(backend, tenant_key, kind, mirror_path=path)
    try:
        repository.initialize({}, source_of_truth=source_of_truth)
    except MailboxConflict:
        # Un'altra richiesta può aver inizializzato il medesimo SQL vuoto.
        # Rileggere solo il catalogo primario, mai sovrascriverlo o reimportarlo.
        repository.load(update_original=False)


def create_email_mailbox(db_path, *, actor_key=None, load_catalog=True):
    path = Path(db_path).resolve()
    tenant, root = _context_for_path(path)
    profile = resolve_storage_runtime(anchor_path=str(path), tenant=tenant)
    if profile.effective_mode == 'JSON':
        # Compatibilità esclusivamente per uno studio configurato JSON.
        if profile.selected_mode != 'JSON':
            raise RuntimeError('Archivio SQL della casella non disponibile.')
        return GestioneEmailRicevute(db_path=str(path))
    kind = {'casella.json': 'pec', 'ordinaria.json': 'ordinary'}.get(path.name)
    if kind is None or path.parent.name != 'email':
        raise ValueError('Percorso della casella non riconosciuto.')
    if profile.effective_mode == 'POSTGRESQL':
        backend = build_core_storage_backend(tenant.database, studio_db_path=profile.studio_db_path)
        if backend is None:
            raise RuntimeError('Archivio PostgreSQL della casella non disponibile.')
    elif profile.uses_sqlite:
        if Path(profile.studio_db_path).resolve() != root / 'studio.db':
            raise RuntimeError('Archivio SQL non coerente con lo studio della casella.')
        if not Path(profile.studio_db_path).is_file():
            raise RuntimeError('Archivio SQL della casella da inizializzare: nessuna lettura da copie storiche.')
        backend = StudioDB.get(profile.studio_db_path)
    else:
        raise RuntimeError('Modalità archivio della casella non disponibile.')
    user = getattr(g, 'utente_corrente', None) if has_app_context() else None
    actor = actor_key or getattr(user, 'id', None) or getattr(user, 'username', None) or 'system'
    tenant_key = tenant.slug if tenant else 'single-tenant'
    kwargs = dict(studio_db=backend, tenant_key=tenant_key, mailbox_kind=kind,
                  tenant_root=root, actor_key=str(actor), load_catalog=load_catalog)
    try:
        return GestioneEmailSQL(str(path), **kwargs)
    except MailboxNotInitialized:
        _initialize_empty_sql_catalog(backend, tenant_key, kind, path, profile.effective_mode.lower())
        return GestioneEmailSQL(str(path), **kwargs)
