"""Controlli regressivi su un documento CAdES realmente firmato ma non fidato."""

import asyncio
import io
from datetime import datetime, timedelta, timezone

import pytest
from asn1crypto import cms, keys, x509 as asn1_x509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.sign.signers import SimpleSigner
from pyhanko.sign.validation.qualified.tsp import TSPRegistry
from pyhanko_certvalidator.registry import SimpleCertificateStore

from pct import eidas_document_validation as validation


def _signer() -> SimpleSigner:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Firma di prova")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return SimpleSigner(
        signing_cert=asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER)),
        signing_key=keys.PrivateKeyInfo.load(key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )),
        cert_registry=SimpleCertificateStore(),
    )


def _signed_cades() -> bytes:
    return asyncio.run(_signer().async_sign_general_data(
        b"Documento di prova", "sha256", detached=False, use_cades=True,
    )).dump()


def test_firma_integra_senza_trust_non_diventa_qualificata(monkeypatch):
    monkeypatch.setattr(validation, "_trusted_registry", lambda: (
        TSPRegistry(), {"paesi_verificati": ["IT"], "paesi_non_disponibili": ["SK"]},
    ))
    result = validation.verifica_documento_eidas(_signed_cades(), "prova.pdf.p7m")
    assert len(result["firme"]) == 1
    signature = result["firme"][0]
    assert signature["integrita"] is True
    assert signature["catena_fidata"] is False
    assert signature["revoca_verificata"] is False
    assert signature["certificato_qualificato"] is False
    assert signature["esito"] == "non_determinabile"


def test_firma_detached_senza_originale_non_viene_validata(monkeypatch):
    monkeypatch.setattr(validation, "_trusted_registry", lambda: (
        TSPRegistry(), {"paesi_verificati": ["IT"], "paesi_non_disponibili": []},
    ))
    signed = cms.ContentInfo.load(_signed_cades())
    signed["content"]["encap_content_info"]["content"] = None
    with pytest.raises(ValueError, match="documento originale"):
        validation.verifica_documento_eidas(signed.dump(), "prova.p7s")


def test_p7m_senza_busta_leggibile_non_e_promosso(monkeypatch):
    monkeypatch.setattr(validation, "_trusted_registry", lambda: (
        TSPRegistry(), {"paesi_verificati": ["IT"], "paesi_non_disponibili": []},
    ))
    with pytest.raises(ValueError, match="busta CAdES leggibile"):
        validation.verifica_documento_eidas(b"<xml>contenuto</xml>", "prova.xml.p7m")


def test_p7m_senza_firmatari_non_e_promosso(monkeypatch):
    monkeypatch.setattr(validation, "_trusted_registry", lambda: (
        TSPRegistry(), {"paesi_verificati": ["IT"], "paesi_non_disponibili": []},
    ))
    signed = cms.ContentInfo.load(_signed_cades())
    signed["content"]["signer_infos"] = cms.SignerInfos([])
    with pytest.raises(ValueError, match="non contiene firmatari"):
        validation.verifica_documento_eidas(signed.dump(), "prova.p7m")


def test_pades_autofirmato_non_diventa_qualificato(monkeypatch):
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from reportlab.pdfgen import canvas

    monkeypatch.setattr(validation, "_trusted_registry", lambda: (
        TSPRegistry(), {"paesi_verificati": ["IT"], "paesi_non_disponibili": []},
    ))
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Documento di prova")
    pdf.save()
    signed = signers.sign_pdf(
        IncrementalPdfFileWriter(io.BytesIO(buffer.getvalue())),
        signers.PdfSignatureMetadata(field_name="Firma1"),
        signer=_signer(),
    ).getvalue()
    result = validation.verifica_documento_eidas(signed, "prova.pdf")
    assert len(result["firme"]) == 1
    assert result["firme"][0]["certificato_qualificato"] is False
    assert result["firme"][0]["esito"] == "non_determinabile"
