"""Preparazione condivisa degli schemi documentali e della coda letture esistente."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def prepare_queue(registry, tenant, destination):
    from pct.registro_letture.event_retry import ReadingEventSchemaNotPrepared, install, require_prepared
    from scripts.query_index_backup import verified_backup
    from web.services.fascicoli_list_events_runtime import registry_outbox_writer
    from web.services.registro_letture_runtime import connessione_registro
    postgres = registry.backend_kind == 'postgres'
    with connessione_registro(registry) as conn:
        try:
            require_prepared(conn, postgres=postgres)
            ready = True
        except ReadingEventSchemaNotPrepared:
            ready = False
        if not ready:
            adapter = SimpleNamespace(conn=conn, db_path=registry.db_path,
                backend_kind='postgresql' if postgres else 'sqlite', dsn=registry.postgres_dsn)
            verified_backup(adapter, destination)
    if not ready:
        with registry_outbox_writer(registry) as conn:
            install(conn, postgres=postgres)
            conn.commit()
    return not ready


def _recupera(registry, writer, recover, adesso):
    from web.services.registro_letture_runtime import tenant_corrente
    with writer(registry) as conn:
        recovered = recover(conn, tenant_corrente(), adesso())
        conn.commit()
    return recovered


def _con_riprova(operazione, tentativi=3, pausa=20):
    """Il deploy gira mentre la versione in servizio scrive il registro: un blocco temporaneo si ritenta.

    Verifica del 01/11/2026: il deploy della 2.470.9 si fermava su «database is locked» durante il recupero
    delle letture. Solo il blocco si ritenta; ogni altro errore ferma il deploy come prima.
    """
    import sqlite3
    import time

    for tentativo in range(1, tentativi + 1):
        try:
            return operazione()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or tentativo == tentativi:
                raise
            print(json.dumps(dict(status='registro_occupato', tentativo=tentativo)), flush=True)
            time.sleep(pausa)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-registry', required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    args = parser.parse_args()
    registry_path = Path(args.tenant_registry).resolve(strict=True)
    if Path('/.dockerenv').exists() and os.environ.get('PCT_DATA_ROOT'):
        if not args.backup_dir.resolve().is_relative_to(Path(os.environ['PCT_DATA_ROOT']).resolve()):
            parser.error('Il backup deve rimanere nel volume dati persistente.')
    # La procedura nativa verifica firma dello schema e backup prima del DDL.
    subprocess.run([sys.executable, '-m', 'tools.prepare_document_ai_schema',
        '--tenant-registry', str(registry_path), '--backup-dir', str(args.backup_dir / 'documenti')], check=True)
    from pct.document_intelligence.repository import DocumentAIRepository
    from pct.registro_letture.event_retry import recover_prepared_schema_failures
    from pct.registro_letture.repository import _adesso
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from web.app import create_app
    from web.services.document_intelligence_runtime import fascicoli_db_path
    from web.services.fascicoli_list_events_runtime import registry_outbox_writer
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from web.services.storage_runtime import get_request_studio_db
    app = create_app({'SCHEDULER_ONLY': True, 'DISABLE_SCHEDULER': True,
                      'TENANTS_REGISTRY': str(registry_path), 'MULTI_TENANT': True})
    manager, owners = _targets(app, '')
    if Path(manager.registry_path).resolve() != registry_path:
        raise RuntimeError('Registro degli studi discordante: nessuna coda modificata.')
    for slug, owner in owners.items():
        with _tenant_context(app, manager, owner, slug):
            try:
                registry = registro_corrente(sola_lettura=True)
            except FileNotFoundError:
                print(json.dumps(dict(tenant=slug, status='registro_non_provisionato')), flush=True)
                continue
            changed = _con_riprova(lambda: prepare_queue(registry, tenant_corrente(), args.backup_dir / slug / 'letture'))
            anchor = fascicoli_db_path()
            # Riscontro SELECT dello schema corretto, senza caricare i fascicoli.
            DocumentAIRepository.from_fascicoli_db(anchor,
                structured_db=get_request_studio_db(anchor), initialize_schema=False)
            recovered = _con_riprova(lambda: _recupera(registry, registry_outbox_writer,
                                                       recover_prepared_schema_failures, _adesso))
            print(json.dumps(dict(tenant=slug, changed=changed, recovered=len(recovered))), flush=True)


if __name__ == '__main__':
    main()
