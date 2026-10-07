"""Migrazione esplicita SQLite dei piani verificati: nessun import runtime.

Richiede tutti i writer applicativi fermi prima di qualsiasi scrittura.
I piani, originali e stati SQL vengono ricontrollati per tutte le caselle.
Un catalogo già inizializzato si conserva soltanto se coincide col piano;
nessun overwrite o ripristino automatico di dati operativi è previsto.
"""
import argparse
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace

from pct.email_mailbox_repository import EmailMailboxRepository, KINDS


def load_planner():
    path = Path(__file__).with_name('plan-mailbox-reconciliation.py')
    spec = importlib.util.spec_from_file_location('mailbox_reconciliation_plan', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def offline_writers():
    result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}\t{{.Label "com.docker.compose.service"}}'],
                            capture_output=True, check=True, text=True)
    writers = [line for line in result.stdout.splitlines()
               if line.rsplit('\t', 1)[-1] in {'app', 'scheduler-worker', 'ocr-worker'}
               or line.split('\t', 1)[0] == 'iusentra-app']
    if writers:
        raise RuntimeError('Migrazione non applicata: i processi applicativi devono essere fermi.')


def tenant_roots(registry, data_root):
    entries = json.loads(registry.read_text(encoding='utf-8'))
    if not isinstance(entries, dict):
        raise ValueError('Registro studi non valido.')
    roots = {}
    for entry in entries.values():
        slug = str(entry.get('slug') or '')
        storage = str(entry.get('storage_key') or slug)
        config = entry.get('db_config', entry.get('database', {}))
        mode = str(config.get('mode', 'SQLITE') if isinstance(config, dict) else config).upper()
        if mode not in {'SQLITE', 'SQLITE3', 'SQLITE_LOCAL'}:
            raise ValueError('Questa procedura migra soltanto studi SQLite configurati esplicitamente.')
        if not slug or not storage or slug in roots:
            raise ValueError('Identità studio non valida o duplicata.')
        stored = Path(storage)
        if stored.is_absolute():
            relative = stored.relative_to('/data/tenants')
        elif stored.name == storage and storage not in {'.', '..'}:
            relative = stored
        else:
            raise ValueError('Percorso studio non valido.')
        root = (data_root / 'tenants' / relative).resolve()
        root.relative_to((data_root / 'tenants').resolve())
        if root in roots.values():
            raise ValueError('Due studi condividono il percorso della casella.')
        roots[slug] = root
    return roots


def validate_plans(plan_dir, roots, planner, data_root):
    expected = {(tenant, kind) for tenant in roots for kind in KINDS}
    prepared, seen = [], set()
    for path in sorted(plan_dir.glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        key = (document['tenant_key'], document['mailbox_kind'])
        if key not in expected or key in seen:
            raise ValueError('Piano duplicato o estraneo al registro studi.')
        seen.add(key)
        tenant, kind = key
        root = roots[tenant]
        saved_root = Path(document['tenant_root'])
        if saved_root.relative_to('/data/tenants') != root.relative_to(data_root / 'tenants'):
            raise ValueError('Il piano non appartiene al percorso registrato dello studio.')
        filename = 'casella.json' if kind == 'pec' else 'ordinaria.json'
        if planner.fingerprint(document['records']) != document['target_sha256']:
            raise ValueError('Il contenuto del piano non coincide con la sua impronta.')
        fresh = planner.plan(root, KINDS[kind], filename, tenant)
        for field in ('primary_sha256', 'sql_read_states_sha256', 'target_sha256'):
            if fresh[field] != document[field]:
                raise ValueError('La fonte primaria o gli originali sono cambiati: rigenerare il piano.')
        with sqlite3.connect((root / 'studio.db').as_uri() + '?mode=ro', uri=True) as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='email_mailbox_bootstrap'").fetchone()
            initialized = bool(exists and conn.execute(
                'SELECT 1 FROM email_mailbox_bootstrap WHERE tenant_key=? AND mailbox_kind=?', key).fetchone())
            if initialized:
                actual = EmailMailboxRepository(SimpleNamespace(conn=conn), tenant, kind).load(update_original=False)
                if planner.fingerprint(actual) != document['target_sha256']:
                    raise ValueError('Catalogo già operativo diverso dal piano: nessuna sostituzione consentita.')
            elif fresh['mirror_sha256'] != document['mirror_sha256']:
                raise ValueError('La copia storica è cambiata: rigenerare il piano.')
        prepared.append((document, root, filename, initialized))
    if seen != expected:
        raise ValueError('I piani non coprono tutte le caselle degli studi configurati.')
    return prepared


def verify_backup(manifest_path, prepared):
    document = json.loads(manifest_path.read_text(encoding='utf-8'))
    entries = {entry['file']: entry for entry in document['files']}
    expected = {hashlib.sha256(plan['tenant_root'].encode()).hexdigest()[:16] + '-' + suffix + '.db'
                for plan, _, _, _ in prepared for suffix in ('core', 'letture')}
    if set(entries) != expected or len(entries) != len(document['files']):
        raise ValueError('Backup non completo o non appartenente ai piani degli studi.')
    for name, entry in entries.items():
        if Path(name).name != name or entry.get('source_of_truth') != 'sqlite' or entry.get('quick_check') != 'ok':
            raise ValueError('Backup non verificato della fonte SQL.')
        snapshot = manifest_path.parent / name
        if snapshot.stat().st_size != entry['bytes']:
            raise ValueError('Dimensione dello snapshot non corrispondente al backup.')
        digest = hashlib.sha256()
        with snapshot.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != entry['sha256']:
            raise ValueError('Impronta dello snapshot non corrispondente al backup.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan-dir', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--backup-manifest', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        offline_writers()
    planner = load_planner()
    prepared = validate_plans(args.plan_dir, tenant_roots(args.registry, args.data_root.resolve()), planner,
                              args.data_root.resolve())
    if not args.apply:
        print(json.dumps({'read_only': True, 'source_of_truth': 'sqlite', 'plans_validated': len(prepared)}))
        return
    verify_backup(args.backup_manifest, prepared)
    offline_writers()
    # La verifica di snapshot grandi può richiedere tempo: ricontrolla tutte
    # le fonti immediatamente prima della prima scrittura, senza fidarti
    # della fotografia precedente al controllo delle impronte.
    prepared = validate_plans(args.plan_dir, tenant_roots(args.registry, args.data_root.resolve()), planner,
                              args.data_root.resolve())
    for document, root, filename, initialized in prepared:
        with sqlite3.connect(root / 'studio.db', timeout=10) as conn:
            repository = EmailMailboxRepository(SimpleNamespace(conn=conn), document['tenant_key'],
                                                 document['mailbox_kind'], root / 'email' / filename)
            if not initialized:
                repository.ensure_schema()
                repository.initialize(document['records'], source_of_truth='controlled_source_reconciliation')
            actual = repository.load(update_original=False)
            if planner.fingerprint(actual) != document['target_sha256']:
                raise RuntimeError('Verifica finale del catalogo SQL non riuscita: mantenere i processi fermi.')
            repository.export_mirror()
            print(json.dumps({'source_of_truth': 'sqlite', 'mailbox_kind': document['mailbox_kind'],
                              'records': len(actual), 'target_sha256': document['target_sha256'],
                              'already_initialized': initialized, 'verified': True}))


if __name__ == '__main__':
    main()
