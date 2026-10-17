"""Migrazione esplicita delle proposte storiche, con backup e fonte immutata.

Eseguire soltanto dopo l'arresto dei vecchi produttori JSON. Nessuna GET
richiama questa procedura; il JSON originale resta conservato integralmente.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pct.tracking_passivo_sql import SCHEMA, decode
from pct.timesheet_sql_writer import TimesheetConflict
from scripts.query_index_backup import verified_backup



def migration_ready(database, source):
    """Controllo consultivo, senza inizializzare schema o leggere tutto l'archivio SQL."""
    source = Path(source).resolve()
    rows = database.fetchall_readonly("SELECT valore FROM _meta WHERE chiave='tracking_passivo_sql_source'")
    if not rows:
        return False
    digest = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else 'absent'
    if json.loads(rows[0]['valore']) != dict(source=str(source), sha256=digest):
        raise TimesheetConflict('Fonte JSON cambiata dopo il passaggio a SQL: verifica necessaria.')
    database.fetchall_readonly('SELECT id FROM time_tracking_proposals LIMIT 0')
    return True


def migrate(database, source, backup_dir):
    source, backup_dir = Path(source).resolve(), Path(backup_dir).resolve()
    content = source.read_bytes() if source.is_file() else None
    digest = hashlib.sha256(content).hexdigest() if content is not None else 'absent'
    raw = json.loads(content.decode('utf-8')) if content is not None else {}
    if not isinstance(raw, dict):
        raise ValueError('Archivio storico delle proposte non valido: nessun dato ignorato.')
    keys = set()
    for key, value in raw.items():
        if not isinstance(value, dict) or value.get('id') != key:
            raise ValueError('Identificativo della proposta storica discordante.')
        required = ('id', 'chiave', 'stato', 'utente_id', 'fascicolo_id', 'inizio')
        if any(not isinstance(value.get(k), str) or not value[k].strip() for k in required):
            raise ValueError('Proposta storica priva di identità o provenienza.')
        if value['stato'] not in {'BOZZA', 'CONFERMATA', 'SCARTATA'} or value['chiave'] in keys:
            raise ValueError('Stato o chiave della proposta storica non validi.')
        keys.add(value['chiave'])
    snapshot, backup_hash = verified_backup(database, backup_dir / 'sql')
    if content is not None:
        original = backup_dir / 'tracking_passivo.original.json'
        if original.exists():
            if original.read_bytes() != content:
                raise TimesheetConflict('La copia storica appartiene a una fonte differente.')
        else:
            with original.open('xb') as handle:
                handle.write(content)
        if hashlib.sha256(original.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Copia della fonte non verificata: migrazione interrotta.')
    identity = dict(source=str(source), sha256=digest)
    report = dict(inserted=0, already_present=0, source=identity, backup=str(snapshot), backup_sha256=backup_hash)

    def write(conn, _):
        report.update(inserted=0, already_present=0)
        if getattr(database, 'raw_conn', None) is not None:
            conn.execute('SELECT pg_advisory_xact_lock(?)', (778215703,))
        previous = conn.execute("SELECT valore FROM _meta WHERE chiave='tracking_passivo_sql_source'").fetchone()
        if previous:
            if json.loads(previous[0]) != identity:
                raise TimesheetConflict('Fonte JSON cambiata dopo il passaggio a SQL: verifica necessaria.')
            report['already_present'] = len(raw)
            return
        for statement in SCHEMA.split(';'):
            if statement.strip():
                conn.execute(statement)
        from pct.operational_live import ensure_live_schema
        ensure_live_schema(conn, postgres=getattr(database, 'raw_conn', None) is not None)
        for value in raw.values():
            if value['stato'] == 'CONFERMATA':
                entry = conn.execute('SELECT id_utente,id_fascicolo FROM timesheet_entries WHERE id=?',
                                     (value.get('voce_timesheet_id'),)).fetchone()
                if entry is None or (entry['id_utente'], entry['id_fascicolo']) != (value['utente_id'], value['fascicolo_id']):
                    raise TimesheetConflict('Voce storica confermata non riscontrata nello stesso utente e fascicolo: verifica necessaria.')
            existing = conn.execute('SELECT * FROM time_tracking_proposals WHERE id=? OR chiave=?',
                                    (value['id'], value['chiave'])).fetchall()
            if existing:
                if len(existing) != 1 or decode(existing[0]) != value:
                    raise TimesheetConflict('Proposta SQL diversa dalla fonte storica: nessuna sovrascrittura.')
                report['already_present'] += 1
                continue
            conn.execute('INSERT INTO time_tracking_proposals (id,chiave,stato,utente_id,fascicolo_id,inizio,dati_json) VALUES (?,?,?,?,?,?,?)',
                         tuple(value[k] for k in ('id', 'chiave', 'stato', 'utente_id', 'fascicolo_id', 'inizio'))
                         + (json.dumps(value, ensure_ascii=False),))
            report['inserted'] += 1
        current = source.read_bytes() if source.is_file() else None
        if current != content:
            raise TimesheetConflict('Fonte modificata durante la migrazione: transazione annullata.')
        conn.execute("INSERT INTO _meta (chiave,valore) VALUES ('tracking_passivo_sql_source',?)",
                     (json.dumps(identity, sort_keys=True),))
        conn.execute('INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) VALUES (?,?,?,?,?,?,?,?,?,?)',
                     (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), 'migrazione_sql',
                      'Procedura esplicita', 'timesheet.proposte_adozione_sql', 'timesheet', source.parent.name,
                      json.dumps(dict(source=identity, inserted=report['inserted'], backup_sha256=backup_hash), ensure_ascii=False), '', 'OK'))
    database.salva_tabella('time_tracking_proposals', [None], write, delete_all=False)
    return report


