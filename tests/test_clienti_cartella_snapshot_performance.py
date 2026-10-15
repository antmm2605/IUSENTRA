"""Guardrail brevi e shardabili della proiezione consultiva cartella cliente."""
import json
import sqlite3
from types import SimpleNamespace

import pytest
from flask import Flask, g

from web import helpers
from web.services.react_cliente_comunicazioni import pec_collegate_cartella


@pytest.fixture
def snapshot_app(monkeypatch):
    app = Flask(__name__)
    app.add_url_rule('/cartella', endpoint='api_v1_react.cliente_cartella_react', view_func=lambda: '', methods=['GET', 'POST'])
    app.add_url_rule('/dettaglio', endpoint='api_v1_react.fascicolo_react_dettaglio', view_func=lambda: '', methods=['GET', 'POST'])
    app.add_url_rule('/altro', endpoint='altra_pagina', view_func=lambda: '')
    app.add_url_rule('/rinomina', endpoint='rinomina_documento', view_func=lambda: '', methods=['POST'])
    app.add_url_rule('/catalogo-editor', endpoint='editor_new_document_matters', view_func=lambda: '')
    made = []
    def factory(**kwargs):
        value = SimpleNamespace(**kwargs)
        made.append(value)
        return value
    monkeypatch.setattr(helpers, 'GestioneFascicoli', factory)
    monkeypatch.setattr(helpers, '_cfg', lambda key: getattr(g, 'studio', 'studio-a') + '/' + key)
    monkeypatch.setattr(helpers, '_studio_db', lambda key: 'sql-richiesta')
    return app, made


@pytest.mark.parametrize('path', ['/cartella', '/dettaglio'])
def test_snapshot_only_inside_same_cartella_request(snapshot_app, path):
    app, made = snapshot_app
    with app.test_request_context(path):
        first = helpers.get_fascicoli()
        assert helpers.get_fascicoli() is first
    with app.test_request_context(path):
        assert helpers.get_fascicoli() is not first
    assert len(made) == 2


@pytest.mark.parametrize('path,method', [('/altro', 'GET'), ('/cartella', 'POST'), ('/dettaglio', 'POST')])
def test_other_read_and_write_routes_keep_fresh_manager(snapshot_app, path, method):
    app, made = snapshot_app
    with app.test_request_context(path, method=method):
        assert helpers.get_fascicoli() is not helpers.get_fascicoli()
    assert len(made) == 2


def test_changed_tenant_paths_cannot_reuse_snapshot(snapshot_app):
    app, made = snapshot_app
    with app.test_request_context('/cartella'):
        first = helpers.get_fascicoli()
        g.studio = 'studio-b'
        second = helpers.get_fascicoli()
        assert second is not first
        assert second.db_path.startswith('studio-b/')
        assert helpers.get_fascicoli() is second
    assert len(made) == 2


def test_rinomina_sql_carica_solo_il_fascicolo_richiesto(snapshot_app):
    app, made = snapshot_app
    with app.test_request_context('/rinomina', method='POST'):
        first = helpers.get_fascicoli()
        assert first.carica_tutto is False
        assert helpers.get_fascicoli() is not first
    assert len(made) == 2


def test_rinomina_json_conserva_il_gestore_storico_completo(snapshot_app, monkeypatch):
    app, _ = snapshot_app
    monkeypatch.setattr(helpers, '_studio_db', lambda _: None)
    with app.test_request_context('/rinomina', method='POST'):
        assert helpers.get_fascicoli().carica_tutto is True


def test_catalogo_editor_non_idrata_documenti_e_attivita_dei_fascicoli(snapshot_app):
    app, made = snapshot_app
    with app.test_request_context('/catalogo-editor'):
        manager = helpers.get_fascicoli()
        assert manager.studio_db == 'sql-richiesta'
        assert manager.carica_tutto is False
    assert len(made) == 1


@pytest.fixture
def pec_repo(tmp_path):
    connection = sqlite3.connect(tmp_path / 'pec.sqlite')
    connection.row_factory = sqlite3.Row
    connection.execute('CREATE TABLE pec_messages(id TEXT, tenant_id TEXT, received_at TEXT, linked_fascicolo_id TEXT, metadata_json TEXT)')
    repo = SimpleNamespace(tenant_id='studio-a', connect=lambda: connection)
    yield repo, connection
    connection.close()


def add_pec(conn, identifier, fid, *, tenant='studio-a', day='2026-10-06', subject='Attività – già letta'):
    conn.execute('INSERT INTO pec_messages VALUES (?,?,?,?,?)', (identifier, tenant, day, fid, json.dumps({'headers': {'subject': subject, 'from': '  mittente@example.it  '}})))
    conn.commit()


def test_exact_links_tenant_and_order_without_reports_or_writes(pec_repo):
    repo, conn = pec_repo
    add_pec(conn, 'one', 'f1', day='2026-10-05')
    add_pec(conn, 'two', 'f1')
    add_pec(conn, 'other-case', 'f2')
    add_pec(conn, 'mention-only', '', subject='f1 - nominativo cliente')
    add_pec(conn, 'other-tenant', 'f1', tenant='studio-b')
    before = conn.total_changes
    rows = pec_collegate_cartella(['f2', 'f1', 'f1'], repository=repo)
    assert [row['id'] for row in rows] == ['other-case', 'two', 'one']
    assert rows[0]['subject'] == 'Attività – già letta'
    assert rows[0]['from'] == 'mittente@example.it'
    assert conn.total_changes == before


def test_all_links_over_parameter_batch_boundary(pec_repo):
    repo, conn = pec_repo
    ids = [f'f{index}' for index in range(502)]
    for index, fid in enumerate(ids):
        add_pec(conn, f'm{index}', fid)
    rows = pec_collegate_cartella(ids, repository=repo)
    assert len(rows) == 502
    assert [row['fascicolo_id'] for row in rows] == ids


def test_sql_error_is_not_a_fake_empty_catalog(pec_repo):
    repo, conn = pec_repo
    conn.execute('DROP TABLE pec_messages')
    with pytest.raises(sqlite3.OperationalError):
        pec_collegate_cartella(['f1'], repository=repo)


def test_no_case_does_not_initialize_pec_repository():
    assert pec_collegate_cartella([]) == []
