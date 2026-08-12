import hashlib
from datetime import UTC, datetime, timedelta

from asn1crypto import cms, tsp
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pct.firma_pkcs11 import build_cades_signed_attrs_der
from tools import local_signer


def _attr_types(der: bytes) -> set[str]:
    attrs = cms.CMSAttributes.load(der)
    result: set[str] = set()
    for attr in attrs:
        result.add(str(attr["type"].native or attr["type"].dotted))
        result.add(str(attr["type"].dotted))
    return result


def _certificate_der() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


def test_cades_signed_attrs_includono_profilo_bes_per_dati_atto():
    digest = hashlib.sha256(b"<DatiAtto>test</DatiAtto>").digest()
    cert_der = _certificate_der()

    types = _attr_types(build_cades_signed_attrs_der(digest, cert_der=cert_der))

    assert "content_type" in types
    assert "message_digest" in types
    assert "signing_time" in types
    assert "1.2.840.113549.1.9.16.2.47" in types

    attrs = cms.CMSAttributes.load(build_cades_signed_attrs_der(digest, cert_der=cert_der))
    signing_cert = next(
        attr for attr in attrs if attr["type"].dotted == "1.2.840.113549.1.9.16.2.47"
    )
    parsed = tsp.SigningCertificateV2.load(signing_cert["values"][0].dump())
    assert parsed["certs"][0]["cert_hash"].native == hashlib.sha256(cert_der).digest()
    assert parsed["certs"][0]["issuer_serial"]["serial_number"].native


def test_local_signer_inline_usa_gli_stessi_attributi_cades():
    types = _attr_types(
        local_signer._build_signed_attrs_der_inline(
            b"<DatiAtto>test</DatiAtto>",
            cert_der=_certificate_der(),
        )
    )

    assert "signing_time" in types
    assert "1.2.840.113549.1.9.16.2.47" in types


def test_local_signer_windows_usa_valore_signing_certificate_v2_standard():
    cert_der = _certificate_der()

    value = tsp.SigningCertificateV2.load(
        local_signer._signing_certificate_v2_value_der_inline(cert_der)
    )

    assert value["certs"][0]["cert_hash"].native == hashlib.sha256(cert_der).digest()
    assert value["certs"][0]["issuer_serial"]["serial_number"].native
