"""Consegna della proiezione delle ricevute tramite la outbox condivisa."""
from types import SimpleNamespace

from pct.query_projection_worker import deliver_pending
from pct.registro_letture.ricevute_query import AGGREGATE, EVENT, ReceiptArchiveQuery, install
from web.services.fascicoli_list_events_runtime import registry_outbox_writer
from web.services.registro_letture_runtime import connessione_registro


def resume_archive_owner(registry, tenant, *, limit=50):
    with connessione_registro(registry) as read:
        postgres = registry.backend_kind == 'postgres'
        exists = read.execute("SELECT to_regclass('receipt_archive_query_owner')" if postgres else
                              "SELECT name FROM sqlite_master WHERE type='table' AND name='receipt_archive_query_owner'").fetchone()
        if not exists or not exists[0]:
            return dict(delivered=0, failed=0, not_migrated=1)
        ready = read.execute('SELECT ready FROM receipt_archive_query_owner WHERE tenant_id=?', (tenant,)).fetchone()
        if not ready or ready[0] != 1:
            return dict(delivered=0, failed=0, not_migrated=1)
    with registry_outbox_writer(registry) as writer:
        def finish(connection, *, rollback=False):
            connection.rollback() if rollback else connection.commit()
        result = deliver_pending(conn=writer, finish=finish, tenant=tenant, aggregate=AGGREGATE,
            event_type=EVENT, project=lambda connection, key: ReceiptArchiveQuery(connection, tenant).project_case(registry, key), limit=limit)
        return dict(result, not_migrated=0)


def prepare_archive_receipts(registry, tenant, destination, *, max_batches=100):
    from scripts.query_index_backup import verified_backup

    if type(max_batches) is not int or not 1 <= max_batches <= 1000:
        raise ValueError('Budget di preparazione non valido.')
    with connessione_registro(registry) as conn:
        adapter = SimpleNamespace(conn=conn, db_path=registry.db_path,
            backend_kind='postgresql' if registry.backend_kind == 'postgres' else 'sqlite',
            dsn=registry.postgres_dsn)
        snapshot, _digest = verified_backup(adapter, destination)
    with registry_outbox_writer(registry) as conn:
        install(conn, tenant, postgres=registry.backend_kind == 'postgres')
        row = conn.execute('SELECT ready,after_case,backup_reference FROM receipt_archive_query_owner WHERE tenant_id=?', (tenant,)).fetchone()
        if row[2] and row[2] != str(snapshot):
            raise ValueError('Backup di ripresa delle ricevute discordante.')
        conn.execute('UPDATE receipt_archive_query_owner SET backup_reference=? WHERE tenant_id=?', (str(snapshot), tenant))
        cursor, complete, processed = row[1], bool(row[0]), 0
        conn.commit()
        for _ in range(max_batches):
            if complete:
                break
            cases = conn.execute('SELECT DISTINCT fascicolo_id FROM letture_fatti WHERE tenant_id=? '
                "AND categoria='prova_notifica' AND campo IN ('rac','rdac','deposito_prova') AND fascicolo_id>? "
                'ORDER BY fascicolo_id LIMIT 100', (tenant, cursor)).fetchall()
            for case in cases:
                ReceiptArchiveQuery(conn, tenant).project_case(registry, case[0])
                cursor = case[0]
                processed += 1
            complete = not cases
            conn.execute('UPDATE receipt_archive_query_owner SET after_case=?,ready=? WHERE tenant_id=?',
                         (cursor, int(complete), tenant))
            conn.commit()
    if not complete:
        raise RuntimeError('Preparazione ricevute non terminata: cursore conservato per la ripresa.')
    # La preparazione può generare più di un lotto di eventi. Non dichiarare
    # concluso il catalogo lasciando consegne pendenti o rimandate dal retry.
    for _ in range(max_batches):
        delivered = resume_archive_owner(registry, tenant)
        if delivered['failed']:
            raise RuntimeError('Consegne delle ricevute da recuperare.')
        with connessione_registro(registry) as read:
            pending = read.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? '
                "AND aggregate_type=? AND event_type=? AND status IN ('PENDING','FAILED') LIMIT 1",
                (tenant, AGGREGATE, EVENT)).fetchone()
        if not pending:
            break
        if not delivered['delivered']:
            raise RuntimeError('Consegne delle ricevute in attesa di recupero: catalogo non confermato.')
    else:
        raise RuntimeError('Budget delle consegne esaurito: riprendere la preparazione delle ricevute.')
    return dict(phase='COMPLETED', processed_cases=processed, backup=str(snapshot))


def resume_receipt_archive_events(app, *, limit=50):
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    manager, owners = _targets(app, '')
    totals = dict(delivered=0, failed=0, not_migrated=0)
    for slug, owner in owners.items():
        with _tenant_context(app, manager, owner, slug):
            try:
                registry = registro_corrente(sola_lettura=True)
                result = resume_archive_owner(registry, tenant_corrente(), limit=limit)
                for key in totals:
                    totals[key] += result[key]
            except FileNotFoundError:
                # Studio non ancora predisposto: nessuna creazione periodica
                # né errore ripetuto; la consultazione resta indisponibile.
                totals['not_migrated'] += 1
            except Exception:
                totals['failed'] += 1
                app.logger.exception('Proiezione ricevute archiviate non confermata: studio=%s', slug)
    return totals
