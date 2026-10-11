"""Factory delle preparazioni, SQL soltanto dopo adozione confermata.

Il collegamento ai factory dell'app avviene con il rilascio dell'intero punto:
nessun DDL/import nelle letture, nessun ritorno al JSON dopo l'adozione.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from pct.prima_nota_transition import read_transition
from pct.udienze.repository import PreparazioniRepository
from pct.wizard_pro import GestioneWizardPro, SessioneWizardPro


class GestionePreparazioniSql:
    def __init__(self, repository):
        self.repository = repository

    @property
    def write_protocol(self):
        repo = self.repository
        scope = hashlib.sha256(f"preparazioni:{repo.tenant}:{repo.actor}:{repo.expected_adoption}".encode("utf-8")).hexdigest()
        return {"persistentCommands": True, "scope": scope, "version": 1}

    @staticmethod
    def _session(item):
        if item is None:
            return None
        session = SessioneWizardPro.from_dict(item["record"])
        session.sql_revision = item["revision"]
        return session

    def lista(self):
        return [self._session(item) for item in self.repository.list()]

    def lista_per_fascicolo(self, key):
        return [self._session(item) for item in self.repository.list(fascicolo_id=key)]

    def carica(self, key):
        return self._session(self.repository.get(key))

    def execute(self, key, operation, intent, *, command_key, expected_revision, today):
        from web.services.preparazione_udienza_commands import execute_command
        return execute_command(self.repository, key, operation, intent, command_key=command_key,
                               expected_revision=expected_revision, today=today)

    def start(self, *, fascicolo_id, appuntamento_id, command_key, avvocato, titolo=""):
        from web.services.preparazione_udienza_start import start_command
        return start_command(self.repository, fascicolo_id=fascicolo_id, appuntamento_id=appuntamento_id,
                             command_key=command_key, avvocato=avvocato, titolo=titolo)

    def salva(self, sessione):
        raise ValueError("Il salvataggio della preparazione richiede il comando SQL con versione e intento dell'operatore.")

    def elimina(self, key):
        raise ValueError("L'eliminazione della preparazione richiede il comando SQL con versione e intento dell'operatore.")


def _postgres_dsn():
    from flask import g
    from pct.storage_postgres import build_postgres_dsn
    config = getattr(getattr(g, "tenant", None), "database", None)
    if config is None:
        raise RuntimeError("Configurazione PostgreSQL delle preparazioni assente.")
    return build_postgres_dsn(host=config.host, port=config.porta_effettiva or 5432,
        db_name=config.db_name, user=config.utente, password=config.password, ssl=config.ssl)


def probe_adoption(profile, tenant_key):
    if profile.uses_sqlite:
        path = Path(profile.studio_db_path).resolve()
        if not path.is_file():
            raise RuntimeError("Archivio SQL dello studio assente: adozione delle preparazioni non determinabile.")
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='preparazioni_state'").fetchone()
            return conn.execute("SELECT source_sha256,backup_reference FROM preparazioni_state WHERE tenant_key=?", (tenant_key,)).fetchone() if exists else None
        finally:
            conn.close()
    if profile.effective_mode != "POSTGRESQL":
        return None
    import psycopg2
    conn = psycopg2.connect(_postgres_dsn(), connect_timeout=5)
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5000ms'")
            cursor.execute("SELECT to_regclass('preparazioni_state')")
            if cursor.fetchone()[0] is None:
                return None
            cursor.execute("SELECT source_sha256,backup_reference FROM preparazioni_state WHERE tenant_key=%s", (tenant_key,))
            return cursor.fetchone()
    finally:
        conn.rollback()
        conn.close()


def open_database(profile):
    from flask import g
    if profile.uses_sqlite:
        from pct.storage import StudioDB
        db = StudioDB(profile.studio_db_path, initialize_schema=False)
    elif profile.effective_mode == "POSTGRESQL":
        from pct.storage_postgres import PostgresStudioDB
        db = PostgresStudioDB(_postgres_dsn(), initialize_schema=False)
    else:
        raise RuntimeError("Repository SQL delle preparazioni non configurato.")
    g._preparazioni_owned_database = db
    return db


def close_database():
    from flask import g
    db = g.pop("_preparazioni_owned_database", None)
    if db is not None:
        db.chiudi()


def get_request_preparazioni(source, anchor):
    from flask import current_app, g
    from web.services.storage_runtime import get_request_storage_runtime
    tenant = str(getattr(g, "tenant_context_slug", "") or
                 getattr(getattr(g, "tenant", None), "slug", "") or "").strip().lower()
    if not tenant and not (current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False)):
        tenant = "studio"
    actor = str(getattr(getattr(g, "utente_corrente", None), "id", "") or "").strip()
    context = (str(source), str(anchor), tenant, actor)
    cached = g.get("_preparazioni_request_runtime")
    if cached is not None:
        if cached[0] != context:
            raise RuntimeError("Contesto dello studio cambiato nella richiesta: accesso alle preparazioni sospeso.")
        return cached[1]
    runtime = open_preparazioni_runtime(source, anchor=anchor, tenant_key=tenant, actor_key=actor,
                                       get_profile=get_request_storage_runtime)
    g._preparazioni_request_runtime = (context, runtime)
    return runtime


def open_preparazioni_runtime(source, *, anchor, tenant_key, actor_key, get_profile,
                             probe=probe_adoption, get_database=open_database):
    if not anchor or not tenant_key:
        raise RuntimeError("Contesto dello studio per le preparazioni incompleto.")
    profile = get_profile(str(anchor))
    if profile.tenant_slug and profile.tenant_slug != tenant_key:
        raise RuntimeError("Profilo SQL di altro studio: accesso alle preparazioni sospeso.")
    try:
        marker = read_transition(source)
    except RuntimeError as exc:
        raise RuntimeError("Transizione delle preparazioni incoerente: nessun ritorno al JSON.") from exc
    adoption = probe(profile, tenant_key)
    if marker is None:
        if adoption is not None:
            raise RuntimeError("Segnale di transizione assente dopo adozione SQL delle preparazioni.")
        return GestioneWizardPro(str(source))
    if marker["tenant"] != tenant_key or marker["phase"] != "committed":
        raise RuntimeError("Transizione delle preparazioni non confermata per lo studio corrente.")
    if adoption is None or adoption[0] != marker["source_sha256"] or not str(adoption[1] or "").strip():
        raise RuntimeError("Adozione SQL delle preparazioni discordante: nessun ritorno al JSON.")
    db = get_database(profile)
    if db is None:
        raise RuntimeError("Repository SQL delle preparazioni indisponibile.")
    return GestionePreparazioniSql(PreparazioniRepository(db, tenant_key, actor=actor_key, expected_adoption=tuple(adoption)))
