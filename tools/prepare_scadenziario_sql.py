"""Adozione degli scadenziari degli studi registrati, fuori dalle richieste."""
import argparse
import json
import os
from pathlib import Path

from pct.core_storage_backend import build_core_storage_backend
from pct.scadenziario_sql_adoption import adopt, read_source
from pct.scadenziario_sql_owner import read_owner, resolve_owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-registry', required=True)
    parser.add_argument('--backup-dir')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--writers-drained', action='store_true')
    args = parser.parse_args()
    if not args.check and (not args.backup_dir or not args.writers_drained):
        parser.error('Backup persistente e arresto dei produttori obbligatori.')
    from pct.tenant import GestioneTenant
    registry_path = Path(args.tenant_registry).resolve(strict=True)
    registry = GestioneTenant(registry_path=str(registry_path))
    ready = True
    for studio in registry.lista():
        paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
        source = paths['SCADENZIARIO_DB']
        backend = build_core_storage_backend(studio.database, studio_db_path=paths['STUDIO_DB'], initialize_schema=False)
        if backend is None:
            raise RuntimeError('Archivio SQL proprietario non disponibile per lo scadenziario: ' + studio.slug)
        try:
            owner = read_owner(source)
            if args.check:
                if owner is None:
                    read_source(source)  # La verifica non avvia importazioni o scritture.
                    ready = False
                    result = {'ready': False}
                else:
                    try:
                        resolve_owner(source, backend)
                    except RuntimeError:
                        ready = False
                        result = {'ready': False, 'recovery_required': True}
                    else:
                        result = {'ready': True}
            else:
                result = adopt(backend, source, tenant=studio.slug, registry=str(registry_path),
                               destination=Path(args.backup_dir) / studio.slug,
                               data_root=os.environ.get('PCT_DATA_ROOT') or registry_path.parent,
                               writers_drained=args.writers_drained)
            print(json.dumps({'tenant': studio.slug, **result}), flush=True)
        finally:
            if getattr(backend, 'backend_kind', '') == 'postgresql':
                backend.chiudi()
    return 0 if ready else 2


if __name__ == '__main__':
    raise SystemExit(main())
