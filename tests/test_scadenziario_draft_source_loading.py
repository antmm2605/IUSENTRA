import json
import sqlite3
from datetime import date, timedelta

import pytest

from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from web.services.react_scadenziario_bridge import build_react_scadenziario_payload


@pytest.mark.parametrize('query', [{'vista': 'aperte'}, {'vista': 'aperte', 'q': 'nessuna corrispondenza'}])
def test_draft_source_is_loaded_even_when_excluded_from_operational_filter(tmp_path, query):
    audit = tmp_path / 'pec.sqlite'
    with sqlite3.connect(audit) as connection:
        connection.executescript('CREATE TABLE pec_messages(id TEXT,tenant_id TEXT); CREATE TABLE pec_validation_reports(message_id TEXT,report_json TEXT); CREATE TABLE pec_attachments(message_id TEXT,filename TEXT,attachment_index INT);')
        connection.execute('INSERT INTO pec_messages VALUES (?,?)', ('pec_draft', 'own'))
        connection.execute('INSERT INTO pec_validation_reports VALUES (?,?)', ('pec_draft', json.dumps({'procedural_profile': {'numero_rg': '505/2024'}})))
        connection.execute('INSERT INTO pec_attachments VALUES (?,?,?)', ('pec_draft', 'sentenza.pdf.zip', 0))
    manager = GestioneScadenziario(str(tmp_path / 'scadenze.json'))
    draft = manager.nuova('Proposta RG 505/2024', TipoTermine.ALTRO, (date.today() + timedelta(days=30)).isoformat(), source_message_id='pec_draft')
    draft.stato = StatoTermine.BOZZA
    payload = build_react_scadenziario_payload(gestione_scadenziario=manager, gestione_fascicoli=None, query_args=query, pec_audit_db=str(audit), tenant_id='own')
    assert not payload['items']
    proposal = next(row for row in payload['draftProposals'] if row['id'] == draft.id)
    assert proposal['sourceHref'] == '/api/v1/ui/email/source/pec_draft?name=sentenza.pdf.zip'
    assert proposal['sourceVerified'] is True
    assert draft.stato == StatoTermine.BOZZA


@pytest.mark.parametrize('origin', ['ctu', 'interno'])
def test_internal_draft_is_not_presented_as_a_pec(tmp_path, origin):
    manager = GestioneScadenziario(str(tmp_path / 'scadenze.json'))
    draft = manager.nuova('Termine controllato', TipoTermine.ADEMPIMENTO, (date.today() + timedelta(days=30)).isoformat(), id_fascicolo='CASE1')
    draft.stato = StatoTermine.BOZZA
    draft.descrizione = 'Data registrata nel fascicolo'
    draft.note = 'ctu:incarico1:deposito' if origin == 'ctu' else ''
    payload = build_react_scadenziario_payload(gestione_scadenziario=manager, gestione_fascicoli=None, query_args={'vista': 'aperte'})
    proposal = next(row for row in payload['draftProposals'] if row['id'] == draft.id)
    assert proposal['sourceOrigin'] == origin
    assert proposal['sourceOriginLabel'] != 'PEC'
    assert not proposal['sourceVerified']
    if origin == 'ctu':
        assert proposal['sourceHref'] == '/fascicoli/CASE1#ctu'
        assert proposal['sourceLabel'] == "Dati dell'incarico CTU: Data registrata nel fascicolo"
    assert draft.stato == StatoTermine.BOZZA
