"""Adozione esplicita dei modelli SQL; nessuna preparazione nelle consultazioni."""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from pct.template_atti_repository import GestioneTemplateRepository, derive_template_repository_db_path


def catalog_ready(db_path, *, postgres_dsn=''):
    path = derive_template_repository_db_path(str(db_path))
    if not postgres_dsn and not Path(path).is_file():
        return False
    repository = GestioneTemplateRepository(path, postgres_dsn=postgres_dsn,
                                            initialize_schema=False, read_only=True)
    try:
        with repository._connection() as conn:
            row = conn.execute("SELECT to_regclass('template_runtime_state')" if postgres_dsn else
                               "SELECT name FROM sqlite_master WHERE type='table' AND name='template_runtime_state'").fetchone()
            if not row or not row[0]:
                return False
        _items, revision = repository.read_runtime_snapshot()
        return revision is not None and repository._get_meta('runtime_snapshot_signature') == hashlib.sha256(revision.encode()).hexdigest()
    finally:
        if repository._postgres_backend:
            repository._postgres_backend.close()


def prepare_catalog(db_path, *, backup_dir, postgres_dsn='', writers_drained=False):
    """Richiede scrittori fermi, salva gli originali prima di usare il gestore nativo."""
    if catalog_ready(db_path, postgres_dsn=postgres_dsn):
        return dict(changed=False)
    if not writers_drained:
        raise RuntimeError('Prima della preparazione fermare gli scrittori dei modelli.')
    from pct.template_atti import GestioneTemplateAtti
    from scripts.query_index_backup import verified_backup

    source = Path(db_path).resolve()
    destination = Path(backup_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    # Copia immutabile del JSON storico, compresi metadati non interpretati.
    if source.is_file():
        content = source.read_bytes()
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ValueError('Archivio storico dei modelli non valido.')
        snapshot = destination / 'templates-original.json'
        if not snapshot.exists():
            with snapshot.open('xb') as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        if snapshot.read_bytes() != content:
            raise RuntimeError('Backup dei modelli diverso dalla fonte: preparazione sospesa.')
        digest = hashlib.sha256(content).hexdigest()
    else:
        digest = None
    path = derive_template_repository_db_path(str(source))
    revision = None
    if postgres_dsn or Path(path).is_file():
        repository = GestioneTemplateRepository(path, postgres_dsn=postgres_dsn,
                                                initialize_schema=False, read_only=True)
        try:
            with repository._connection() as conn:
                verified_backup(SimpleNamespace(conn=conn, db_path=path,
                    backend_kind=repository.backend_kind, dsn=postgres_dsn), destination / 'sql')
                present = conn.execute("SELECT to_regclass('template_runtime_state')" if postgres_dsn else
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='template_runtime_state'").fetchone()
            if present and present[0]:
                _, revision = repository.read_runtime_snapshot()
        finally:
            if repository._postgres_backend:
                repository._postgres_backend.close()
    if postgres_dsn and revision is None:
        repository = GestioneTemplateRepository(path, postgres_dsn=postgres_dsn)
        try:
            with repository._connection() as conn:
                existing = conn.execute("SELECT template_id FROM template_repository WHERE builtin=0 AND collezione<>?",
                                        ('Editor personale',)).fetchall()
            if existing:
                raise RuntimeError('Modelli PostgreSQL preesistenti senza snapshot: riconciliazione richiesta.')
            originals = list(raw.values()) if source.is_file() else []
            local = GestioneTemplateRepository(path, initialize_schema=False, read_only=True)
            if Path(path).is_file():
                local_items, local_revision = local.read_runtime_snapshot()
                if local_revision is not None:
                    originals = local_items
            repository.compare_and_save_runtime_state(originals, expected_json=None)
        finally:
            repository._postgres_backend.close()
    manager = GestioneTemplateAtti(str(source), postgres_dsn=postgres_dsn)
    try:
        if not catalog_ready(str(source), postgres_dsn=postgres_dsn):
            raise RuntimeError('Preparazione dei modelli non confermata.')
        return dict(changed=True, original_sha256=digest, templates=len(manager.tutti()))
    finally:
        if manager._repository._postgres_backend:
            manager._repository._postgres_backend.close()
