"""Prepara gli schemi documentali degli studi prima dell'avvio delle consultazioni."""
import argparse
import json
import os
from pathlib import Path

from pct.document_intelligence.preparation import prepare_document_ai_schema
from pct.storage import StudioDB
from pct.storage_postgres import PostgresStudioDB


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--tenant-registry')
    source.add_argument('--sqlite-path')
    source.add_argument('--postgres-dsn-env', help='Nome della variabile del DSN; mai il valore nel comando')
    parser.add_argument('--fascicoli-path', help='Percorso proprietario esplicito per un singolo studio')
    parser.add_argument('--backup-dir', required=True)
    args = parser.parse_args()
    if not args.tenant_registry:
        if not args.fascicoli_path:
            parser.error('Per un singolo studio indicare --fascicoli-path.')
        if args.sqlite_path:
            path = Path(args.sqlite_path).resolve(strict=True)
            backend = StudioDB(str(path), initialize_schema=False)
        else:
            dsn = os.environ.get(args.postgres_dsn_env)
            if not dsn:
                raise RuntimeError('Configurazione PostgreSQL dello studio non disponibile.')
            backend = PostgresStudioDB(dsn, initialize_schema=False)
        try:
            changed = prepare_document_ai_schema(backend, args.fascicoli_path, backup_dir=args.backup_dir)
            print(json.dumps({'changed': changed}), flush=True)
        finally:
            backend.chiudi()
        return
    from pct.tenant import GestioneTenant, DbMode
    from pct.postgres_runtime_support import database_config_to_dsn
    from web.services.storage_runtime import resolve_storage_runtime
    registry = GestioneTenant(registry_path=str(Path(args.tenant_registry).resolve(strict=True)))
    for studio in registry.lista():
        paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
        profile = resolve_storage_runtime(anchor_path=paths['FASCICOLI_DB'], tenant=studio)
        if profile.uses_sqlite:
            if not Path(profile.studio_db_path).is_file():
                print(json.dumps({'tenant': studio.slug, 'status': 'database_non_provisionato'}), flush=True)
                continue
            backend = StudioDB(profile.studio_db_path, initialize_schema=False)
        elif profile.effective_mode == DbMode.POSTGRESQL:
            backend = PostgresStudioDB(database_config_to_dsn(studio.database), initialize_schema=False)
        else:
            print(json.dumps({'tenant': studio.slug, 'status': 'archivio_non_sql'}), flush=True)
            continue
        try:
            changed = prepare_document_ai_schema(backend, paths['FASCICOLI_DB'], backup_dir=Path(args.backup_dir) / studio.slug)
            print(json.dumps({'tenant': studio.slug, 'changed': changed}), flush=True)
        finally:
            backend.chiudi()


if __name__ == '__main__':
    main()
