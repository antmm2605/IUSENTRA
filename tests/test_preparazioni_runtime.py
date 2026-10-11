"""Selezione SQL governata e letture senza bootstrap, su fonte controllata."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.prima_nota_transition import commit_transition_locked, prepare_transition_locked, prima_nota_source_lock, transition_path
from pct.udienze.repository import PreparazioniRepository
from tests.test_preparazioni_sql_repository import database as database
from web.services.preparazione_udienza_sql_runtime import open_preparazioni_runtime, probe_adoption


def setup(database):
    root = Path(database.db_path).parent
    source = root / "sessioni.json"
    source.write_text("[]", encoding="utf-8")
    profile = SimpleNamespace(tenant_slug="studio", uses_sqlite=True, studio_db_path=database.db_path, effective_mode="SQLITE")
    kwargs = {"anchor": str(root / "clienti.json"), "tenant_key": "studio", "actor_key": "avvocato",
              "get_profile": lambda anchor: profile, "get_database": lambda profile: database}
    return source, profile, kwargs


def adopted(database, source, *, committed=True):
    repo = PreparazioniRepository(database, "studio", actor="migrazione")
    with prima_nota_source_lock(source):
        prepare_transition_locked(source, tenant="studio", source_sha256="a" * 64)
        repo.initialize([], source_sha256="a" * 64, backup_reference="backup-verificato")
        if committed:
            commit_transition_locked(source, tenant="studio", source_sha256="a" * 64)


def test_read_pre_adoption_no_ddl(database):
    source, profile, kwargs = setup(database)
    before = database.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
    assert probe_adoption(profile, "studio") is None
    assert open_preparazioni_runtime(source, **kwargs).lista() == []
    assert before == database.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()


def test_adopted_never_reads_json_or_creates_schema(database):
    source, _, kwargs = setup(database)
    adopted(database, source)
    source.write_text("questo non deve essere letto", encoding="utf-8")
    before = database.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
    manager = open_preparazioni_runtime(source, **kwargs)
    assert manager.lista() == [] and manager.write_protocol["persistentCommands"] is True
    assert before == database.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
    assert manager.write_protocol["scope"] == open_preparazioni_runtime(source, **kwargs).write_protocol["scope"]
    assert manager.write_protocol["scope"] != open_preparazioni_runtime(source, **{**kwargs, "actor_key": "altro"}).write_protocol["scope"]
    with pytest.raises(ValueError, match="comando SQL"):
        manager.salva(None)


def test_missing_transition_marker_does_not_restore_json(database):
    source, _, kwargs = setup(database)
    adopted(database, source)
    transition_path(source).unlink()
    with pytest.raises(RuntimeError, match="Segnale"):
        open_preparazioni_runtime(source, **kwargs)


def test_prepared_transition_not_operational(database):
    source, _, kwargs = setup(database)
    adopted(database, source, committed=False)
    with pytest.raises(RuntimeError, match="non confermata"):
        open_preparazioni_runtime(source, **kwargs)


def test_foreign_tenant_rejected_before_probe(database):
    source, profile, kwargs = setup(database)
    profile.tenant_slug = "altro-studio"
    with pytest.raises(RuntimeError, match="altro studio"):
        open_preparazioni_runtime(source, **kwargs, probe=lambda *args: pytest.fail("Probe in altro studio"))


def test_database_failure_never_falls_back_to_json(database):
    source, _, kwargs = setup(database)
    adopted(database, source)
    def unavailable(profile):
        raise RuntimeError("SQL non disponibile")
    with pytest.raises(RuntimeError, match="SQL non disponibile"):
        open_preparazioni_runtime(source, **{**kwargs, "get_database": unavailable})
