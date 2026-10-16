"""Consegne puntuali: sorgenti controllate, repository e resolver nativi."""
import json
import re
from datetime import date, timedelta
from types import SimpleNamespace

from flask import Flask, g

from pct.database import SCHEMA_SQL
from pct.storage_postgres import CORE_POSTGRES_SCHEMA_SQL
from pct.fascicoli import GestioneFascicoli
from tests.test_fascicoli_list_query import catalog as catalog
from tests.test_archivio_fatti_request_snapshot import snapshot_registry as snapshot_registry
from web.services import registro_letture_runtime as runtime
from web.services.fascicoli_list_writer import FascicoliListWriter


def test_registro_condiviso_aggiorna_solo_studi_registrati(snapshot_registry):
    import pytest
    from pct.registro_letture import Oggetto
    from pct.fascicoli_list_query import install_registry_events, assert_registry_ready, FascicoliListNotReady
    from web.services.registro_letture_runtime import connessione_registro
    registry = snapshot_registry
    with connessione_registro(registry) as conn:
        for tenant in ('studio', 'secondo'):
            install_registry_events(conn, tenant=tenant, postgres=registry.backend_kind == 'postgres')
        assert_registry_ready(conn, 'studio')
        assert_registry_ready(conn, 'secondo')
    source = Oggetto(tipo='documento', oggetto_id='D1', sha256='a' * 64)
    registry.registra_inventario('studio', 'F1', [source])
    registry.registra_inventario('non-migrato', 'F1', [source])
    with connessione_registro(registry) as conn:
        with pytest.raises(FascicoliListNotReady):
            assert_registry_ready(conn, 'studio')
        assert_registry_ready(conn, 'secondo')
        owners = {row[0] for row in conn.execute('SELECT DISTINCT tenant_id FROM transactional_outbox').fetchall()}
        assert owners == {'studio'}


