"""Preparazione esplicita delle due fonti ricevute, mai attivata dalle domande Lex."""
import argparse
import importlib.util
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', default='all')
    parser.add_argument('--backup-dir', type=Path, required=True)
    args = parser.parse_args()
    if Path('/.dockerenv').exists() and os.environ.get('PCT_DATA_ROOT'):
        if not args.backup_dir.resolve().is_relative_to(Path(os.environ['PCT_DATA_ROOT']).resolve()):
            parser.error('Il backup deve rimanere nel volume dati persistente.')
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from web.app import create_app
    from web.services.notification_presidia_runtime import _presidio_db_path, _tenant_id
    from web.services.pec_audit_query_connection import pec_audit_query_connection
    from web.services.receipt_archive_runtime import prepare_archive_receipts
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    script = Path(__file__).parent / 'mailbox/rebuild-deposit-query-index.py'
    spec = importlib.util.spec_from_file_location('receipt_query_preparer', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = create_app({'SCHEDULER_ONLY': True, 'DISABLE_SCHEDULER': True})
    manager, owners = _targets(app, '' if args.tenant == 'all' else args.tenant)
    for slug, owner in owners.items():
        with _tenant_context(app, manager, owner, slug):
            registry = registro_corrente(sola_lettura=True)
            archived = prepare_archive_receipts(registry, tenant_corrente(), args.backup_dir / slug / 'letture')
            deposits = dict(phase='NOT_CONFIGURED')
            if _presidio_db_path().is_file():
                with pec_audit_query_connection(tenant=_tenant_id(), writable=True) as conn:
                    deposits = module.rebuild(conn, tenant=_tenant_id(), path=_presidio_db_path(), destination=args.backup_dir / slug / 'pec')
                    if deposits['phase'] != 'COMPLETED':
                        raise RuntimeError('Catalogo ricevute PEC non completato.')
            print(json.dumps(dict(tenant=slug, archive=archived, deposits=deposits)))


if __name__ == '__main__':
    main()
