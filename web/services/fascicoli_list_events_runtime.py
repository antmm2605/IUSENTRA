"""Recupero delle sole consegne pendenti nella outbox condivisa."""
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime

from pct.fascicoli_list_query import AGGREGATE, EVENT_TYPE
from pct.query_projection_worker import deliver_pending
from web.services.fascicoli_list_runtime import catalog_exists, native_list_repository
from web.services.fascicoli_list_writer import FascicoliListWriter, confirm_recovered_events
from web.services.registro_letture_runtime import registro_corrente, connessione_registro


def pending(conn, tenant):
    return conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? AND aggregate_type=? '
        "AND event_type=? AND status='PENDING' AND attempts<5 AND available_at<=? LIMIT 1",
        (tenant, AGGREGATE, EVENT_TYPE, datetime.now(UTC).isoformat())).fetchone() is not None


@contextmanager
def registry_outbox_writer(registry):
    """Sessione di consegna separata dalle letture native; nessun DDL runtime."""
    if registry.backend_kind == 'postgres':
        from pct.postgres_runtime_support import PostgresRepositoryBackend
        from pct.registro_letture.repository import SCHEMA_POSTGRES
        backend = PostgresRepositoryBackend(registry.postgres_dsn, SCHEMA_POSTGRES, initialize_schema=False)
        try:
            with backend.connection() as conn:
                yield conn
        finally:
            backend.close()
    else:
        conn = sqlite3.connect(registry.db_path.resolve().as_uri() + '?mode=rw', uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()


def resume_owner_events(database, tenant, anchor, *, limit=50):
    """Il proprietario e i due database sono già risolti dal contesto studio."""
    registry = registro_corrente(sola_lettura=True)
    from pct.fascicoli_list_clock import refresh_clock
    clock_target = getattr(database, 'raw_conn', None) or database.conn
    try:
        refresh_clock(database.conn, tenant, postgres=getattr(database, 'backend_kind', '') == 'postgresql', limit=limit)
        clock_target.commit()
    except Exception:
        clock_target.rollback()
        raise
    with connessione_registro(registry) as conn:
        if not catalog_exists(conn, 'fascicoli_list_registry_owner', postgres=registry.backend_kind == 'postgres'):
            return dict(delivered=0, failed=0, not_migrated=1)
        owner = conn.execute('SELECT tenant_key,version FROM fascicoli_list_registry_owner WHERE tenant_key=?', (tenant,)).fetchone()
        if owner is None or owner[0] != tenant or owner[1] != 1:
            raise ValueError('Registro delle fonti non attribuito allo studio corrente.')
        registry_pending = pending(conn, tenant)
    core_pending = pending(database.conn, tenant)
    if not registry_pending and not core_pending:
        return dict(delivered=0, failed=0, not_migrated=0)
    writer = FascicoliListWriter(database, tenant, native_list_repository(database, anchor))
    result = writer.recover(limit=limit) if core_pending else dict(delivered=0, failed=0)
    if registry_pending:
        with registry_outbox_writer(registry) as source:
            def finish(connection, *, rollback=False):
                connection.rollback() if rollback else connection.commit()

            def project(_source, key):
                try:
                    failed = [row[0] for row in _source.execute('SELECT id FROM transactional_outbox '
                        "WHERE tenant_id=? AND aggregate_type=? AND event_type=? AND aggregate_id=? AND status='FAILED'",
                        (tenant, AGGREGATE, EVENT_TYPE, key)).fetchall()]
                    writer.handle_event(database.conn, key)
                    target = getattr(database, 'raw_conn', None) or database.conn
                    target.commit()
                    confirm_recovered_events(_source, tenant, failed)
                except Exception:
                    target = getattr(database, 'raw_conn', None) or database.conn
                    target.rollback()
                    raise
            delivered = deliver_pending(conn=source, finish=finish, tenant=tenant, aggregate=AGGREGATE,
                                        event_type=EVENT_TYPE, project=project, limit=limit)
            result['delivered'] += delivered['delivered']
            result['failed'] += delivered['failed']
    return {**result, 'not_migrated': 0}


def resume_fascicoli_list_events(app, *, limit=50):
    from flask import g
    from pct.tenant import GestioneTenant, StatoTenant
    from web.services.document_intelligence_runtime import document_ai_tenant_id
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.studio_readonly import worker_studio_writer
    from web.services.tenant_paths import tenant_data_path

    manager = GestioneTenant(registry_path=app.config['TENANTS_REGISTRY']) if app.config.get('MULTI_TENANT') else None
    owners = [owner for owner in manager.lista() if owner.stato != StatoTenant.SOSPESO] if manager else [None]
    totals = dict(delivered=0, failed=0, not_migrated=0)
    for owner in owners:
        with app.test_request_context('/__scheduler/fascicoli-list-events'):
            if owner:
                _attach_tenant_context(manager, owner)
            else:
                g.multi_tenant_enabled, g.tenant_context_missing = False, False
            anchor = tenant_data_path('FASCICOLI_DB', app.config.get('FASCICOLI_DB', ''), require_tenant=True)
            try:
                with worker_studio_writer(anchor) as database:
                    if not catalog_exists(database.conn, 'fascicoli_list_owner',
                                          postgres=getattr(database, 'backend_kind', '') == 'postgresql'):
                        totals['not_migrated'] += 1
                        continue
                    tenant = document_ai_tenant_id()
                    owner_row = database.conn.execute('SELECT tenant_key FROM fascicoli_list_owner WHERE singleton=1').fetchone()
                    if owner_row is None or owner_row[0] != tenant:
                        raise ValueError('Catalogo non attribuito allo studio corrente.')
                    result = resume_owner_events(database, tenant, anchor, limit=limit)
                    for key in totals:
                        totals[key] += result[key]
            except Exception:
                totals['failed'] += 1
                app.logger.error('Consegna catalogo fascicoli non confermata: studio=%s.', owner.slug if owner else 'single-studio')
    return totals
