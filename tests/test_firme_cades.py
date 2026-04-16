from __future__ import annotations

from pathlib import Path

from asn1crypto import algos, cms

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
