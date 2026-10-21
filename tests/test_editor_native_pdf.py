from __future__ import annotations

import hashlib
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import fitz
import pytest
from flask import Flask, g

from web.bootstrap.editor_native_pdf_routes import register_editor_native_pdf_routes


def pdf_bytes(text):
    with fitz.open() as pdf:
        pdf.new_page().insert_text((72, 72), text)
        return pdf.tobytes()


@pytest.fixture
def native_editor(tmp_path):
    path = tmp_path / 'atto.pdf'
    original = pdf_bytes('Originale dello studio')
    path.write_bytes(original)
    doc = SimpleNamespace(id='doc', nome='Atto.pdf', eliminato_il='', fonte_documento='REDAZIONE_STUDIO',
                          hash_sha256=hashlib.sha256(original).hexdigest(), hash_contenuto_sha256='',
                          note='', caricato_da='avvocato', versioni=[])
    writes, events, audits = [], [], []

    class Repository:
        _studio_db = object()

        def get(self, fid):
            return SimpleNamespace(documenti=[doc] if fid == 'case' else [])

        def percorso_documento_lettura(self, *_):
            return path

        def sostituisci_documento(self, fid, did, **values):
            writes.append(values)
            doc.versioni.append(path.read_bytes())
            path.write_bytes(values['contenuto'])
            doc.hash_sha256 = hashlib.sha256(values['contenuto']).hexdigest()
            doc.hash_contenuto_sha256 = values['hash_contenuto_sha256']
            doc.note, doc.caricato_da = values['note'], values['caricato_da']
            return doc

    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def context():
        g.utente_corrente = SimpleNamespace(username='avvocato', ha_permesso=lambda _: app.config.get('ALLOW', True))
        g.data_paths = {'FASCICOLI_DB': str(tmp_path / 'fascicoli.json')}

    register_editor_native_pdf_routes(app, get_fascicoli=Repository, decrypt_doc=lambda b: b,
                                     encrypt_doc=lambda b: b, audit=lambda *a, **kw: audits.append((a, kw)),
                                     document_updated=lambda *a: events.append(a))
    return app, doc, path, writes, events, audits, original


def save(client, content, expected, command=None, *, path='/api/v1/ui/fascicoli/case/documenti/doc/pdf-diretto'):
    return client.post(path, headers={'X-Requested-With': 'XMLHttpRequest'}, data={
        'file': (BytesIO(content), 'Atto.pdf'), 'expectedHash': expected,
        'commandId': command or str(uuid4()),
    })


def test_native_read_does_not_modify_or_process_document(native_editor):
    app, doc, _, writes, events, audits, original = native_editor
    with app.test_client() as client:
        result = client.get('/api/v1/ui/fascicoli/case/documenti/doc/pdf-diretto', query_string={'expectedHash': doc.hash_sha256})
    assert result.status_code == 200
    assert result.data == original
    assert result.headers['Cache-Control'] == 'no-store'
    assert writes == events == audits == []


def test_public_editor_is_network_restricted_without_exposing_document_api(native_editor):
    app, doc, *_ = native_editor
    with app.test_client() as client:
        asset = client.get('/static/vendor/pdfcraft-direct/editor/index.html')
        source = client.get('/api/v1/ui/fascicoli/case/documenti/doc/pdf-diretto',
                            query_string={'expectedHash': doc.hash_sha256})
    policy = asset.headers['Content-Security-Policy']
    assert "connect-src 'self' blob:" in policy
    assert "form-action 'none'" in policy
    assert "default-src 'none'" in policy
    assert 'https:' not in policy and 'http:' not in policy
    assert asset.headers['Access-Control-Allow-Origin'] == '*'
    assert 'Access-Control-Allow-Origin' not in source.headers


def test_signed_pdf_bytes_are_rejected_even_when_metadata_claims_editable(native_editor, monkeypatch):
    app, doc, path, writes, events, _, original = native_editor
    monkeypatch.setattr('pct.document_signature_state.document_bytes_have_real_digital_signature',
                        lambda *_: True)
    with app.test_client() as client:
        result = save(client, pdf_bytes('Non sostituire una firma'), doc.hash_sha256)
    assert result.status_code == 400
    assert 'firmato' in result.json['message']
    assert writes == events == []
    assert path.read_bytes() == original


def test_save_retry_preserves_original_and_writes_once(native_editor):
    app, doc, path, writes, events, audits, original = native_editor
    expected, command, edited = doc.hash_sha256, str(uuid4()), pdf_bytes('Testo modificato')
    with app.test_client() as client:
        first = save(client, edited, expected, command)
        retry = save(client, edited, expected, command)
        incompatible = save(client, pdf_bytes('Altra modifica'), expected, command)
    assert first.status_code == retry.status_code == 200
    assert retry.json['alreadyPresent'] is True
    assert incompatible.status_code == 409
    assert len(writes) == len(events) == 1
    assert doc.versioni == [original]
    assert path.read_bytes() == edited
    assert len(audits) == 2


def test_concurrent_old_revision_cannot_overwrite_new_version(native_editor):
    app, doc, path, writes, _, _, _ = native_editor
    expected, first = doc.hash_sha256, pdf_bytes('Prima modifica')
    with app.test_client() as client:
        assert save(client, first, expected).status_code == 200
        assert save(client, pdf_bytes('Modifica concorrente'), expected).status_code == 409
    assert len(writes) == 1
    assert path.read_bytes() == first


@pytest.mark.parametrize('case', ['permission', 'external', 'deleted', 'other-matter', 'invalid-file'])
def test_native_editor_rejects_unauthorized_or_invalid_save(native_editor, case):
    app, doc, path, writes, events, _, original = native_editor
    if case == 'permission':
        app.config['ALLOW'] = False
    if case == 'external':
        doc.fonte_documento = 'PORTALE'
    if case == 'deleted':
        doc.eliminato_il = '2026-10-21'
    endpoint = '/api/v1/ui/fascicoli/other/documenti/doc/pdf-diretto' if case == 'other-matter' else '/api/v1/ui/fascicoli/case/documenti/doc/pdf-diretto'
    with app.test_client() as client:
        result = save(client, b'not pdf' if case == 'invalid-file' else pdf_bytes('Tentativo'), doc.hash_sha256, path=endpoint)
    assert result.status_code in {400, 403, 404}
    assert writes == events == []
    assert path.read_bytes() == original