def main():
    import argparse
    from pct.core_storage_backend import build_core_storage_backend
    from pct.tenant import DatabaseConfig
    from web.services.storage_runtime import _derive_studio_db_path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', default='all')
    parser.add_argument('--tenant-registry', type=Path)
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--writers-drained', action='store_true')
    args = parser.parse_args()
    if not args.check and (not args.writers_drained or not args.backup_dir):
        parser.error('Fermare i produttori JSON precedenti prima di applicare la migrazione.')
    if not args.check and Path('/.dockerenv').exists() and os.environ.get('PCT_DATA_ROOT'):
        if not args.backup_dir.resolve().is_relative_to(Path(os.environ['PCT_DATA_ROOT']).resolve()):
            parser.error('Il backup deve rimanere nel volume dati persistente.')
    if args.tenant_registry:
        from pct.tenant import GestioneTenant
        manager = GestioneTenant(registry_path=str(args.tenant_registry.resolve(strict=True)))
        owners = {studio.slug: studio for studio in manager.lista()
                  if args.tenant == 'all' or studio.slug == args.tenant}
        if not owners:
            raise RuntimeError('Nessuno studio selezionato per la preparazione.')
        app = None
    else:
        from scripts.backfill_archivio_batches import _targets
        from web.app import create_app
        app = create_app({'SCHEDULER_ONLY': True, 'DISABLE_SCHEDULER': True})
        manager, owners = _targets(app, '' if args.tenant == 'all' else args.tenant)
    ready = True
    for slug, studio in owners.items():
        paths = manager.percorsi_dati(slug, reconcile_aliases=False, ensure_baseline=False) if studio else app.config
        config = studio.database if studio else app.config.get('TENANT_DATABASE_CONFIG') or DatabaseConfig(mode='SQLITE')
        database = build_core_storage_backend(config, studio_db_path=str(paths.get('STUDIO_DB') or
            _derive_studio_db_path(paths['CLIENTI_DB'])), readonly=args.check, initialize_schema=False)
        if database is None:
            raise RuntimeError(f'Repository SQL non disponibile per lo studio {slug}.')
        try:
            source = Path(paths['TIMESHEET_DB']).parent / 'tracking_passivo.json'
            if args.check:
                current = migration_ready(database, source)
                ready = ready and current
                report = dict(ready=current)
            else:
                report = migrate(database, source, args.backup_dir / slug)
            print(json.dumps(dict(tenant=slug, **report), ensure_ascii=False))
        finally:
            database.chiudi()
    return 0 if ready else 2


if __name__ == '__main__':
    raise SystemExit(main())
