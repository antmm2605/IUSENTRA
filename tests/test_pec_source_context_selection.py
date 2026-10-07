import json
import sqlite3
from types import SimpleNamespace

from web.services.pec_source_links import latest_pec_profiles, pec_profile_for_item, pec_audit_message_ids


def item(rg='795/2026', court='Tribunale di Vicenza', explicit=''):
    return SimpleNamespace(titolo=f'Grosso Eugenio - RG {rg}', descrizione='', tribunale=court,
                           note='PEC_AUDIT:pec_wrong:deadline\nPEC_AUDIT:pec_correct:deadline',
                           source_message_id=explicit)


def profiles():
    return {'pec_wrong': {'numero_rg':'806/2026','ufficio':'Tribunale di Vicenza'},
            'pec_correct': {'numero_rg':'795/2026','ufficio':'Tribunale di Vicenza'}}


def test_later_reference_matches_proceeding_not_first_marker():
    result=pec_profile_for_item(item(),profiles())
    assert result['_source_message_id']=='pec_correct'
    assert result['_source_multiple'] is True


def test_same_prefix_does_not_match_other_role():
    assert pec_profile_for_item(item('79/2026'),profiles())['_source_resolution']=='ambiguous'


def test_same_role_other_court_is_not_verified():
    assert pec_profile_for_item(item(court='Tribunale di Roma'),profiles())['_source_resolution']=='ambiguous'


def test_duplicate_role_remains_ambiguous():
    data=profiles();data['pec_wrong']['numero_rg']='795/2026'
    assert pec_profile_for_item(item(),data)['_source_message_id']==''


def test_missing_profiles_never_selects_first_historical_reference():
    assert pec_profile_for_item(item(),{})['_source_resolution']=='ambiguous'


def test_explicit_primary_reference_precedes_history():
    assert pec_profile_for_item(item(explicit='pec_correct'),profiles())['_source_message_id']=='pec_correct'
    assert pec_audit_message_ids(item(explicit='pec_correct'))==['pec_correct','pec_wrong']


def test_conflicting_primary_reference_is_not_verified():
    assert pec_profile_for_item(item(explicit='pec_wrong'),profiles())['_source_resolution']=='ambiguous'


def test_single_historical_reference_preserves_old_source():
    row=SimpleNamespace(note='PEC_AUDIT:pec_correct:hearing:event',titolo='Udienza')
    assert pec_profile_for_item(row,profiles())['_source_message_id']=='pec_correct'


def test_sql_loads_all_references_latest_report_and_own_tenant(tmp_path):
    path=tmp_path/'audit.sqlite'
    db=sqlite3.connect(path)
    db.executescript("CREATE TABLE pec_messages(id TEXT,tenant_id TEXT); CREATE TABLE pec_validation_reports(message_id TEXT,report_json TEXT); CREATE TABLE pec_attachments(message_id TEXT,filename TEXT,attachment_index INT);")
    db.executemany('INSERT INTO pec_messages VALUES (?,?)',[('pec_wrong','own'),('pec_correct','own'),('pec_private','other')])
    for mid,profile in profiles().items():
        db.execute('INSERT INTO pec_validation_reports VALUES (?,?)',(mid,json.dumps({'procedural_profile':profile})))
    db.execute('INSERT INTO pec_validation_reports VALUES (?,?)',('pec_correct',json.dumps({'procedural_profile':{'numero_rg':'795/2026','ufficio':'Tribunale di Vicenza'}})))
    db.execute('INSERT INTO pec_attachments VALUES (?,?,?)',('pec_correct','correct.pdf.zip',0))
    db.commit();db.close()
    loaded=latest_pec_profiles([item(),SimpleNamespace(note='PEC_AUDIT:pec_private')],pec_audit_db=str(path),tenant_id='own')
    assert set(loaded)=={'pec_wrong','pec_correct'}
    selected=pec_profile_for_item(item(),loaded)
    assert selected['_source_message_id']=='pec_correct'
    assert selected['_indexed_source_name']=='correct.pdf.zip'
    db=sqlite3.connect(path)
    assert db.execute('SELECT count(*) FROM pec_validation_reports').fetchone()[0]==3
    assert db.total_changes==0
    db.close()