def test_scadenza_cambia_fascicolo_senza_leggere_pratiche_estranee(catalog, snapshot_registry, monkeypatch, tmp_path):
    db, _repo = catalog
    db.conn.execute('DELETE FROM fascicoli_list_rows')
    db.conn.execute('CREATE TABLE clienti(id TEXT PRIMARY KEY)')
    schema = CORE_POSTGRES_SCHEMA_SQL if db.backend_kind == 'postgresql' else SCHEMA_SQL
    definition = re.search(r'CREATE TABLE IF NOT EXISTS fascicoli \(.*?\n\);', schema, re.S)
    db.conn.execute(definition.group())
    db.conn.execute('CREATE TABLE scadenze(id TEXT PRIMARY KEY,id_fascicolo TEXT,dati_json TEXT)')
    db.conn.execute('CREATE TABLE parcelle(id TEXT PRIMARY KEY,id_fascicolo TEXT,dati_json TEXT)')
    for number in range(3):
        payload = dict(id=f'F{number:03}', numero=f'2026/{number:03}', titolo='Pratica controllata',
            nome_cliente='Cliente condiviso' if number < 2 else 'Cliente estraneo', tipo='CIVILE', stato='APERTO',
            numero_rg='1000' if number < 2 else '2000', anno_rg=2026, tribunale='Tribunale di Milano',
            data_apertura='2026-01-01', creato_il='2026-01-01T10:00:00', modificato_il='2026-01-01T10:00:00')
        db.conn.execute('INSERT INTO fascicoli(id,numero,dati_json) VALUES (?,?,?)',
                        (payload['id'], payload['numero'], json.dumps(payload)))
    day = (date.today() + timedelta(days=4)).isoformat()
    deadline = dict(id='S1', titolo='Scadenza controllata', tipo='ALTRO', stato='APERTO',
                    id_fascicolo='F000', data_scadenza=day)
    db.conn.execute('INSERT INTO scadenze VALUES (?,?,?)', ('S1', 'F000', json.dumps(deadline)))
    calls = []

    def fetch(sql, params):
        assert 'WHERE id IN (' in sql
        calls.append(tuple(params))
        return db.conn.execute(sql, params).fetchall()

    db.fetchall_readonly = fetch
    native = GestioneFascicoli(str(tmp_path / 'fascicoli.json'), studio_db=db, carica_tutto=False)
    # Importare prima delle sostituzioni evita che alias importati durante il
    # caso conservino funzioni del test dopo il ripristino di monkeypatch.
    from web.services import archivio_letture_runtime as archive
    monkeypatch.setattr(runtime, 'registro_corrente', lambda: snapshot_registry)
    monkeypatch.setattr(runtime, 'tenant_corrente', lambda: g.studio)
    monkeypatch.setattr(runtime, 'percorso_registro', lambda: 'controlled-registry')
    monkeypatch.setattr(archive, 'registro_corrente', lambda: snapshot_registry)
    monkeypatch.setattr(archive, 'tenant_corrente', lambda: g.studio)
    app = Flask(__name__)
    app.config.update(FASCICOLI_DB=str(tmp_path / 'fascicoli.json'), REGISTRO_LETTURE_DB=str(tmp_path / 'facts.db'))
    writer = FascicoliListWriter(db, 'studio', native)
    with app.test_request_context('/__controlled-projection'):
        g.studio = 'studio'
        writer.project_identities(db.conn, ['F000', 'F001', 'F002'])
        writer.project_deadline(db.conn, 'S1')
        writer.project_batch(db.conn, ['F000', 'F001', 'F002'], phase='ROWS')
        first = json.loads(db.conn.execute("SELECT payload_json FROM fascicoli_list_rows WHERE record_key='F000'").fetchone()[0])
        assert first['nextDeadlineIso'] == day
        calls.clear()
        deadline['id_fascicolo'] = 'F001'
        db.conn.execute('UPDATE scadenze SET id_fascicolo=?,dati_json=? WHERE id=?', ('F001', json.dumps(deadline), 'S1'))
        writer.project_deadline(db.conn, 'S1')
        pending = {row[0] for row in db.conn.execute("SELECT aggregate_id FROM transactional_outbox WHERE status='PENDING'").fetchall()}
        assert pending == {'case:F000', 'case:F001'}
        writer.project_batch(db.conn, ['F000', 'F001'], phase='ROWS')
        values = {row[0]: json.loads(row[1]) for row in db.conn.execute(
            "SELECT record_key,payload_json FROM fascicoli_list_rows WHERE record_key IN ('F000','F001')").fetchall()}
        assert values['F000']['nextDeadlineIso'] == ''
        assert values['F001']['nextDeadlineIso'] == day
        assert calls == [('F000',), ('F001',)]
        assert db.conn.execute('SELECT COUNT(*) FROM fascicoli').fetchone()[0] == 3
        assert db.conn.execute('SELECT COUNT(*) FROM scadenze').fetchone()[0] == 1
        # Riferimento indipendente: il vecchio costruttore completo resta una
        # guardia tecnica della parità, mai il percorso della nuova richiesta.
        from pct.calendar_sql_records import deadline_from_row
        from web.services import react_fascicoli_bridge as bridge
        from web.services.fascicoli_list_payload import build_sql_list_payload
        reference_db = SimpleNamespace(backend_kind=db.backend_kind,
            fetchall_readonly=lambda sql, params=(): db.conn.execute(sql, params).fetchall())
        reference_native = GestioneFascicoli(str(tmp_path / 'reference.json'), studio_db=reference_db,
                                           carica_tutto=False, senza_documenti=True)
        source = deadline_from_row(db.conn.execute("SELECT * FROM scadenze WHERE id='S1'").fetchone())
        source.aggiorna_priorita()
        monkeypatch.setattr(bridge, '_fascicoli_base_cache_get', lambda *_args: None)
        monkeypatch.setattr(bridge, '_fascicoli_base_cache_set', lambda *_args: None)
        expected = bridge.build_react_fascicoli_payload(get_fascicoli=lambda: reference_native,
            get_scadenziario=lambda: SimpleNamespace(tutte=lambda **_kwargs: [source]),
            get_fatturazione=lambda: SimpleNamespace(tutte=lambda: []), page_size=2, sort='cliente')
        calls.clear()
        actual = build_sql_list_payload(writer.repository, page_size=2, sort='cliente')
        for value in (expected, actual):
            value.pop('generatedAt')
        matching = actual == expected
        assert matching, [key for key in actual if actual[key] != expected.get(key)]
        assert calls == []
