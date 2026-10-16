"""Ripresa mirata del calendario nella regia nativa, senza caricare gestori."""


def resume_calendar_query_events(app, *, limit=50):
    from flask import g

    from pct.calendar_query_repository import CalendarQueryNotReady, CalendarQueryRepository
    from pct.tenant import GestioneTenant, StatoTenant
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.studio_readonly import worker_studio_writer
    from web.services.tenant_paths import tenant_data_path

    manager = GestioneTenant(registry_path=app.config['TENANTS_REGISTRY']) if app.config.get('MULTI_TENANT') else None
    owners = [owner for owner in manager.lista() if owner.stato != StatoTenant.SOSPESO] if manager else [None]
    totals = dict(delivered=0, failed=0, not_migrated=0)
    for owner in owners:
        with app.test_request_context('/__scheduler/calendar-query-events'):
            if owner:
                _attach_tenant_context(manager, owner)
            else:
                g.multi_tenant_enabled, g.tenant_context_missing = False, False
            anchor = tenant_data_path('AGENDA_DB', app.config.get('AGENDA_DB', ''), require_tenant=True)
            try:
                with worker_studio_writer(anchor) as database:
                    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
                    sql = ("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='calendar_query_owner'"
                           if postgres else "SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_query_owner'")
                    if database.conn.execute(sql).fetchone() is None:
                        totals['not_migrated'] += 2
                        continue
                    repository = CalendarQueryRepository(database, owner.slug if owner else 'single-tenant')
                    for domain in ('agenda', 'deadlines'):
                        try:
                            result = repository.retry_events(domain=domain, limit=limit)
                            totals['delivered'] += result['delivered']
                            totals['failed'] += result['failed']
                        except CalendarQueryNotReady:
                            totals['not_migrated'] += 1
            except Exception:
                totals['failed'] += 1
                app.logger.error('Consegna indice calendario non confermata: studio=%s.', owner.slug if owner else 'single-tenant')
    return totals
