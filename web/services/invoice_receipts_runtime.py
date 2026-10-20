"""Repository puntuale degli incassi sul proprietario SQL di Prima nota."""
from __future__ import annotations

import hashlib
import json

from flask import current_app, g


def current_invoice_receipts(*, readonly=False):
    from web.helpers import _cfg
    from web.services.prima_nota_runtime import open_prima_nota_repository, get_existing_prima_nota_database
    from web.services.storage_runtime import get_request_storage_runtime
    from pct.parcella_incassi_repository import ParcellaIncassiRepository

    tenant = str(getattr(g, 'tenant_context_slug', '') or '').strip().lower()
    tenant = tenant or str(getattr(getattr(g, 'tenant', None), 'slug', '') or '').strip().lower()
    if not tenant and not (current_app.config.get('MULTI_TENANT') or getattr(g, 'multi_tenant_enabled', False)):
        tenant = 'studio'
    actor = str(getattr(getattr(g, 'utente_corrente', None), 'id', '') or '').strip()
    if not tenant or not actor or getattr(g, 'tenant_context_missing', False):
        raise RuntimeError('Studio e operatore non riscontrati: nessuna operazione eseguita.')
    cash = open_prima_nota_repository(_cfg('PRIMA_NOTA_DB'), anchor=_cfg('CLIENTI_DB'),
        tenant_key=tenant, actor_key=actor, get_profile=get_request_storage_runtime,
        get_database=lambda anchor: get_existing_prima_nota_database(anchor, readonly=readonly))
    repo = ParcellaIncassiRepository(cash.db, tenant, actor_key=actor)
    repo.require_prepared()
    return repo


def receipt_command_scope(repo, invoice_id):
    # Lo scope del browser separa studio, operatore e singolo documento.
    # L'identità del database non viene esposta in chiaro.
    owner = str(getattr(repo.db, 'db_path', ''))
    if getattr(repo.db, 'backend_kind', '') == 'postgresql':
        from psycopg2.extensions import parse_dsn
        parameters = parse_dsn(repo.db.dsn)
        owner = json.dumps({key: parameters.get(key, '') for key in
            ('host', 'hostaddr', 'port', 'dbname', 'user', 'options')}, sort_keys=True)
    return hashlib.sha256(json.dumps(['invoice-receipt-v1', owner, repo.tenant,
        repo.actor, invoice_id], separators=(',', ':')).encode()).hexdigest()
