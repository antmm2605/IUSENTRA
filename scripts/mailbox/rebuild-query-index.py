"""Proiezione consultiva della posta: backup nativo e lotti SQL riprendibili.

Non importa messaggi, non legge MIME o documenti e non cambia gli stati PEC.
Senza --apply riporta soltanto i conteggi del catalogo SQL proprietario.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.query_index_backup import verified_backup


def rebuild(repository, *, destination, limit=100, max_batches=100):
    snapshot, digest = verified_backup(repository.db, destination)
    repository.ensure_schema()
    state = repository.begin_query_index_migration(backup_reference=str(snapshot), backup_sha256=digest,
                                                   actor_key='mailbox-query-migration')
    processed = 0
    for _ in range(max_batches):
        if state['phase'] == 'COMPLETED':
            break
        result = repository.rebuild_query_index_batch(migration_id=state['id'], after_key=state['after_key'],
                                                       limit=limit, actor_key='mailbox-query-migration')
        processed += result['processed']
        state.update(after_key=result['after_key'], phase='COMPLETED' if result['done'] else 'BACKFILL')
    return {'migration_id': state['id'], 'phase': state['phase'], 'processed_this_run': processed,
            'backup_sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--mailbox', choices=('pec', 'ordinary', 'all'), default='all')
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--max-batches', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.max_batches <= 1000 or (args.apply and args.backup_dir is None):
        parser.error('Servono un budget finito di lotti e una destinazione backup per applicare.')
    if args.apply and Path('/.dockerenv').exists() and os.environ.get('PCT_DATA_ROOT'):
        if not args.backup_dir.resolve().is_relative_to(Path(os.environ['PCT_DATA_ROOT']).resolve()):
            parser.error('Il backup deve rimanere nel volume dati persistente.')
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from web.app import create_app
    from web.helpers import _cfg
    from web.services.email_mailbox_readonly import mailbox_projection_worker, mailbox_reader

    app = create_app({'SCHEDULER_ONLY': True})
    manager, targets = _targets(app, args.tenant)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('a', encoding='utf-8') as report:
        for slug, owner in targets.items():
            with _tenant_context(app, manager, owner, slug):
                for kind, key in (('pec', 'EMAIL_CASELLA_DB'), ('ordinary', 'EMAIL_ORDINARIA_DB')):
                    if args.mailbox not in ('all', kind):
                        continue
                    connection = mailbox_projection_worker if args.apply else mailbox_reader
                    with connection(_cfg(key), expected_tenant=owner.slug if owner else 'single-tenant') as repository:
                        result = {'tenant': slug, 'mailbox': kind, 'apply': args.apply, 'records': repository.count()}
                        if args.apply:
                            result.update(rebuild(repository, destination=args.backup_dir / slug / kind,
                                                  max_batches=args.max_batches))
                        report.write(json.dumps(result, ensure_ascii=False) + '\n')
                        report.flush()
                        os.fsync(report.fileno())
                        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
