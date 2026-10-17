"""Prepara i modelli degli studi registrati, senza avviare il runtime applicativo."""
import argparse
import json
from pathlib import Path

from pct.postgres_runtime_support import database_config_to_dsn
from pct.template_atti_preparation import catalog_ready, prepare_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-registry', required=True)
    parser.add_argument('--backup-dir')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--writers-drained', action='store_true')
    args = parser.parse_args()
    if not args.check and (not args.backup_dir or not args.writers_drained):
        parser.error('Indicare backup persistente e scrittori fermi.')
    from pct.tenant import GestioneTenant

    registry = GestioneTenant(registry_path=str(Path(args.tenant_registry).resolve(strict=True)))
    ready = True
    for studio in registry.lista():
        paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
        path = paths['TEMPLATE_ATTI_DB']
        dsn = database_config_to_dsn(studio.database)
        if args.check:
            current = catalog_ready(path, postgres_dsn=dsn)
            ready = ready and current
            result = dict(ready=current)
        else:
            result = prepare_catalog(path, backup_dir=Path(args.backup_dir) / studio.slug,
                                     postgres_dsn=dsn, writers_drained=True)
        print(json.dumps(dict(tenant=studio.slug, **result)), flush=True)
    return 0 if ready else 2


if __name__ == '__main__':
    raise SystemExit(main())
