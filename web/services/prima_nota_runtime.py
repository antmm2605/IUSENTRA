"""Selezione governata Prima nota, senza migrazione o bootstrap nelle GET."""
from pathlib import Path
import sqlite3

from pct.prima_nota import GestionePrimaNota
from pct.prima_nota_transition import read_transition


def _read_adoption(connection, tenant_key, *, postgres=False):
    """Riscontro puntuale; una tabella assente non viene creata."""
    if postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('prima_nota_state')")
            if cursor.fetchone()[0] is None:
                return None
            cursor.execute('SELECT source_sha256,backup_reference FROM prima_nota_state WHERE tenant_key=%s', (tenant_key,))
            return cursor.fetchone()
    present = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prima_nota_state'").fetchone()
    if present is None:
        return None
    return connection.execute('SELECT source_sha256,backup_reference FROM prima_nota_state WHERE tenant_key=?', (tenant_key,)).fetchone()


def _postgres_request_dsn():
    from flask import g
    from pct.storage_postgres import build_postgres_dsn
    config = getattr(getattr(g, 'tenant', None), 'database', None)
    if config is None:
        raise RuntimeError('Configurazione PostgreSQL Prima nota assente.')
    return build_postgres_dsn(host=config.host, port=config.porta_effettiva or 5432,
                              db_name=config.db_name, user=config.utente,
                              password=config.password, ssl=config.ssl)


def get_existing_prima_nota_database(anchor):
    """Backend nativo della sola richiesta, senza bootstrap o cache globali."""
    from flask import g
    from web.services.storage_runtime import get_request_storage_runtime
    profile = get_request_storage_runtime(anchor)
    if profile.uses_sqlite:
        from pct.storage import StudioDB
        database = StudioDB(profile.studio_db_path, initialize_schema=False)
    elif profile.effective_mode == 'POSTGRESQL':
        from pct.storage_postgres import PostgresStudioDB
        database = PostgresStudioDB(_postgres_request_dsn(), initialize_schema=False)
    else:
        raise RuntimeError('Repository SQL Prima nota non configurato.')
    # Il teardown deve chiudere anche se lettura/validazione successive falliscono.
    g._prima_nota_owned_database = database
    return database


def close_prima_nota_database():
    from flask import g
    database = g.pop('_prima_nota_owned_database', None)
    if database is not None:
        database.chiudi()


def probe_prima_nota_adoption(profile, tenant_key):
    """Connessione di sola lettura separata dai factory che inizializzano schemi."""
    if profile.uses_sqlite:
        path = Path(profile.studio_db_path).resolve()
        if not path.is_file():
            raise RuntimeError('Archivio SQL Prima nota assente: adozione non determinabile.')
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
        try:
            return _read_adoption(connection, tenant_key)
        finally:
            connection.close()
    if profile.effective_mode != 'POSTGRESQL':
        raise RuntimeError('Archivio SQL Prima nota non configurato: adozione non determinabile.')
    import psycopg2
    connection = psycopg2.connect(_postgres_request_dsn(), connect_timeout=5)
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5000ms'")
        return _read_adoption(connection, tenant_key, postgres=True)
    finally:
        connection.rollback()
        connection.close()


def open_prima_nota_runtime(source, *, anchor, tenant_key, actor_key,
                           get_profile, get_database, probe_adoption=probe_prima_nota_adoption):
    """Il marker non sceglie tenant, database o attore: arrivano dal runtime."""
    marker = read_transition(source)
    if marker is None:
        if not anchor or not tenant_key:
            raise RuntimeError('Contesto Prima nota incompleto: adozione non determinabile.')
        profile = get_profile(str(anchor))
        profile_tenant = str(getattr(profile, 'tenant_slug', '') or '').strip()
        if profile_tenant and profile_tenant != tenant_key:
            raise RuntimeError('Profilo SQL di altro studio: accesso Prima nota sospeso.')
        if probe_adoption(profile, tenant_key) is not None:
            raise RuntimeError('Segnale di transizione Prima nota assente dopo adozione SQL: recupero necessario.')
        # Compatibilità prima dell'adozione esplicita, non fallback SQL.
        return GestionePrimaNota(str(source))
    if not tenant_key or marker['tenant'] != tenant_key:
        raise RuntimeError('Contesto studio discordante per la Prima nota: accesso sospeso.')
    if marker['phase'] != 'committed':
        raise RuntimeError('Transizione Prima nota non confermata: recupero necessario.')
    if not anchor:
        raise RuntimeError('Riferimento SQL canonico Prima nota assente.')
    profile = get_profile(str(anchor))
    profile_tenant = str(getattr(profile, 'tenant_slug', '') or '').strip()
    if profile_tenant and profile_tenant != tenant_key:
        raise RuntimeError('Profilo SQL di altro studio: accesso Prima nota sospeso.')
    if profile.uses_sqlite:
        from web.services.storage_runtime import _sqlite_runtime_is_unseeded
        database_path = Path(profile.studio_db_path)
        if not database_path.is_file() or _sqlite_runtime_is_unseeded(database_path, Path(anchor)):
            raise RuntimeError('Archivio SQL Prima nota assente o non inizializzato: nessun bootstrap.')
    database = get_database(str(anchor))
    if database is None:
        raise RuntimeError('Repository SQL Prima nota non disponibile: nessun ritorno al JSON.')
    state = database.conn.execute(
        'SELECT source_sha256,backup_reference FROM prima_nota_state WHERE tenant_key=?',
        (tenant_key,),
    ).fetchone()
    if state is None or state[0] != marker['source_sha256'] or not str(state[1] or '').strip():
        raise RuntimeError('Adozione SQL Prima nota discordante: recupero necessario.')
    return GestionePrimaNota(str(source), studio_db=database, tenant_key=tenant_key, actor_key=actor_key)


def riprendi_audit_prima_nota(app, *, limit=50):
    """Solo consegne pendenti degli studi attivi; nessuna lettura documentale."""
    from flask import g
    from web.helpers import _cfg
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context
    from pct.prima_nota_repository import PrimaNotaRepository
    from pct.tenant import GestioneTenant

    targets = _active_tenants(app) if app.config.get('MULTI_TENANT') else [None]
    manager = GestioneTenant(registry_path=app.config['TENANTS_REGISTRY']) if targets and targets[0] is not None else None
    totals = {'delivered':0,'failed':0}
    for studio in targets:
        slug = studio.slug if studio is not None else 'studio'
        with app.test_request_context('/__scheduler/prima-nota-audit'):
            if studio is not None:
                _attach_tenant_context(manager,studio)
            else:
                g.multi_tenant_enabled = False
                g.tenant_context_missing = False
                g.tenant_context_slug = ''
            marker = read_transition(_cfg('PRIMA_NOTA_DB'))
            if marker is None:
                continue
            if marker['tenant'] != slug or marker['phase'] != 'committed':
                raise RuntimeError('Adozione Prima nota non confermata: consegna sospesa.')
            try:
                database = get_existing_prima_nota_database(_cfg('CLIENTI_DB'))
                state = database.conn.execute('SELECT source_sha256 FROM prima_nota_state WHERE tenant_key=?',(slug,)).fetchone()
                if state is None or state[0] != marker['source_sha256']:
                    raise RuntimeError('Impronta Prima nota discordante: consegna sospesa.')
                result = PrimaNotaRepository(database,slug).retry_pending_audit(limit=limit)
                for key in totals:
                    totals[key] += result[key]
            finally:
                close_prima_nota_database()
    return totals
