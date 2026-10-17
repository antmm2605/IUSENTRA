"""Consegne consultive delle ricevute: solo eventi pendenti, nessun MIME."""


def resume_deposit_query_events(app, *, limit=50):
    from flask import g

    from pct.pec_deposit_query_repository import PecDepositQueryRepository
    from pct.tenant import GestioneTenant, StatoTenant
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.notification_presidia_runtime import _presidio_db_path, _tenant_id
    from web.services.pec_audit_query_connection import pec_audit_query_connection

    manager = GestioneTenant(registry_path=app.config['TENANTS_REGISTRY']) if app.config.get('MULTI_TENANT') else None
    owners = [owner for owner in manager.lista() if owner.stato != StatoTenant.SOSPESO] if manager else [None]
    totals = dict(delivered=0, failed=0, not_migrated=0)
    for owner in owners:
        with app.test_request_context('/__scheduler/deposit-query-events'):
            if owner:
                _attach_tenant_context(manager, owner)
            else:
                g.multi_tenant_enabled, g.tenant_context_missing = False, False
            try:
                if not _presidio_db_path().is_file():
                    totals['not_migrated'] += 1
                    continue
                tenant = _tenant_id()
                with pec_audit_query_connection(tenant=tenant, writable=True) as conn:
                    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pec_deposit_query_bootstrap'").fetchone() is None:
                        totals['not_migrated'] += 1
                        continue
                    marker = conn.execute('SELECT version FROM pec_deposit_query_bootstrap WHERE tenant_id=?', (tenant,)).fetchone()
                    if marker is None or marker[0] != 1:
                        totals['not_migrated'] += 1
                        continue
                    def finish(connection, *, rollback=False):
                        connection.rollback() if rollback else connection.commit()
                    result = PecDepositQueryRepository(conn, tenant).retry_events(finish=finish, limit=limit)
                    totals['delivered'] += result['delivered']
                    totals['failed'] += result['failed']
            except Exception:
                totals['failed'] += 1
                app.logger.error('Consegna indice ricevute deposito non confermata: studio=%s.', owner.slug if owner else 'single-tenant')
    return totals
