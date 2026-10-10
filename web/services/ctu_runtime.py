"""Selezione CTU governata: SQL solo dopo adozione esplicita riscontrata.

Nessun DDL o import nelle richieste; SQL indisponibile non riattiva il JSON.
Il wiring della route e la migrazione rimangono passaggi da accettare.
"""
from pathlib import Path
import sqlite3

from flask import g

from pct.ctu import GestioneCtu
from pct.ctu_repository import CtuRepository
from pct.ctu_transition import read_marker


def postgres_dsn():
    from pct.storage_postgres import build_postgres_dsn
    config = getattr(getattr(g, "tenant", None), "database", None)
    if config is None:
        raise RuntimeError("Configurazione SQL dello studio assente per gli incarichi CTU.")
    return build_postgres_dsn(host=config.host, port=config.porta_effettiva or 5432,
                              db_name=config.db_name, user=config.utente, password=config.password, ssl=config.ssl)


def probe_adoption(profile, tenant_key):
    if profile.uses_sqlite:
        path = Path(profile.studio_db_path).resolve()
        if not path.is_file():
            raise RuntimeError("Archivio SQL dello studio assente: adozione CTU non determinabile.")
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ctu_state'").fetchone()
            return connection.execute("SELECT source_sha256,backup_reference FROM ctu_state WHERE tenant_key=?", (tenant_key,)).fetchone() if table else None
        finally:
            connection.close()
    if profile.effective_mode != "POSTGRESQL":
        return None
    import psycopg2
    connection = psycopg2.connect(postgres_dsn())
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('ctu_state')")
            if cursor.fetchone()[0] is None:
                return None
            cursor.execute("SELECT source_sha256,backup_reference FROM ctu_state WHERE tenant_key=%s", (tenant_key,))
            return cursor.fetchone()
    finally:
        connection.close()


def open_database(profile):
    if profile.uses_sqlite:
        from pct.storage import StudioDB
        database = StudioDB(profile.studio_db_path, initialize_schema=False)
    elif profile.effective_mode == "POSTGRESQL":
        from pct.storage_postgres import PostgresStudioDB
        database = PostgresStudioDB(postgres_dsn(), initialize_schema=False)
    else:
        raise RuntimeError("Repository SQL CTU non configurato.")
    g._ctu_owned_database = database
    return database


def close_database():
    database = g.pop("_ctu_owned_database", None)
    if database is not None:
        database.chiudi()


def open_ctu_runtime(source, *, anchor, tenant_key, actor_key, get_profile,
                     probe=probe_adoption, get_database=open_database):
    if not anchor or not tenant_key:
        raise RuntimeError("Contesto dello studio CTU incompleto.")
    profile = get_profile(str(anchor))
    if profile.tenant_slug and profile.tenant_slug != tenant_key:
        raise RuntimeError("Profilo SQL di altro studio: accesso CTU sospeso.")
    marker = read_marker(source)
    if marker is None:
        if probe(profile, tenant_key) is not None:
            raise RuntimeError("Segnale di transizione CTU assente dopo adozione SQL: recupero necessario.")
        return GestioneCtu(str(source))
    if marker["tenant"] != tenant_key or marker["phase"] != "committed":
        raise RuntimeError("Transizione CTU non confermata per lo studio corrente.")
    adoption = probe(profile, tenant_key)
    if adoption is None or adoption[0] != marker["source_sha256"] or not str(adoption[1] or "").strip():
        raise RuntimeError("Adozione SQL CTU discordante: nessun ritorno all'archivio storico.")
    database = get_database(profile)
    if database is None:
        raise RuntimeError("Repository SQL CTU indisponibile.")
    return GestioneCtu(str(source), repository=CtuRepository(database, tenant_key, actor_key=actor_key, expected_adoption=adoption))
