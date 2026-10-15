from contextlib import closing
import sqlite3

import pytest

from pct.operational_live import (
    TENANT_TABLE_DOMAINS,
    ensure_tenant_live_schema,
    read_tenant_live_revisions,
)


@pytest.mark.parametrize("family", ["letture", "economico"])
def test_vertical_commit_rollback_and_tenant_isolation(tmp_path, family):
    target = tmp_path / "vertical.db"
    writer = sqlite3.connect(target)
    reader = sqlite3.connect(target)
    try:
        for table in TENANT_TABLE_DOMAINS[family]:
            writer.execute(f"CREATE TABLE {table}(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, value TEXT)")
        ensure_tenant_live_schema(writer, family)
        writer.commit()
        table = next(iter(TENANT_TABLE_DOMAINS[family]))
        writer.execute(f"INSERT INTO {table} VALUES ('proof', 'studio-a', 'originale')")
        assert read_tenant_live_revisions(reader, family, "studio-a", {"fascicoli"}) == {}
        writer.commit()
        assert read_tenant_live_revisions(reader, family, "studio-a", {"fascicoli"}) == {"fascicoli": 1}
        writer.execute(f"UPDATE {table} SET value='originale' WHERE id='proof'")
        writer.commit()
        assert read_tenant_live_revisions(reader, family, "studio-a", {"fascicoli"}) == {"fascicoli": 1}
        assert read_tenant_live_revisions(reader, family, "studio-b", {"fascicoli"}) == {}
        writer.execute(f"UPDATE {table} SET value='scartato' WHERE id='proof'")
        writer.rollback()
        assert read_tenant_live_revisions(reader, family, "studio-a", {"fascicoli"}) == {"fascicoli": 1}
        ensure_tenant_live_schema(writer, family)
        writer.execute(f"UPDATE {table} SET tenant_id='studio-b' WHERE id='proof'")
        writer.commit()
        assert read_tenant_live_revisions(reader, family, "studio-a", {"fascicoli"}) == {"fascicoli": 2}
        assert read_tenant_live_revisions(reader, family, "studio-b", {"fascicoli"}) == {"fascicoli": 1}
        writer.execute(f"DELETE FROM {table} WHERE id='proof'")
        writer.commit()
        assert read_tenant_live_revisions(reader, family, "studio-b", {"fascicoli"}) == {"fascicoli": 2}
    finally:
        writer.close()
        reader.close()


def test_repeated_reader_confirmation_only_signals_changed_results(tmp_path):
    from pct.registro_letture.repository import RegistroLetture

    repository = RegistroLetture(tmp_path / "registro.db")
    try:
        repository.segna_fascicolo("studio-a", "f1", "indice_documentale", impronta="proof", oggetti_totali=1, oggetti_letti=1, esito={"pronti": 1})
        with closing(repository.connection()) as reader:
            before = read_tenant_live_revisions(reader, "letture", "studio-a", {"fascicoli"})
        repository.segna_fascicolo("studio-a", "f1", "indice_documentale", impronta="proof", oggetti_totali=1, oggetti_letti=1, esito={"pronti": 1})
        with closing(repository.connection()) as reader:
            assert read_tenant_live_revisions(reader, "letture", "studio-a", {"fascicoli"}) == before
        repository.segna_fascicolo("studio-a", "f1", "indice_documentale", impronta="proof", oggetti_totali=1, oggetti_letti=0, stato="errore", esito={"errori": 1})
        with closing(repository.connection()) as reader:
            assert read_tenant_live_revisions(reader, "letture", "studio-a", {"fascicoli"})["fascicoli"] == before["fascicoli"] + 1
    finally:
        repository.close()


def test_read_does_not_migrate_or_include_cache(tmp_path):
    target = tmp_path / "read-only.db"
    connection = sqlite3.connect(target)
    try:
        connection.execute("CREATE TABLE source(id TEXT)")
        connection.commit()
        connection.execute("PRAGMA query_only=ON")
        assert read_tenant_live_revisions(connection, "letture", "studio-a", {"fascicoli"}) == {}
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 1
        assert "letture_payload_cache" not in TENANT_TABLE_DOMAINS["letture"]
    finally:
        connection.close()


