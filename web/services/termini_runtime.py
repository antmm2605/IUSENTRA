"""Selezione SQL dopo adozione riscontrata, senza DDL o import nelle GET."""
from pathlib import Path
import sqlite3

from flask import g

from pct.termini_processuali import DeadlinePracticeRepository
from pct.termini_processuali_repository import DeadlineSqlRepository
from pct.termini_transition import read_marker


def postgres_dsn():
    from pct.storage_postgres import build_postgres_dsn
    config = getattr(getattr(g, "tenant", None), "database", None)
    if config is None:
        raise RuntimeError("Configurazione SQL dello studio assente per i termini.")
    return build_postgres_dsn(host=config.host, port=config.porta_effettiva or 5432,
                             db_name=config.db_name, user=config.utente, password=config.password, ssl=config.ssl)


def probe_adoption(profile, tenant_key):
    if profile.uses_sqlite:
        path = Path(profile.studio_db_path).resolve()
        if not path.is_file():
            raise RuntimeError("Archivio SQL dello studio assente: adozione dei termini non determinabile.")
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='termini_state'").fetchone()
            return connection.execute("SELECT source_sha256,backup_reference FROM termini_state WHERE tenant_key=?",
                                      (tenant_key,)).fetchone() if table else None
        finally:
            connection.close()
    if profile.effective_mode != "POSTGRESQL":
        raise RuntimeError("Repository SQL dei termini non configurato.")
    import psycopg2
    connection = psycopg2.connect(postgres_dsn())
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('termini_state')")
            if cursor.fetchone()[0] is None:
                return None
            cursor.execute("SELECT source_sha256,backup_reference FROM termini_state WHERE tenant_key=%s", (tenant_key,))
            return cursor.fetchone()
    finally:
        connection.close()


def open_database(profile):
    existing = g.get("_termini_owned_database")
    if existing is not None:
        return existing
    if profile.uses_sqlite:
        from pct.storage import StudioDB
        database = StudioDB(profile.studio_db_path, initialize_schema=False)
    elif profile.effective_mode == "POSTGRESQL":
        from pct.storage_postgres import PostgresStudioDB
        database = PostgresStudioDB(postgres_dsn(), initialize_schema=False)
    else:
        raise RuntimeError("Repository SQL dei termini non configurato.")
    g._termini_owned_database = database
    return database


def close_database():
    database = g.pop("_termini_owned_database", None)
    if database is not None:
        database.chiudi()


def open_termini_runtime(source, *, anchor, tenant_key, actor_key, get_profile,
                         probe=probe_adoption, get_database=open_database):
    if not anchor or not tenant_key:
        raise RuntimeError("Contesto dello studio dei termini incompleto.")
    profile = get_profile(str(anchor))
    if profile.tenant_slug and profile.tenant_slug != tenant_key:
        raise RuntimeError("Profilo SQL di altro studio: accesso ai termini sospeso.")
    marker = read_marker(source)
    adoption = probe(profile, tenant_key)
    if marker is None:
        if adoption is not None:
            raise RuntimeError("Segnale di transizione dei termini assente dopo adozione SQL.")
        # Solo archivio non ancora adottato: questo ramo sarà dismesso dalla
        # migrazione esplicita. Non è recupero di un guasto SQL.
        return DeadlinePracticeRepository.json(source)
    if marker["tenant"] != tenant_key or marker["phase"] != "committed":
        raise RuntimeError("Transizione dei termini non confermata per lo studio corrente.")
    if adoption is None or adoption[0] != marker["source_sha256"] or not str(adoption[1] or "").strip():
        raise RuntimeError("Adozione SQL dei termini discordante: archivio storico preservato.")
    database = get_database(profile)
    if database is None:
        raise RuntimeError("Repository SQL dei termini indisponibile.")
    return DeadlineSqlRepository(database, tenant_key, source=source,
                                 actor_key=actor_key, expected_adoption=adoption)
