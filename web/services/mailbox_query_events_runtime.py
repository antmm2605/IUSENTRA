"""Ripresa delle sole proiezioni posta pendenti nella regia periodica nativa."""


def resume_mailbox_query_events(app, *, limit=50):
    from flask import g

    from pct.email_mailbox_repository import MailboxNotInitialized
    from pct.tenant import GestioneTenant, StatoTenant
    from web.services.email_mailbox_readonly import mailbox_projection_worker
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.tenant_paths import tenant_data_path

    manager = GestioneTenant(registry_path=app.config['TENANTS_REGISTRY']) if app.config.get('MULTI_TENANT') else None
    targets = [owner for owner in manager.lista() if owner.stato != StatoTenant.SOSPESO] if manager else [None]
    totals = {'delivered': 0, 'failed': 0, 'not_migrated': 0}
    for owner in targets:
        with app.test_request_context('/__scheduler/mailbox-query-events'):
            if owner is not None:
                _attach_tenant_context(manager, owner)
            else:
                g.multi_tenant_enabled = False
                g.tenant_context_missing = False
            for key in ('EMAIL_CASELLA_DB', 'EMAIL_ORDINARIA_DB'):
                path = tenant_data_path(key, app.config.get(key, ''), require_tenant=True)
                if not path:
                    continue
                try:
                    with mailbox_projection_worker(path, expected_tenant=owner.slug if owner else 'single-tenant') as repository:
                        marker = repository.db.conn.execute('SELECT version FROM email_mailbox_query_bootstrap '
                                                             'WHERE tenant_key=? AND mailbox_kind=?',
                                                             (repository.tenant, repository.kind)).fetchone()
                        if marker is None or marker[0] != 1:
                            totals['not_migrated'] += 1
                            continue
                        result = repository.retry_query_index_events(limit=limit)
                        totals['delivered'] += result['delivered']
                        totals['failed'] += result['failed']
                except MailboxNotInitialized:
                    totals['not_migrated'] += 1
                except Exception:
                    import logging

                    totals['failed'] += 1
                    logging.getLogger(__name__).error(
                        'Consegna indice posta non confermata: studio=%s casella=%s. Nessun catalogo riletto.',
                        owner.slug if owner else 'single-tenant', key,
                    )
    return totals
