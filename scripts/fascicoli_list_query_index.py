"""Prepara il catalogo paginato con backup verificati e lotti finiti."""
import argparse
import json
import os
from pathlib import Path


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
    from web.helpers import _cfg
    from web.services.document_intelligence_runtime import document_ai_tenant_id
    from web.services.fascicoli_list_preparation import prepare_catalog
    from web.services.studio_readonly import request_studio_reader, worker_studio_writer

    app = create_app({'SCHEDULER_ONLY': True, 'DISABLE_SCHEDULER': True})
    manager, owners = _targets(app, '' if args.tenant == 'all' else args.tenant)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('a', encoding='utf-8') as report:
        for slug, owner in owners.items():
            with _tenant_context(app, manager, owner, slug):
                anchor = _cfg('FASCICOLI_DB')
                connection = worker_studio_writer if args.apply else request_studio_reader
                with connection(anchor) as database:
                    result = dict(tenant=slug, apply=args.apply,
                        records=int(database.conn.execute('SELECT COUNT(*) FROM fascicoli').fetchone()[0]))
                    if args.apply:
                        result.update(prepare_catalog(database, tenant=document_ai_tenant_id(), anchor=anchor,
                            destination=args.backup_dir / slug, max_batches=args.max_batches))
                    report.write(json.dumps(result, ensure_ascii=False) + '\n')
                    report.flush()
                    os.fsync(report.fileno())
                    print(json.dumps(result, ensure_ascii=False))
                    if args.apply and result.get('phase') != 'COMPLETED':
                        raise RuntimeError('Budget del lotto terminato: checkpoint preservato, rilascio non attivabile.')


if __name__ == '__main__':
    main()
