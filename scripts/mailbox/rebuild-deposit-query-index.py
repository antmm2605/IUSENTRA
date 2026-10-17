"""Migrazione consultiva delle ricevute PEC: backup nativo e lotti finiti."""
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

from pct.pec_deposit_query_migration import begin, rebuild_batch
from pct.pec_deposit_query_repository import PecDepositQueryRepository, install_deposit_query_events
from scripts.query_index_backup import verified_backup


def rebuild(conn, *, tenant, path, destination, max_batches=100):
    if type(max_batches) is not int or not 1 <= max_batches <= 1000:
        raise ValueError('Budget di lotti non valido.')
    snapshot, digest = verified_backup(SimpleNamespace(conn=conn, db_path=path, backend_kind='sqlite'), destination)
    actor = 'pec-deposit-query-migration'
    repository = PecDepositQueryRepository(conn, tenant)
    try:
        install_deposit_query_events(conn)
        state = begin(conn, tenant=tenant, backup_reference=str(snapshot), backup_sha256=digest, actor=actor)
        conn.commit()
        processed = 0
        for _ in range(max_batches):
            if state['phase'] == 'COMPLETED':
                break
            state = rebuild_batch(conn, repository, migration_id=state['id'], after_key=state['after_key'], actor=actor)
            conn.commit()
            processed += state['processed']
        if state['phase'] == 'COMPLETED':
            def finish(connection, *, rollback=False):
                connection.rollback() if rollback else connection.commit()
            for _ in range(max_batches):
                delivery = repository.retry_events(finish=finish)
                if delivery['failed']:
                    raise RuntimeError('Consegne delle ricevute PEC da recuperare.')
                remaining = conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? '
                    "AND aggregate_type='pec_deposit_query' AND event_type='pec_deposit_query.refresh_requested' "
                    "AND status IN ('PENDING','FAILED') LIMIT 1", (tenant,)).fetchone()
                if not remaining:
                    break
                if not delivery['delivered']:
                    raise RuntimeError('Consegne delle ricevute PEC in attesa di recupero.')
            else:
                raise RuntimeError('Budget delle consegne PEC esaurito: riprendere la preparazione.')
        return dict(migration_id=state['id'], phase=state['phase'], processed_this_run=processed, backup_sha256=digest)
    except Exception:
        conn.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--max-batches', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.max_batches <= 1000 or (args.apply and args.backup_dir is None):
        parser.error('Servono budget finito e backup persistente per applicare.')
    if args.apply and Path('/.dockerenv').exists() and os.environ.get('PCT_DATA_ROOT'):
        if not args.backup_dir.resolve().is_relative_to(Path(os.environ['PCT_DATA_ROOT']).resolve()):
            parser.error('Il backup deve rimanere nel volume dati persistente.')
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from web.app import create_app
    from web.services.notification_presidia_runtime import _presidio_db_path, _tenant_id
    from web.services.pec_audit_query_connection import pec_audit_query_connection

    app = create_app({'SCHEDULER_ONLY': True})
    manager, owners = _targets(app, '' if args.tenant == 'all' else args.tenant)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('a', encoding='utf-8') as output:
        for slug, owner in owners.items():
            with _tenant_context(app, manager, owner, slug):
                tenant = _tenant_id()
                with pec_audit_query_connection(tenant=tenant, writable=args.apply) as conn:
                    result = dict(tenant=slug, apply=args.apply, records=int(conn.execute(
                        'SELECT COUNT(*) FROM pec_messages WHERE tenant_id=?', (tenant,)).fetchone()[0]))
                    if args.apply:
                        result.update(rebuild(conn, tenant=tenant, path=_presidio_db_path(),
                            destination=args.backup_dir / slug, max_batches=args.max_batches))
                    output.write(json.dumps(result, ensure_ascii=False) + '\n')
                    output.flush()
                    os.fsync(output.fileno())
                    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
