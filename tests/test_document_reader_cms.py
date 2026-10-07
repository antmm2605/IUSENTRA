from datetime import datetime, timezone
from hashlib import sha256

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from web.services.document_reader_cms import detached_signature_preview


@pytest.fixture(scope='module')
def signature():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, '<script>Nome & prova</script>')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(123)
            .not_valid_before(datetime(2026, 10, 6, 9, 30, tzinfo=timezone.utc))
            .not_valid_after(datetime(2027, 10, 6, 9, 30, tzinfo=timezone.utc))
            .sign(key, hashes.SHA256()))
    return (pkcs7.PKCS7SignatureBuilder().set_data(b'contenuto riservato')
            .add_signer(cert, key, hashes.SHA256()))


@pytest.mark.parametrize('encoding', [serialization.Encoding.DER, serialization.Encoding.PEM])
def test_real_detached_signature_metadata_without_claiming_validity(signature, encoding):
    data = signature.sign(encoding, [pkcs7.PKCS7Options.DetachedSignature])
    html, status, headers = detached_signature_preview(data, '/api/v1/ui/email/source/P1?download=1')
    assert status == 200
    assert 'role="alert"' not in html
    assert 'Firmatari dichiarati</dt><dd>1' in html
    assert '06/10/2026 11:30' in html
    assert '&lt;script&gt;Nome &amp; prova&lt;/script&gt;' in html
    assert '<script>' not in html
    assert 'contenuto riservato' not in html
    assert 'Validità della firma non verificata' in html
    assert sha256(data).hexdigest() in html
    assert 'private, no-store' == headers['Cache-Control']
    assert 'charset=utf-8' in headers['Content-Type']


@pytest.mark.parametrize('data', [b'', b'firma non valida', b'A' * (8 * 1024 * 1024 + 1)])
def test_invalid_or_oversized_signature_preserves_original_and_explicit_error(data):
    html, status, _ = detached_signature_preview(data, '/api/v1/ui/email/source/P1?download=1')
    assert status == 200
    assert 'role="alert"' in html
    assert 'Il file originale resta scaricabile.' in html
    assert sha256(data).hexdigest() in html
    assert 'Firmatari dichiarati' not in html


def test_attached_signature_is_not_mislabeled_as_detached(signature):
    data = signature.sign(serialization.Encoding.DER, [])
    html, _, _ = detached_signature_preview(data, '/api/v1/ui/email/source/P1?download=1')
    assert 'role="alert"' in html
    assert 'Firma CMS / S/MIME separata</dd>' not in html


def test_external_download_url_is_rejected():
    html, _, _ = detached_signature_preview(b'invalid', 'https://other.example/file?secret=1')
    assert 'other.example' not in html
    assert 'secret=1' not in html
