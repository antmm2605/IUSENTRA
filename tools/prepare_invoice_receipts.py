"""Prepara gli incassi sul repository proprietario; nessuna migrazione nelle GET."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pct.parcella_incassi_preparation import InvoiceReceiptsNotPrepared, prepare_invoice_receipts
from pct.prima_nota_transition import read_transition


def adoption_status(database, source, tenant):
    from web.services.prima_nota_runtime import _read_adoption
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    connection = database.raw_conn if postgres else database.conn
    state = _read_adoption(connection, tenant, postgres=postgres)
    marker = read_transition(source)
    if marker is None and state is None:
        return False, None
    if marker is None or marker['tenant'] != tenant:
        raise RuntimeError('Proprietà della Prima nota non riscontrata: nessuna reimportazione.')
    if state is not None and (state[0] != marker['source_sha256'] or not str(state[1] or '').strip()):
        raise RuntimeError('Fonte SQL e transizione Prima nota discordanti.')
    if marker['phase'] == 'committed':
        if state is None:
            raise RuntimeError('Transizione confermata senza repository Prima nota.')
        return True, None
    # La ripresa conserva il riferimento del backup già adottato dal repository.
    return False, Path(state[1]).parent if state is not None else None


def open_database(profile, studio, *, readonly=False):
    if profile.uses_sqlite:
        from pct.storage import StudioDB
        path = Path(profile.studio_db_path).resolve(strict=True)
        return StudioDB(str(path), initialize_schema=False, readonly=readonly)
    if profile.effective_mode == 'POSTGRESQL':
        from pct.postgres_runtime_support import database_config_to_dsn
        from pct.storage_postgres import PostgresStudioDB
        return PostgresStudioDB(database_config_to_dsn(studio.database), initialize_schema=False, readonly=readonly)
    raise RuntimeError('Repository SQL proprietario necessario per gli incassi.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-registry', required=True)
    parser.add_argument('--backup-dir', required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--writers-drained', action='store_true')
    args = parser.parse_args()
    if not args.check and not args.writers_drained:
        parser.error('Arrestare i produttori prima della preparazione esplicita.')
    from pct.tenant import GestioneTenant, StatoTenant
    from pct.parcella_incassi_repository import ParcellaIncassiRepository
    from web.services.storage_runtime import resolve_storage_runtime
    registry_path = Path(args.tenant_registry).resolve(strict=True)
    manager = GestioneTenant(registry_path=str(registry_path))
    root = Path(args.backup_dir).resolve()
    pending = False
    for studio in manager.lista():
        if studio.stato == StatoTenant.SOSPESO:
            continue
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', studio.slug):
            raise RuntimeError('Identificativo dello studio non canonico: preparazione sospesa.')
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
        profile = resolve_storage_runtime(anchor_path=paths['CLIENTI_DB'], tenant=studio)
        database = open_database(profile, studio, readonly=True)
        try:
            adopted, resume_root = adoption_status(database, paths['PRIMA_NOTA_DB'], studio.slug)
            if adopted:
                try:
                    ParcellaIncassiRepository(database, studio.slug, actor_key='preparazione-incassi').require_prepared()
                    print(json.dumps({'tenant': studio.slug, 'changed': False}), flush=True)
                    continue
                except InvoiceReceiptsNotPrepared:
                    pass
            pending = True
        finally:
            database.chiudi()
        if args.check:
            print(json.dumps({'tenant': studio.slug, 'preparation_required': True, 'adoption_required': not adopted}), flush=True)
            continue
        if not adopted:
            adoption_root = resume_root or root / 'prima-nota'
            subprocess.run([sys.executable, '-m', 'scripts.migra_prima_nota_sql',
                '--tenant', studio.slug, '--tenant-registry', str(registry_path),
                '--report', str(root / 'adozione-prima-nota.jsonl'), '--apply', '--writers-drained',
                '--backup-dir', str(adoption_root)], check=True)
        database = open_database(profile, studio)
        try:
            if not adoption_status(database, paths['PRIMA_NOTA_DB'], studio.slug)[0]:
                raise RuntimeError('Adozione Prima nota non confermata dopo la preparazione.')
            attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            result = prepare_invoice_receipts(database, studio.slug, root / studio.slug / attempt)
            print(json.dumps({'tenant': studio.slug, **result}), flush=True)
        finally:
            database.chiudi()
    return 2 if args.check and pending else 0


if __name__ == '__main__':
    raise SystemExit(main())
