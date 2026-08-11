import hashlib

from asn1crypto import cms

from pct.firma_pkcs11 import build_cades_signed_attrs_der
from tools import local_signer


def _attr_types(der: bytes) -> set[str]:
    attrs = cms.CMSAttributes.load(der)
    result: set[str] = set()
    for attr in attrs:
        result.add(str(attr["type"].native or attr["type"].dotted))
        result.add(str(attr["type"].dotted))
    return result


def test_cades_signed_attrs_includono_profilo_bes_per_dati_atto():
    digest = hashlib.sha256(b"<DatiAtto>test</DatiAtto>").digest()
    cert_der = b"certificato-der-di-test"

    types = _attr_types(build_cades_signed_attrs_der(digest, cert_der=cert_der))

    assert "content_type" in types
    assert "message_digest" in types
    assert "signing_time" in types
    assert "1.2.840.113549.1.9.16.2.47" in types


def test_local_signer_inline_usa_gli_stessi_attributi_cades():
    types = _attr_types(
        local_signer._build_signed_attrs_der_inline(
            b"<DatiAtto>test</DatiAtto>",
            cert_der=b"certificato-der-di-test",
        )
    )

    assert "signing_time" in types
    assert "1.2.840.113549.1.9.16.2.47" in types
