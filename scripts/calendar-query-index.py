"""Catalogo consultivo calendario: backup verificato e lotti SQL finiti."""
import argparse
import json
import os
from pathlib import Path

from pct.calendar_query_preparation import rebuild as rebuild


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--domain', choices=('agenda', 'deadlines', 'all'), default='all')
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
    from web.helpers import _cfg
    from web.services.studio_readonly import request_studio_reader, worker_studio_writer

    app = create_app({'SCHEDULER_ONLY': True})
    manager, owners = _targets(app, args.tenant)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('a', encoding='utf-8') as report:
        for slug, owner in owners.items():
            with _tenant_context(app, manager, owner, slug):
                connection = worker_studio_writer if args.apply else request_studio_reader
                with connection(_cfg('AGENDA_DB')) as database:
                    for domain, table in [('agenda', 'appuntamenti'), ('deadlines', 'scadenze')]:
                        if args.domain not in ('all', domain):
                            continue
                        result = dict(tenant=slug, domain=domain, apply=args.apply,
                                      records=int(database.conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]))
                        if args.apply:
                            result.update(rebuild(database, tenant=owner.slug if owner else 'single-tenant',
                                destination=args.backup_dir / slug / domain, domain=domain, max_batches=args.max_batches))
                        report.write(json.dumps(result, ensure_ascii=False) + '\n')
                        report.flush()
                        os.fsync(report.fileno())
                        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
