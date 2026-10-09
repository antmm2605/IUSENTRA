"""Adozione esplicita e puntuale della prima nota; nessuna scansione documentale."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace

from pct.prima_nota_repository import PrimaNotaRepository, validate_legacy_payload


def read_source(path):
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return {}, hashlib.sha256(('absent:' + str(path)).encode()).hexdigest(), None
    return validate_legacy_payload(json.loads(content.decode('utf-8'))), hashlib.sha256(content).hexdigest(), content


def canonical_sql_anchor(config):
    # Il JSON contabile è una fonte da adottare, non la radice del database.
    # Usa lo stesso anchor canonico delle procedure native clienti/fascicoli.
    anchor = config('CLIENTI_DB')
    if not anchor:
        raise RuntimeError('Riferimento SQL canonico dello studio assente.')
    return str(anchor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-dir', default='')
    parser.add_argument('--writers-drained', action='store_true', help='Produttori precedenti arrestati e sostituiti con il runtime governato.')
    args = parser.parse_args()
    if args.apply and not args.backup_dir:
        parser.error('Occorre una directory nuova per il backup coerente.')
    if args.apply and not args.writers_drained:
        parser.error('Adozione sospesa: occorre confermare il drain dei produttori precedenti.')
    from web.app import create_app
    from web.helpers import _cfg
    from web.services.storage_runtime import get_request_storage_runtime, _sqlite_runtime_is_unseeded
    from web.services.prima_nota_runtime import get_existing_prima_nota_database
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    # Profilo nativo senza wiring web/OCR o governance di avvio: solo contesto e repository.
    app = create_app({'SCHEDULER_ONLY': True})
    manager, targets = _targets(app, args.tenant)
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('a', encoding='utf-8') as log:
        for slug, studio in targets.items():
            with _tenant_context(app, manager, studio, slug), ExitStack() as resources:
                source = Path(_cfg('PRIMA_NOTA_DB'))
                payload, fingerprint, content = read_source(source)
                anchor = canonical_sql_anchor(_cfg)
                profile = get_request_storage_runtime(anchor)
                if profile.uses_sqlite:
                    canonical = Path(profile.studio_db_path)
                    if not canonical.is_file() or _sqlite_runtime_is_unseeded(canonical, Path(anchor)):
                        raise RuntimeError('Archivio SQL canonico assente o non inizializzato: nessun bootstrap dal JSON.')
                    if not args.apply:
                        connection = sqlite3.connect(f'file:{canonical.as_posix()}?mode=ro', uri=True)
                        resources.callback(connection.close)
                        db = SimpleNamespace(conn=connection, db_path=str(canonical))
                    else:
                        db = get_existing_prima_nota_database(anchor)
                        resources.callback(db.chiudi)
                else:
                    db = get_existing_prima_nota_database(anchor)
                    resources.callback(db.chiudi)
                if db is None:
                    raise RuntimeError('Profilo SQL dello studio necessario: nessuna adozione.')
                # Un mirror non vuoto, con fonte assente, non autorizza un archivio vuoto.
                if content is None:
                    rows = db.conn.execute(
                        "SELECT COUNT(*) FROM moduli_json_records WHERE modulo IN ('prima_nota','prima-nota')"
                    ).fetchone()
                    if rows and int(rows[0]):
                        raise RuntimeError('Fonte storica assente ma mirror non vuoto: recupero necessario.')
                result = {'tenant': slug, 'source': str(source), 'source_sha256': fingerprint,
                          'source_exists': content is not None, 'records': len(payload), 'apply': args.apply}
                result['sql_path'] = str(getattr(db, 'db_path', 'postgresql'))
                if args.apply:
                    from pct.prima_nota_transition import prima_nota_source_lock, prepare_transition_locked, commit_transition_locked
                    from scripts.postgres_backup import backup_postgres
                    from deploy.hetzner.backup_structured import _backup_sqlite
                    # Il lock deve coprire l'intero backup e la conferma SQL, non solo l'hash.
                    # --apply rimane bloccato finché tutti i produttori runtime lo rispettano.
                    with prima_nota_source_lock(source):
                        current_payload, current_fingerprint, current_content = read_source(source)
                        if current_fingerprint != fingerprint:
                            raise RuntimeError('La fonte è cambiata prima del backup: adozione sospesa.')
                        destination = Path(args.backup_dir) / slug
                        resume = destination.exists()
                        if resume:
                            manifest = json.loads((destination / 'source-manifest.json').read_text(encoding='utf-8'))
                            if manifest.get('source_sha256') != current_fingerprint or manifest.get('tenant') != slug:
                                raise RuntimeError('Backup esistente discordante: adozione sospesa.')
                            backup_file = destination / ('studio-prima-nota.dump' if getattr(db,'backend_kind','') == 'postgresql' else 'studio-prima-nota.db')
                            if (not backup_file.is_file() or backup_file.stat().st_size == 0
                                    or hashlib.sha256(backup_file.read_bytes()).hexdigest() != manifest.get('backup',{}).get('sha256')):
                                raise RuntimeError('Backup coerente non disponibile: recupero necessario.')
                            result['backup'] = manifest['backup']
                        else:
                            destination.mkdir(parents=True, exist_ok=False)
                        if not resume and getattr(db, 'backend_kind', '') == 'postgresql':
                            result['backup'] = backup_postgres(db.dsn, destination / 'studio-prima-nota.dump')
                        elif not resume:
                            source_db = Path(db.db_path)
                            if shutil.disk_usage(destination).free < source_db.stat().st_size + 1024**3:
                                raise RuntimeError('Spazio insufficiente per il backup coerente.')
                            result['backup'] = _backup_sqlite(source_db, destination / 'studio-prima-nota.db')
                        if current_content is not None and not resume:
                            (destination / 'prima_nota-original.json').write_bytes(current_content)
                        if not resume:
                            (destination / 'source-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                        # Rileva anche un produttore non ancora aggiornato: non prova da solo la barriera.
                        _, final_fingerprint, _ = read_source(source)
                        if final_fingerprint != current_fingerprint:
                            raise RuntimeError('La fonte è cambiata durante il backup: adozione sospesa.')
                        tenant_key = slug if studio is not None else 'studio'
                        prepare_transition_locked(source, tenant=tenant_key, source_sha256=current_fingerprint)
                        repo = PrimaNotaRepository(db, tenant_key, actor_key="migrazione-prima-nota")
                        repo.ensure_schema()
                        # I trigger della nuova tabella appartengono alla migrazione,
                        # non al primo caricamento della pagina o a un comando utente.
                        from pct.operational_live import ensure_live_schema
                        ensure_live_schema(db.conn, postgres=getattr(db, 'backend_kind', '') == 'postgresql')
                        adopted = repo.initialize(current_payload, source_sha256=current_fingerprint, backup_reference=str(destination))
                        state = db.conn.execute('SELECT source_sha256 FROM prima_nota_state WHERE tenant_key=?', (tenant_key,)).fetchone()
                        if state is None or state[0] != current_fingerprint:
                            raise RuntimeError('Impronta del marker SQL discordante: transizione non confermata.')
                        adoption = db.conn.execute('SELECT actor_key,after_json,created_at FROM prima_nota_audit WHERE tenant_key=? AND revision=0 AND record_key=?',(tenant_key,'__adoption')).fetchone()
                        if adoption is None:
                            raise RuntimeError('Audit di adozione assente: transizione non confermata.')
                        identity = 'prima-nota-adoption:' + hashlib.sha256((tenant_key + current_fingerprint).encode()).hexdigest()
                        values = (identity,adoption[2],adoption[0],adoption[0],'prima_nota.adozione','prima_nota',tenant_key,adoption[1],'','OK')
                        db.conn.execute('INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',values)
                        audit = db.conn.execute('SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito FROM audit_log WHERE id=?',(identity,)).fetchone()
                        if audit is None or tuple(audit[i] for i in range(10)) != values:
                            db.conn.rollback()
                            raise RuntimeError('Audit generale di adozione discordante.')
                        db.conn.commit()
                        commit_transition_locked(source, tenant=tenant_key, source_sha256=current_fingerprint)
                        result['sql_records'] = len(adopted)
                log.write(json.dumps(result, ensure_ascii=False) + '\n')
                log.flush()
                print(json.dumps({'tenant': slug, 'apply': args.apply, 'records': len(payload)}), flush=True)


if __name__ == '__main__':
    main()
