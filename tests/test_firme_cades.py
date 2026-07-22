from __future__ import annotations

from pathlib import Path
import subprocess

from asn1crypto import algos, cms

import pct.firme_cades as firme_cades
from pct.firme_cades import inspect_signed_document_bytes, verify_and_extract_p7m


def _build_p7m(payload: bytes | None) -> bytes:
    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data", **({"content": payload} if payload is not None else {})},
            "signer_infos": [],
        }
    )
    return cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()


def test_inspect_signed_document_bytes_supporta_payload_embedded_pdf():
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    prepared = inspect_signed_document_bytes(
        source_name="ordinanza.pdf.p7m",
        data=_build_p7m(pdf_bytes),
    )

    assert prepared.status.is_signed_container is True
    assert prepared.status.payload_available is True
    assert prepared.status.embedded_payload is True
    assert prepared.status.detached_signature is False
    assert prepared.status.payload_mime == "application/pdf"
    assert prepared.status.payload_name == "ordinanza.pdf"
    assert prepared.payload_bytes == pdf_bytes


def test_inspect_signed_document_bytes_distingue_detached_con_originale():
    pdf_bytes = b"%PDF-1.4\n% detached\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    prepared = inspect_signed_document_bytes(
        source_name="verbale.pdf.p7m",
        data=_build_p7m(None),
        original_detached_bytes=pdf_bytes,
        original_detached_name="verbale.pdf",
    )

    assert prepared.status.payload_available is True
    assert prepared.status.embedded_payload is False
    assert prepared.status.detached_signature is True
    assert prepared.status.payload_mime == "application/pdf"
    assert prepared.status.payload_name == "verbale.pdf"
    assert prepared.payload_bytes == pdf_bytes


def test_verify_and_extract_p7m_salva_payload_estratto(tmp_path: Path):
    payload = b"%PDF-1.4\n% extracted\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    p7m_path = tmp_path / "decreto.pdf.p7m"
    p7m_path.write_bytes(_build_p7m(payload))

    status = verify_and_extract_p7m(p7m_path, tmp_path / "estratti")

    assert status.payload_available is True
    assert status.payload_path
    extracted_path = Path(status.payload_path)
    assert extracted_path.exists() is True
    assert extracted_path.name == "decreto.pdf"
    assert extracted_path.read_bytes() == payload


def test_openssl_ha_timeout_e_diagnostica_limitata(monkeypatch):
    def _timeout(*_args, **kwargs):
        assert kwargs["timeout"] == firme_cades.OPENSSL_COMMAND_TIMEOUT_SECONDS
        assert kwargs["stdin"] is subprocess.DEVNULL
        raise subprocess.TimeoutExpired(cmd="openssl", timeout=kwargs["timeout"])

    monkeypatch.setattr(firme_cades.subprocess, "run", _timeout)

    ok, details = firme_cades._run_command(["openssl", "version"])

    assert ok is False
    assert "tempo massimo" in details
    assert len(details) <= firme_cades.MAX_OPENSSL_DIAGNOSTIC_CHARS


def test_inspect_blocca_output_openssl_oltre_budget_prima_della_lettura(monkeypatch):
    monkeypatch.setattr(firme_cades, "MAX_SIGNED_PAYLOAD_BYTES", 8)
    monkeypatch.setattr(firme_cades, "_openssl_available", lambda: True)

    def _oversized_output(_source: Path, output: Path):
        output.write_bytes(b"123456789")
        return True, "ok"

    for function_name in (
        "_extract_with_openssl_smime",
        "_extract_with_openssl_cms",
        "_extract_with_openssl_cms_auto",
        "_extract_with_openssl_smime_auto",
    ):
        monkeypatch.setattr(firme_cades, function_name, _oversized_output)

    prepared = inspect_signed_document_bytes(
        source_name="firma.p7m",
        data=b"contenitore-senza-payload",
    )

    assert prepared.payload_bytes is None
    assert prepared.status.payload_available is False
    assert "limite di sicurezza" in str(prepared.status.technical_details)


def test_inspect_blocca_contenitore_firmato_oltre_budget_senza_avviare_openssl(monkeypatch):
    monkeypatch.setattr(firme_cades, "MAX_SIGNED_CONTAINER_BYTES", 8)

    def _unexpected_openssl(*_args, **_kwargs):
        raise AssertionError("OpenSSL non deve partire oltre il budget del contenitore")

    monkeypatch.setattr(firme_cades, "_openssl_available", _unexpected_openssl)
    monkeypatch.setattr(firme_cades, "_extract_with_openssl_smime", _unexpected_openssl)

    prepared = inspect_signed_document_bytes(
        source_name="firma.p7m",
        data=b"123456789",
    )

    assert prepared.payload_bytes is None
    assert prepared.status.extraction_attempted is False
    assert "supera il limite di sicurezza" in prepared.status.message


def test_inspect_riconosce_smime_da_mime_senza_estensione_p7m():
    payload = b'<?xml version="1.0"?><Comunicazione />'

    prepared = inspect_signed_document_bytes(
        source_name="smime-contenuto.bin",
        source_mime="application/pkcs7-mime",
        data=_build_p7m(payload),
    )

    assert prepared.status.is_signed_container is True
    assert prepared.status.signature_format == "smime"
    assert prepared.status.payload_available is True
    assert prepared.status.payload_mime == "application/xml"
    assert prepared.payload_bytes == payload


def test_mime_ooxml_non_apre_zip_prima_dei_budget():
    docx_like = (
        b"PK\x03\x04"
        b"[Content_Types].xml"
        b"word/document.xml"
        b"PK\x05\x06"
    )

    assert (
        firme_cades.payload_mime_from_bytes(docx_like, "contenuto.bin")
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
