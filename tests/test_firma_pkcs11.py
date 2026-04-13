from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pct.firma_pkcs11 as firma_pkcs11


def test_libreria_disponibile_prefers_best_scored_candidate(monkeypatch):
    monkeypatch.delenv(firma_pkcs11._ENV_LIBRARY, raising=False)
    monkeypatch.setattr(
        firma_pkcs11,
        "_candidate_libraries",
        lambda: ["C:\\fake\\legacy.dll", "C:\\fake\\bit4xpki.dll"],
    )
    monkeypatch.setattr(
        firma_pkcs11,
        "_score_library",
        lambda path: 1 if path.endswith("legacy.dll") else 3,
    )

    assert firma_pkcs11.libreria_disponibile() == "C:\\fake\\bit4xpki.dll"


def test_libreria_disponibile_accetta_override_env_esistente(monkeypatch, tmp_path):
    override = tmp_path / "bit4xpki.dll"
    override.write_text("stub", encoding="utf-8")
    monkeypatch.setenv(firma_pkcs11._ENV_LIBRARY, str(override))

    assert firma_pkcs11.libreria_disponibile() == str(override)


def test_windows_candidates_include_bit4xpki():
    assert any("bit4xpki.dll" in lib.lower() for lib in firma_pkcs11._LIBRERIE_DEFAULT)


def test_build_cades_bes_embeds_content_and_certificate():
    from asn1crypto import cms
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test PKCS11"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    documento = b"%PDF-1.4\n% cades test\n%%EOF"
    digest = hashes.Hash(hashes.SHA256())
    digest.update(documento)
    signed_attrs_der = firma_pkcs11.FirmaPKCS11._build_signed_attrs(
        object.__new__(firma_pkcs11.FirmaPKCS11),
        digest.finalize(),
    )
    signature = key.sign(signed_attrs_der, padding.PKCS1v15(), hashes.SHA256())

    envelope = firma_pkcs11._build_cades_bes(
        documento=documento,
        signature_bytes=signature,
        cert_der=cert.public_bytes(serialization.Encoding.DER),
        signed_attrs_der=signed_attrs_der,
        detached=False,
    )

    content_info = cms.ContentInfo.load(envelope)
    assert content_info["content_type"].native == "signed_data"
    signed_data = content_info["content"]
    assert len(signed_data["signer_infos"]) == 1
    assert len(signed_data["certificates"]) == 1
    assert signed_data["encap_content_info"]["content"].native == documento