def test_sync_api_reads_vertical_counters_without_cross_tenant_data(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from flask import Flask, g
    from web.bootstrap.sync_runtime_routes import register_sync_runtime_routes
    import web.services.storage_runtime as storage_runtime
    import web.services.registro_letture_runtime as registry_runtime

    central = sqlite3.connect(tmp_path / "studio.db")
    central.execute("CREATE TABLE operational_live_revisions(domain TEXT PRIMARY KEY,revision INTEGER)")
    central.execute("INSERT INTO operational_live_revisions VALUES ('fascicoli', 5)")
    central.commit()
    paths = {}
    for family, key in (("letture", "REGISTRO_LETTURE_DB"), ("economico", "SENTENZA_ECONOMIC_DB")):
        target = tmp_path / f"{family}.db"
        with closing(sqlite3.connect(target)) as conn, conn:
            for table in TENANT_TABLE_DOMAINS[family]:
                conn.execute(f"CREATE TABLE {table}(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,value TEXT)")
            ensure_tenant_live_schema(conn, family)
            table = next(iter(TENANT_TABLE_DOMAINS[family]))
            conn.execute(f"INSERT INTO {table} VALUES ('own','studio-a','controllato')")
            conn.execute(f"INSERT INTO {table} VALUES ('other','studio-b','altro studio')")
        paths[key] = str(target)
    app = Flask(__name__)
    app.config.update(paths, CLIENTI_DB=str(tmp_path / "clienti.json"))
    @app.before_request
    def context():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda permission: permission == "fascicoli.leggi")
        g.tenant_context_slug = "studio-a"
    monkeypatch.setattr(storage_runtime, "get_request_studio_db", lambda _: SimpleNamespace(conn=central))
    monkeypatch.setattr(registry_runtime, "tenant_corrente", lambda: "studio-a")
    monkeypatch.setattr(registry_runtime, "_dsn_postgres", lambda paths=None: "")
    register_sync_runtime_routes(app, sync_manager=SimpleNamespace(), get_fascicoli=lambda: None, get_utenti=lambda: None, audit=lambda *args, **kwargs: None)
    try:
        response = app.test_client().get("/api/v1/ui/sync/revisions")
        assert response.status_code == 200
        payload = dict(response.json)
        context = payload.pop("revisionContext")
        assert len(context) == 64 and all(char in '0123456789abcdef' for char in context)
        assert payload == {"ok": True, "revisions": {"fascicoli": 7}}
        assert response.headers["Cache-Control"] == "no-store"
        # Il polling non crea segnali e non muta il contenuto delle fonti.
        assert app.test_client().get("/api/v1/ui/sync/revisions").json == response.json
    finally:
        central.close()


def test_fascicolo_get_does_not_restart_missing_document_readers(tmp_path, monkeypatch):
    from tests.test_react_shell import _app
    from pct.fascicoli import TipoDocumento, TipoFascicolo
    from web.services import react_fascicoli_bridge as bridge

    app = _app(tmp_path)
    with app.app_context():
        manager = app.extensions["core_runtime"]["get_fascicoli"]()
        matter = manager.nuovo("COLLAUDO consultazione senza rilancio", TipoFascicolo.CIVILE)
        manager.aggiungi_documento(matter.id, nome_file="fonte.txt", tipo=TipoDocumento.ALTRO, contenuto=b"Fonte tecnica controllata senza eventi processuali.")
    calls = []
    monkeypatch.setattr(bridge, "_ensure_deadline_document_ai_texts_for_fascicolo", lambda *args: calls.append("reading"))
    for include in ("documenti", "scadenze", "documenti,scadenze", "all"):
        response = app.test_client().get(f"/api/v1/ui/fascicoli/{matter.id}?include={include}", headers={"X-API-Key": "react-test-key"})
        assert response.status_code == 200
        assert response.json["fascicolo"]["id"] == matter.id
    assert calls == []
