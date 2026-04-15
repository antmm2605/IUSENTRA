from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

import pct.firma_pkcs11 as firma_pkcs11
from pct.firma import FirmaDigitale


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


def test_pkcs11_active_probe_disabled_by_default_on_windows(monkeypatch):
    monkeypatch.delenv(firma_pkcs11._ENV_ACTIVE_PROBE, raising=False)
    monkeypatch.setattr(firma_pkcs11.os, "name", "nt")

    assert firma_pkcs11._pkcs11_active_probe_enabled() is False


def test_score_library_uses_passive_probe_when_disabled(tmp_path, monkeypatch):
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_text("stub", encoding="utf-8")
    monkeypatch.setattr(firma_pkcs11, "_pkcs11_active_probe_enabled", lambda: False)
    monkeypatch.setitem(sys.modules, "pkcs11", object())

    assert firma_pkcs11._score_library(str(dll_path)) == 2


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


def test_salva_documento_firmato_pkcs11_pdf_usa_cades_contenente_pdf(tmp_path, monkeypatch):
    signer = object.__new__(firma_pkcs11.FirmaPKCS11)
    captured = {}

    def _fake_firma_cades(
        documento,
        detached=True,
        visible_signature_mode="laterale",
        visible_signature_place="",
    ):
        captured["documento"] = documento
        captured["detached"] = detached
        captured["visible_signature_mode"] = visible_signature_mode
        captured["visible_signature_place"] = visible_signature_place
        return b"firmato"

    monkeypatch.setattr(signer, "firma_cades", _fake_firma_cades)

    output = signer.salva_documento_firmato(
        b"%PDF-1.4\nstub\n%%EOF",
        str(tmp_path / "atto.pdf"),
        visible_signature_mode="laterale",
        visible_signature_place="Taurianova",
    )

    assert output.endswith(".p7m")
    assert captured["detached"] is False
    assert captured["visible_signature_mode"] == "laterale"
    assert captured["visible_signature_place"] == "Taurianova"


def test_salva_documento_firmato_standard_pdf_usa_cades_contenente_pdf(tmp_path, monkeypatch):
    signer = object.__new__(FirmaDigitale)
    captured = {}

    def _fake_firma_cades(
        documento,
        detached=True,
        visible_signature_mode="laterale",
        visible_signature_place="",
    ):
        captured["documento"] = documento
        captured["detached"] = detached
        captured["visible_signature_mode"] = visible_signature_mode
        captured["visible_signature_place"] = visible_signature_place
        return b"firmato"

    monkeypatch.setattr(signer, "firma_cades", _fake_firma_cades)

    output = signer.salva_documento_firmato(
        b"%PDF-1.4\nstub\n%%EOF",
        str(tmp_path / "atto.pdf"),
        visible_signature_mode="basso_destra",
        visible_signature_place="Taurianova",
    )

    assert output.endswith(".p7m")
    assert captured["detached"] is False
    assert captured["visible_signature_mode"] == "basso_destra"
    assert captured["visible_signature_place"] == "Taurianova"
