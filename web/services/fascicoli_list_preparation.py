"""Preparazione esplicita con backup nativi, prova delle fonti e lotti finiti."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from pct.fascicoli_list_migration import begin, rebuild_batch, install_migration_schema
from pct.fascicoli_list_query import install_schema, install_source_events, install_registry_events
from scripts.query_index_backup import verified_backup
from web.services.fascicoli_list_runtime import catalog_exists, native_list_repository
from web.services.fascicoli_list_events_runtime import registry_outbox_writer, resume_owner_events
from web.services.fascicoli_list_writer import FascicoliListWriter
from web.services.registro_letture_runtime import registro_corrente, connessione_registro


def _digest(rows):
    digest = hashlib.sha256()
    for value in sorted(json.dumps(dict(row), sort_keys=True, ensure_ascii=False, default=str) for row in rows):
        digest.update(value.encode('utf-8'))
        digest.update(b'\n')
    return digest.hexdigest()


def source_fingerprints(database, registry, native, tenant):
    result = {'fascicoli': _digest(database.fetchall_readonly(native._select_elenco_sql()))}
    for table in ('parcelle', 'scadenze'):
        result[table] = _digest(database.conn.execute('SELECT * FROM ' + table).fetchall())
    with connessione_registro(registry) as conn:
        result['letture_fatti'] = _digest(conn.execute('SELECT * FROM letture_fatti WHERE tenant_id=?', (tenant,)).fetchall())
        result['letture_oggetti'] = _digest(conn.execute('SELECT * FROM letture_oggetti WHERE tenant_id=?', (tenant,)).fetchall())
    return result


def _backup_pair(database, registry, native, tenant, destination):
    destination = Path(destination)
    marker = destination / 'catalog-source-proof.json'
    if marker.is_file():
        proof = json.loads(marker.read_text(encoding='utf-8'))
        if proof.get('tenant') != tenant or proof.get('before') != proof.get('after'):
            raise ValueError('Prova della coppia di backup non confermata.')
    else:
        proof = {'tenant': tenant, 'before': source_fingerprints(database, registry, native, tenant)}
    core_path, core_digest = verified_backup(database, destination / 'core')
    with connessione_registro(registry) as conn:
        adapter = SimpleNamespace(backend_kind='postgresql' if registry.backend_kind == 'postgres' else 'sqlite',
            dsn=registry.postgres_dsn, db_path=registry.db_path, conn=conn)
        registry_path, registry_digest = verified_backup(adapter, destination / 'registro')
    if not marker.is_file():
        proof['after'] = source_fingerprints(database, registry, native, tenant)
        proof.update(core_backup=str(core_path), core_sha256=core_digest,
                     registry_backup=str(registry_path), registry_sha256=registry_digest,
                     scope='SQL proprietario e fonti del catalogo, nessuna lettura dei file documentali')
        marker.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
        marker.chmod(0o600)
    if proof['before'] != proof['after']:
        raise RuntimeError('Fonti cambiate durante il backup: copie preservate, preparazione non applicata.')
    if proof['core_sha256'] != core_digest or proof['registry_sha256'] != registry_digest:
        raise ValueError('Impronte dei backup non concordanti con il registro della preparazione.')
    return marker, hashlib.sha256(marker.read_bytes()).hexdigest()


def prepare_catalog(database, *, tenant, anchor, destination, limit=100, max_batches=100):
    if not tenant or type(max_batches) is not int or not 1 <= max_batches <= 1000:
        raise ValueError('Studio e budget finito della preparazione sono obbligatori.')
    try:
        registry = registro_corrente(sola_lettura=True)
    except FileNotFoundError:
        # Solo la preparazione esplicita può creare il registro vuoto di uno
        # studio nuovo; la GET e il worker consultivo non inizializzano fonti.
        registry = registro_corrente()
    native = native_list_repository(database, anchor)
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    conn = database.conn
    target = getattr(database, 'raw_conn', None) or conn
    if catalog_exists(conn, 'fascicoli_list_owner', postgres=postgres):
        owner = conn.execute('SELECT tenant_key,version FROM fascicoli_list_owner WHERE singleton=1').fetchone()
        if owner is not None and owner[0] != tenant:
            raise ValueError('Catalogo attribuito a un altro studio.')
        if owner is not None and owner[1] == 1:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            from pct.fascicoli_list_clock import install_clock_schema, initialize_clock
            has_clock = catalog_exists(conn, 'fascicoli_list_clock', postgres=postgres)
            clock = conn.execute('SELECT event_day FROM fascicoli_list_clock WHERE tenant_key=?', (tenant,)).fetchone() if has_clock else None
            if clock is None:
                verified_backup(database, Path(destination) / 'clock-guard')
                install_clock_schema(conn)
                previous = conn.execute("SELECT MAX(updated_at) FROM fascicoli_list_migrations WHERE tenant_key=? AND phase='COMPLETED'", (tenant,)).fetchone()
                day = datetime.fromisoformat(previous[0]).astimezone(ZoneInfo('Europe/Rome')).date().isoformat() if previous and previous[0] else '1970-01-01'
                initialize_clock(conn, tenant, day)
                target.commit()
            for _ in range(max_batches):
                result = resume_owner_events(database, tenant, anchor, limit=limit)
                if not result['delivered']:
                    break
            from web.services.fascicoli_list_runtime import registry_ready
            from pct.fascicoli_list_query import FascicoliListQuery
            FascicoliListQuery(database, tenant)._ready()
            registry_ready(tenant)
            return dict(phase='COMPLETED', prepared=False)
    proof_path, proof_digest = _backup_pair(database, registry, native, tenant, destination)
    try:
        install_schema(conn, postgres=postgres)
        install_migration_schema(conn)
        state = begin(conn, tenant=tenant, backup_reference=str(proof_path), backup_sha256=proof_digest,
                      actor='fascicoli-list-migration')
        install_source_events(conn, postgres=postgres)
        target.commit()
        with registry_outbox_writer(registry) as source:
            install_registry_events(source, tenant=tenant, postgres=registry.backend_kind == 'postgres')
        if state['phase'] == 'ROWS':
            # Una ripresa deve applicare anche cancellazioni o inserimenti
            # avvenuti dopo il cursore, prima del controllo finale delle chiavi.
            for _ in range(max_batches):
                delivered = resume_owner_events(database, tenant, anchor, limit=limit)
                if not delivered['delivered']:
                    break
        writer = FascicoliListWriter(database, tenant, native)
        processed = 0
        for _ in range(max_batches):
            if state['phase'] == 'COMPLETED':
                break
            state = rebuild_batch(conn, tenant=tenant, migration_id=state['id'], actor='fascicoli-list-migration',
                phase=state['phase'], after_key=state['after_key'], project=writer.project_batch, limit=limit)
            target.commit()
            processed += state['processed']
        if state['phase'] == 'COMPLETED':
            for _ in range(max_batches):
                result = resume_owner_events(database, tenant, anchor, limit=limit)
                if not result['delivered']:
                    break
            writer.repository._ready()
            from web.services.fascicoli_list_runtime import registry_ready
            registry_ready(tenant)
        return dict(migration_id=state['id'], phase=state['phase'], prepared=True,
                    processed_this_run=processed, backup_sha256=proof_digest)
    except Exception:
        target.rollback()
        raise
