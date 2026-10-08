import hashlib
from types import SimpleNamespace

import pytest

from web.services.sentenza_archiviazione_runtime import _contenuto_firmato_verificato


def test_signed_source_keeps_container_and_inner_document_proof(monkeypatch):
    container, content = b'CMS-container', b'%PDF-original'
    stored_hash = hashlib.sha256(b'encrypted-container').hexdigest()
    content_hash = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr('pct.firme_cades.inspect_signed_document_bytes', lambda **kw:
        SimpleNamespace(payload_bytes=content, status=SimpleNamespace(payload_name='original.pdf')))
    data, name, proof = _contenuto_firmato_verificato(container, nome='original.pdf.p7m',
        sha256=content_hash, sha256_archivio=stored_hash, stored_sha256=stored_hash)
    assert (data, name) == (content, 'original.pdf')
    assert proof['signed_container_sha256'] == hashlib.sha256(container).hexdigest()
    assert proof['content_sha256'] == content_hash
    assert 'signature_verified' not in proof


def test_changed_stored_source_is_rejected_before_inspection(monkeypatch):
    def unexpected(**kwargs):
        pytest.fail('Un contenitore cambiato non deve essere ispezionato come prova SQL')
    monkeypatch.setattr('pct.firme_cades.inspect_signed_document_bytes', unexpected)
    with pytest.raises(ValueError, match='file conservato'):
        _contenuto_firmato_verificato(b'CMS', nome='file.p7m', sha256='a'*64,
            sha256_archivio='b'*64, stored_sha256='c'*64)


@pytest.mark.parametrize('payload', [None, b'CMS', b'other-document'])
def test_wrong_or_missing_inner_document_is_rejected(monkeypatch, payload):
    monkeypatch.setattr('pct.firme_cades.inspect_signed_document_bytes', lambda **kw:
        SimpleNamespace(payload_bytes=payload, status=SimpleNamespace(payload_name='file.pdf')))
    with pytest.raises(ValueError, match='originale'):
        _contenuto_firmato_verificato(b'CMS', nome='file.p7m', sha256=hashlib.sha256(b'expected').hexdigest(),
            sha256_archivio='b'*64, stored_sha256='b'*64)
