"""Consegna interna dei gestori sul proprietario SQL dello studio corrente."""
from pathlib import Path

from flask import current_app, g


def current_payment_repository(database):
    from pct.parcella_incassi_repository import ParcellaIncassiRepository
    from web.helpers import _cfg
    from web.services.storage_runtime import get_request_storage_runtime
    from web.services.prima_nota_runtime import open_prima_nota_repository
    tenant = str(getattr(g, 'tenant_context_slug', '') or getattr(getattr(g, 'tenant', None), 'slug', '') or '').strip()
    if not tenant and not (current_app.config.get('MULTI_TENANT') or getattr(g, 'multi_tenant_enabled', False)):
        tenant = 'studio'
    if not tenant or getattr(g, 'tenant_context_missing', False) or database is None:
        raise RuntimeError('Studio SQL della conferma non riscontrato.')
    profile = get_request_storage_runtime(_cfg('CLIENTI_DB'))
    if profile.uses_sqlite:
        if (getattr(database, 'backend_kind', '') == 'postgresql'
                or Path(database.db_path).resolve() != Path(profile.studio_db_path).resolve()):
            raise RuntimeError('Pagamenti e incassi hanno proprietari SQL differenti.')
    elif profile.effective_mode == 'POSTGRESQL':
        from psycopg2.extensions import parse_dsn
        from web.services.prima_nota_runtime import _postgres_request_dsn
        if getattr(database, 'backend_kind', '') != 'postgresql' or parse_dsn(database.dsn) != parse_dsn(_postgres_request_dsn()):
            raise RuntimeError('Pagamenti e incassi hanno proprietari SQL differenti.')
    else:
        raise RuntimeError('Proprietario SQL non configurato per gli incassi dei gestori.')
    cash = open_prima_nota_repository(_cfg('PRIMA_NOTA_DB'), anchor=_cfg('CLIENTI_DB'), tenant_key=tenant,
        actor_key='payment-verifier', get_profile=get_request_storage_runtime, get_database=lambda anchor: database)
    repo = ParcellaIncassiRepository(cash.db, tenant, actor_key='payment-verifier')
    repo.require_prepared()
    return repo


def payment_link_amount(gp, invoice):
    from pct.parcella_incassi_views import payment_link_amount as amount_for_invoice
    database = getattr(gp, '_studio_db', None)
    if database is None:
        return amount_for_invoice(None, invoice)
    repo = current_payment_repository(database)
    return amount_for_invoice(database, invoice, tenant_key=repo.tenant)


def confirm_payment(gp, facts, *, verification_kind):
    from pct.payment_confirmations import ingest, deliver, TABLE
    repo = current_payment_repository(gp._studio_db)
    key = ingest(repo.db, repo.tenant, facts, verification_kind=verification_kind)
    outcome = deliver(repo.db, repo.tenant, source_key=key, limit=1)
    # Invalidare solo la copia del collegamento della richiesta corrente.
    gp.get_by_id(facts.link_id)
    source = repo.db.conn.execute('SELECT paid_on FROM ' + TABLE + ' WHERE tenant_key=? AND source_key=?',
                                  (repo.tenant, key)).fetchone()
    return {'source_key': key, 'delivered': outcome['delivered'], 'failed': outcome['failed'],
            'date_required': source is None or source[0] is None}
