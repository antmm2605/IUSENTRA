"""Collega tutti i produttori nativi al medesimo archivio dopo l'adozione.

Il file contiene solo il collegamento, mai scadenze o credenziali. Un fence
preparato impedisce il ritorno al JSON anche dopo un'interruzione.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path


def owner_path(source):
    return Path(str(Path(source).resolve()) + '.sql-owner')


@lru_cache(maxsize=32)
def _existing_sqlite(path):
    from pct.storage import StudioDB
    return StudioDB(path, initialize_schema=False)


def backend_identity(database):
    if getattr(database, 'backend_kind', '') == 'postgresql':
        from psycopg2.extensions import parse_dsn
        parameters = parse_dsn(database.dsn)
        value = {key: parameters.get(key, '') for key in ('host', 'hostaddr', 'port', 'dbname', 'user', 'options')}
        return 'postgresql:' + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return str(Path(database.db_path).resolve())


def read_owner(source):
    try:
        value = json.loads(owner_path(source).read_bytes())
    except FileNotFoundError:
        return None
    except (ValueError, OSError) as exc:
        raise RuntimeError('Collegamento SQL dello scadenziario non leggibile: recupero necessario.') from exc
    fields = {'version', 'source', 'tenant', 'backend', 'studio_db', 'registry', 'sha256', 'backup'}
    if (not isinstance(value, dict) or set(value) != fields or value['version'] != 1
            or value['source'] != str(Path(source).resolve())
            or any(not isinstance(value[key], str) or not value[key] for key in fields - {'version', 'registry'})
            or not isinstance(value['registry'], str)):
        raise RuntimeError('Collegamento SQL dello scadenziario discordante: nessun ritorno al JSON.')
    return value


def resolve_owner(source, database=None):
    owner = read_owner(source)
    if owner is None:
        return database, False
    if database is None:
        if owner['backend'].startswith('postgresql:'):
            from pct.tenant import GestioneTenant
            from pct.core_storage_backend import build_core_storage_backend
            registry = GestioneTenant(registry_path=owner['registry'])
            studio = registry.get(owner['tenant'])
            if studio is None:
                raise RuntimeError('Studio proprietario dello scadenziario non disponibile.')
            paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
            if str(Path(paths['SCADENZIARIO_DB']).resolve()) != owner['source']:
                raise RuntimeError('Fonte dello scadenziario appartenente a uno studio diverso.')
            database = build_core_storage_backend(studio.database, studio_db_path=paths['STUDIO_DB'], initialize_schema=False)
        else:
            if not Path(owner['studio_db']).is_file():
                raise RuntimeError('Archivio SQL dello scadenziario assente: recupero necessario.')
            database = _existing_sqlite(owner['studio_db'])
    if database is None or backend_identity(database) != owner['backend']:
        raise RuntimeError('Archivio dello scadenziario diverso dal proprietario confermato.')
    try:
        # Non interrogare una tabella assente: su PostgreSQL l'errore
        # abortirebbe la transazione del chiamante impedendo la ripresa.
        exists = database.conn.execute("SELECT to_regclass('scadenziario_sql_state')" if
                    getattr(database, 'backend_kind', '') == 'postgresql' else
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='scadenziario_sql_state'").fetchone()
        if not exists or not exists[0]:
            raise RuntimeError('Conferma SQL non ancora registrata.')
        state = database.conn.execute('SELECT source_sha256 FROM scadenziario_sql_state WHERE tenant=? AND source=?',
                                      (owner['tenant'], owner['source'])).fetchone()
    except Exception as exc:
        raise RuntimeError('Adozione SQL dello scadenziario non confermata: recupero necessario.') from exc
    if state is None or state[0] != owner['sha256']:
        raise RuntimeError('Adozione SQL dello scadenziario non confermata: recupero necessario.')
    return database, True
