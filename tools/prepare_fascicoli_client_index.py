"""Prepara esplicitamente il catalogo cliente senza alterare i fascicoli."""
import argparse
import json
import os
from pathlib import Path
from pct.fascicoli_clienti_index import install_client_index, prepare_sqlite_client_index as prepare_sqlite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--sqlite-path')
    source.add_argument('--postgres-dsn-env', help='Nome della variabile che contiene il DSN dello studio')
    source.add_argument('--tenant-registry', help='Registro degli studi: usa i resolver nativi, senza bootstrap')
    parser.add_argument('--backup-dir')
    args = parser.parse_args()
    if args.sqlite_path:
        changed = prepare_sqlite(args.sqlite_path, args.backup_dir)
        print(json.dumps({'engine': 'sqlite', 'changed': changed}))
    elif args.tenant_registry:
        from pct.tenant import GestioneTenant, DbMode
        from web.services.storage_runtime import resolve_storage_runtime
        from pct.postgres_runtime_support import database_config_to_dsn, PostgresRepositoryBackend
        registry = GestioneTenant(registry_path=str(Path(args.tenant_registry).resolve(strict=True)))
        for studio in registry.lista():
            paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
            profile = resolve_storage_runtime(anchor_path=paths['FASCICOLI_DB'], tenant=studio)
            if profile.uses_sqlite:
                if not Path(profile.studio_db_path).is_file():
                    print(json.dumps({'tenant': studio.slug, 'status': 'database_non_provisionato'}))
                    continue
                backup = Path(args.backup_dir) / studio.slug if args.backup_dir else None
                changed = prepare_sqlite(profile.studio_db_path, backup)
            elif profile.effective_mode == DbMode.POSTGRESQL:
                backend = PostgresRepositoryBackend(database_config_to_dsn(studio.database),
                                                    Path(__file__), initialize_schema=False)
                try:
                    with backend.connection() as conn:
                        changed = install_client_index(conn, postgres=True)
                finally:
                    backend.close()
            else:
                print(json.dumps({'tenant': studio.slug, 'status': 'archivio_non_sql'}))
                continue
            print(json.dumps({'tenant': studio.slug, 'changed': changed}))
    else:
        from pct.postgres_runtime_support import PostgresRepositoryBackend
        dsn = os.environ.get(args.postgres_dsn_env)
        if not dsn:
            raise RuntimeError('Configurazione PostgreSQL dello studio non disponibile.')
        backend = PostgresRepositoryBackend(dsn, Path(__file__), initialize_schema=False)
        try:
            with backend.connection() as conn:
                changed = install_client_index(conn, postgres=True)
            print(json.dumps({'engine': 'postgresql', 'changed': changed}))
        finally:
            backend.close()


if __name__ == '__main__':
    main()
