import json
import sqlite3
from types import SimpleNamespace
import pytest
from web.services.pec_source_links import latest_pec_profiles, pec_profile_for_item
from web.services.signed_attachment_preview_text import _format_xml_text, render_xml_preview

@pytest.mark.parametrize('parsed', [ {'pec_receipt': {'type': 'accettazione'}}, {'fields': {'tipo_ricevuta': {'value': 'accettazione', 'confidence': .78}}} ])
def test_receipt_kind_schema_and_tenant_scope(tmp_path, parsed):
    path = tmp_path / 'audit.sqlite'
    conn = sqlite3.connect(path)
    conn.executescript('CREATE TABLE pec_messages(id TEXT, tenant_id TEXT, received_at TEXT); CREATE TABLE pec_validation_reports(message_id TEXT,report_json TEXT,parsed_version_id TEXT); CREATE TABLE pec_parsed_versions(id TEXT,parsed_json TEXT); CREATE TABLE pec_attachments(message_id TEXT,filename TEXT,attachment_index INT);')
    for mid, owner in [('pec_a','own'),('pec_b','own'),('pec_private','other')]:
        conn.execute('INSERT INTO pec_messages VALUES (?,?,?)',(mid,owner,'2026-06-04T07:14:38Z'))
        conn.execute('INSERT INTO pec_parsed_versions VALUES (?,?)',(mid,json.dumps(parsed)))
        conn.execute('INSERT INTO pec_validation_reports VALUES (?,?,?)',(mid,'{}',mid))
        conn.execute('INSERT INTO pec_attachments VALUES (?,?,?)',(mid,'daticert.xml',0))
    conn.commit(); conn.close()
    item=SimpleNamespace(note='PEC_AUDIT:pec_a\nPEC_AUDIT:pec_b\nPEC_AUDIT:pec_private',titolo='Storico')
    loaded=latest_pec_profiles([item],pec_audit_db=str(path),tenant_id='own')
    assert set(loaded)=={'pec_a','pec_b'}
    candidates=pec_profile_for_item(item,loaded)['_source_candidates']
    assert all(c['receiptKind']=='accettazione' for c in candidates)
    assert all(c['receivedAt']=='2026-06-04T07:14:38Z' for c in candidates)
    conn=sqlite3.connect(path)
    assert conn.total_changes==0
    assert conn.execute('SELECT count(*) FROM pec_messages').fetchone()[0]==3
    conn.close()


def test_formatted_xml_does_not_add_blank_lines_or_alter_mixed_content():
    text='<?xml version="1.0" encoding="UTF-8"?>\n<root>\n  <p>è — &amp; <b>testo</b> finale</p>\n  <x><![CDATA[<script>é</script>]]></x>\n</root>'
    data=text.encode('utf-8')
    assert _format_xml_text(data)==text
    result=render_xml_preview('prova.xml',data,signed=False).data.decode('utf-8')
    assert 'role="region"' in result and 'aria-label="Contenuto del documento"' in result and 'tabindex="0"' in result
    assert '<script>é</script>' not in result
    assert '&lt;script&gt;é&lt;/script&gt;' in result
    assert data==text.encode('utf-8')


def test_compact_xml_stays_readable_and_invalid_xml_is_not_lost():
    assert '\n' in _format_xml_text(b'<root><a>1</a><b>2</b></root>')
    assert _format_xml_text(b'<root>unclosed')=='<root>unclosed'