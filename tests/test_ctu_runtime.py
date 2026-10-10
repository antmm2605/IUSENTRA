"""Transizione e factory su archivi controllati; nessuna accettazione UI."""
import sqlite3
from types import SimpleNamespace

import pytest

from pct.ctu_repository import CtuRepository
from pct.ctu_transition import commit_locked, prepare_locked, source_lock
from web.services.ctu_runtime import open_ctu_runtime, probe_adoption


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / "incarichi.json"
    sql = tmp_path / "studio.db"
    conn = sqlite3.connect(sql)
    db = SimpleNamespace(conn=conn)
    conn.execute("CREATE TABLE audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                 "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
    conn.commit()
    profile = SimpleNamespace(tenant_slug="studio", uses_sqlite=True, studio_db_path=str(sql), effective_mode="SQLITE")
    kwargs = {"anchor": str(tmp_path / "clienti.json"), "tenant_key": "studio", "actor_key": "avvocato",
              "get_profile": lambda anchor: profile, "get_database": lambda profile: db}
    yield source, db, profile, kwargs
    conn.close()


def adopt(source, db, *, commit=True):
    repo = CtuRepository(db, "studio", actor_key="migrazione")
    repo.ensure_schema()
    with source_lock(source):
        prepare_locked(source, tenant="studio", source_sha256="a" * 64)
        repo.initialize({}, source_sha256="a" * 64, backup_reference="backup-verificato")
        if commit:
            commit_locked(source, tenant="studio", source_sha256="a" * 64)


def test_json_pre_adozione_e_probe_senza_ddl(setup):
    source, db, profile, kwargs = setup
    before = db.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
    assert probe_adoption(profile, "studio") is None
    assert not open_ctu_runtime(source, **kwargs).write_protocol["persistentCommands"]
    assert before == db.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()


def test_sql_adottato_non_legge_json_e_non_esegue_ddl(setup):
    source, db, profile, kwargs = setup
    adopt(source, db)
    source.write_text("contenuto storico non consultabile", encoding="utf-8")
    before = db.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()
    manager = open_ctu_runtime(source, **kwargs)
    protocol = manager.write_protocol
    assert protocol["persistentCommands"] is True
    assert protocol["revision"] == 0
    assert len(protocol["scope"]) == 64
    assert open_ctu_runtime(source, **kwargs).write_protocol["scope"] == protocol["scope"]
    assert open_ctu_runtime(source, **{**kwargs, "actor_key": "altro-operatore"}).write_protocol["scope"] != protocol["scope"]
    assert before == db.conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()


def test_marker_assente_non_ripristina_json(setup):
    source, db, profile, kwargs = setup
    adopt(source, db)
    from pct.prima_nota_transition import transition_path
    transition_path(source).unlink()
    with pytest.raises(RuntimeError, match="assente dopo adozione"):
        open_ctu_runtime(source, **kwargs)


def test_prepared_non_apre_archivio(setup):
    source, db, profile, kwargs = setup
    adopt(source, db, commit=False)
    with pytest.raises(RuntimeError, match="non confermata"):
        open_ctu_runtime(source, **kwargs)


def test_tenant_discordante_non_apre_database(setup):
    source, db, profile, kwargs = setup
    def forbidden(*args):
        pytest.fail("Il database non deve essere aperto")
    kwargs["get_database"] = forbidden
    kwargs["tenant_key"] = "altro"
    with pytest.raises(RuntimeError, match="altro studio"):
        open_ctu_runtime(source, **kwargs)


def test_errore_sql_non_diventa_json(setup):
    source, db, profile, kwargs = setup
    def unavailable(*args):
        raise OSError("SQL indisponibile")
    kwargs["probe"] = unavailable
    with pytest.raises(OSError, match="SQL indisponibile"):
        open_ctu_runtime(source, **kwargs)


def test_database_mancante_non_creato_dal_probe(tmp_path):
    profile = SimpleNamespace(uses_sqlite=True, studio_db_path=str(tmp_path / "mancante.db"))
    with pytest.raises(RuntimeError, match="assente"):
        probe_adoption(profile, "studio")
    assert not (tmp_path / "mancante.db").exists()


def test_adozione_cambiata_tra_probe_e_apertura_non_accettata(setup):
    source, db, profile, kwargs = setup
    adopt(source, db)
    def changed(profile):
        db.conn.execute("UPDATE ctu_state SET source_sha256=?", ("b" * 64,))
        db.conn.commit()
        return db
    kwargs["get_database"] = changed
    with pytest.raises(RuntimeError, match="cambiata durante"):
        open_ctu_runtime(source, **kwargs)
