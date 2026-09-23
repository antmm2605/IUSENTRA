from __future__ import annotations

import io
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


def test_firma_pades_pkcs11_riproduce_profilo_studio_telematico(monkeypatch):
    from asn1crypto import keys
    from asn1crypto import x509 as asn1_x509
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from pyhanko.sign import pkcs11 as pyhanko_pkcs11
    from pyhanko.sign import signers
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
        x509.NameAttribute(NameOID.COMMON_NAME, "GIUSEPPE MONTAGNESE"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    key_der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    software_signer = signers.SimpleSigner(
        signing_cert=asn1_x509.Certificate.load(cert_der),
        signing_key=keys.PrivateKeyInfo.load(key_der),
        cert_registry=SimpleCertificateStore(),
    )
    monkeypatch.setattr(
        pyhanko_pkcs11,
        "PKCS11Signer",
        lambda *args, **kwargs: software_signer,
    )

    signer = object.__new__(firma_pkcs11.FirmaPKCS11)
    signer._cert_der = cert_der
    signer._cert_id = b"firma"
    signer._cert_chain_der = []
    signer._certificate = cert
    signer._session = object()

    source = io.BytesIO()
    pdf = canvas.Canvas(source)
    pdf.drawString(72, 720, "Ricorso")
    pdf.save()

    # Riproduce la cache ASN.1 inizializzata prima degli attributi ESS:
    # il flusso deve funzionare anche dopo una precedente firma CAdES.
    from asn1crypto import cms
    cms.CMSAttributeType("content_type")
    monkeypatch.delitem(cms.CMSAttributeType._reverse_map, "signing_certificate_v2", raising=False)
    signed = signer.firma_pades(source.getvalue(), visible_signature_place="Taurianova")
    reader = PdfReader(io.BytesIO(signed))
    fields = reader.get_fields()
    signature = fields["Signature1"]["/V"]
    from visible_signature import VISIBLE_SIGNATURE_METADATA_KEY, has_visible_signature_stamp

    assert signed.startswith(b"%PDF")
    assert has_visible_signature_stamp(signed) is True
    assert "Modalita firma visibile: laterale" in str(
        (reader.metadata or {}).get(VISIBLE_SIGNATURE_METADATA_KEY, "")
    )
    rendered_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Firmato Da: AVV. GIUSEPPE MONTAGNESE" in rendered_text
    assert "Luogo firma: TAURIANOVA" in rendered_text
    assert signature["/SubFilter"] == "/ETSI.CAdES.detached"
    assert signature["/Reason"] == "Per autentica e sottoscrizione"
    assert signature["/Location"] == "Taurianova"
    assert signature["/Name"] == "GIUSEPPE MONTAGNESE"


def test_prepare_pdf_usa_get_cert_non_self_cert(monkeypatch):
    from datetime import UTC, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
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

    signer = object.__new__(firma_pkcs11.FirmaPKCS11)
    signer._certificate = cert
    signer._cert_der = cert.public_bytes(serialization.Encoding.DER)
    signer._lib = None
    signer._session = None

    captured = {}

    def _fake_prepare(
        doc,
        *,
        intestatario="",
        data_firma=None,
        luogo="",
        issuer="",
        serial="",
        mode="laterale",
        datetime_mode="data_ora",
    ):
        captured["called"] = True
        captured["issuer"] = issuer
        captured["serial"] = serial
        captured["datetime_mode"] = datetime_mode
        return doc

    monkeypatch.setattr("visible_signature.prepare_document_for_signature", _fake_prepare)
    import visible_signature as _vs
    monkeypatch.setattr(_vs, "prepare_document_for_signature", _fake_prepare)
    import pct.firma_pkcs11 as _pk
    monkeypatch.setattr(_pk, "prepare_document_for_signature", _fake_prepare)

    pdf = b"%PDF-1.4\nstub\n%%EOF"
    result = signer._prepare_pdf_for_visible_signature(pdf, visible_signature_mode="basso_sinistra")

    assert result == pdf
    assert captured.get("called") is True


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


def test_pkcs11_prepare_pdf_for_visible_signature_usa_get_cert_senza_self_cert(monkeypatch):
    signer = object.__new__(firma_pkcs11.FirmaPKCS11)
    captured = {}

    class _Attr:
        value = "CA Test"

    class _Issuer:
        def get_attributes_for_oid(self, _oid):
            return [_Attr()]

    class _Cert:
        issuer = _Issuer()
        subject = _Issuer()
        serial_number = 0xABC123

    def _fake_prepare(documento, **kwargs):
        captured.update(kwargs)
        return documento + b"\n% visible"

    monkeypatch.setattr(firma_pkcs11.FirmaPKCS11, "_get_cert", lambda _self: _Cert())
    monkeypatch.setattr(firma_pkcs11, "prepare_document_for_signature", _fake_prepare)

    out = signer._prepare_pdf_for_visible_signature(
        b"%PDF-1.4\nstub\n%%EOF",
        visible_signature_mode="basso_sinistra",
        visible_signature_place="Taurianova",
    )

    assert out.endswith(b"% visible")
    assert captured["issuer"] == "CA Test"
    assert captured["serial"] == "ABC123"
    assert captured["mode"] == "basso_sinistra"


def test_cades_additional_signature_is_parallel_and_preserves_previous_signature():
    import hashlib

    from asn1crypto import cms
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.document_signature_state import verify_additional_signature

    def certificate(common_name: str):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(UTC) - timedelta(days=1))
            .not_valid_after(datetime.now(UTC) + timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        return key, cert.public_bytes(serialization.Encoding.DER)

    def sign(content: bytes, key, cert_der: bytes, *, existing: bytes | None = None):
        signed_attrs = firma_pkcs11.build_cades_signed_attrs_der(
            hashlib.sha256(content).digest(),
            cert_der=cert_der,
        )
        signature = key.sign(signed_attrs, padding.PKCS1v15(), hashes.SHA256())
        return firma_pkcs11._build_cades_bes(
            documento=content,
            signature_bytes=signature,
            cert_der=cert_der,
            signed_attrs_der=signed_attrs,
            detached=False,
            existing_cades=existing,
        )

    content = b"%PDF-1.4\nDocumento con due firmatari\n%%EOF"
    first_key, first_cert = certificate("Primo firmatario")
    second_key, second_cert = certificate("Avvocato cofirmatario")
    first_envelope = sign(content, first_key, first_cert)
    first_info = cms.ContentInfo.load(first_envelope, strict=True)
    preserved_signer = first_info["content"]["signer_infos"][0].dump()

    parallel_envelope = sign(
        content,
        second_key,
        second_cert,
        existing=first_envelope,
    )
    parallel_info = cms.ContentInfo.load(parallel_envelope, strict=True)
    parallel_data = parallel_info["content"]

    assert parallel_data["encap_content_info"]["content"].native == content
    assert len(parallel_data["signer_infos"]) == 2
    assert len(parallel_data["certificates"]) == 2
    assert preserved_signer in {
        signer.dump() for signer in parallel_data["signer_infos"]
    }
    assert parallel_data["encap_content_info"]["content"].native != first_envelope
    verify_additional_signature(
        first_envelope,
        parallel_envelope,
        "documento.pdf.p7m",
    )


def test_cades_additional_signature_rejects_nested_container():
    import hashlib

    import pytest
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.document_signature_state import verify_additional_signature

    def certificate(common_name: str):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(UTC) - timedelta(days=1))
            .not_valid_after(datetime.now(UTC) + timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        return key, cert.public_bytes(serialization.Encoding.DER)

    def sign(content: bytes, key, cert_der: bytes):
        signed_attrs = firma_pkcs11.build_cades_signed_attrs_der(
            hashlib.sha256(content).digest(),
            cert_der=cert_der,
        )
        signature = key.sign(signed_attrs, padding.PKCS1v15(), hashes.SHA256())
        return firma_pkcs11._build_cades_bes(
            documento=content,
            signature_bytes=signature,
            cert_der=cert_der,
            signed_attrs_der=signed_attrs,
            detached=False,
        )

    content = b"%PDF-1.4\nDocumento da non annidare\n%%EOF"
    first_key, first_cert = certificate("Primo firmatario")
    second_key, second_cert = certificate("Secondo firmatario")
    first_envelope = sign(content, first_key, first_cert)
    nested_envelope = sign(first_envelope, second_key, second_cert)

    with pytest.raises(ValueError, match="annidata|stesso contenuto"):
        verify_additional_signature(
            first_envelope,
            nested_envelope,
            "documento.pdf.p7m",
        )

    nested_attrs = firma_pkcs11.build_cades_signed_attrs_der(
        hashlib.sha256(first_envelope).digest(),
        cert_der=second_cert,
    )
    nested_signature = second_key.sign(
        nested_attrs,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    with pytest.raises(ValueError, match="annidata"):
        firma_pkcs11._build_cades_bes(
            documento=first_envelope,
            signature_bytes=nested_signature,
            cert_der=second_cert,
            signed_attrs_der=nested_attrs,
            detached=False,
            existing_cades=nested_envelope,
        )
