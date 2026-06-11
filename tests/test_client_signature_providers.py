"""Test dell'adapter di firma del Portale Cliente (predisposizione provider)."""

from __future__ import annotations

import io

import pytest

from web.services.client_signature_providers import (
    InternalGraphicSignatureProvider,
    ManualUploadSignatureProvider,
    QualifiedSignatureProviderStub,
    SignatureProviderError,
    SignatureProviderNotConfigured,
    SignatureRequest,
    SignatureType,
    apply_visible_signature_stamp,
    available_signature_providers,
    build_signature_evidence_pack,
    get_signature_provider,
    redact_ip,
    sha256_hex,
)


def _minimal_pdf() -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Documento da firmare")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _request(**kwargs) -> SignatureRequest:
    base = {
        "signature_id": "sig-1",
        "signature_type": SignatureType.GRAPHIC_INTERNAL,
        "tenant_id": "studio-a",
        "client_id": "cliente-1",
        "matter_id": "pratica-1",
        "document_id": "doc-1",
    }
    base.update(kwargs)
    return SignatureRequest(**base)


def test_factory_restituisce_i_tre_provider() -> None:
    assert set(available_signature_providers()) == {"internal_graphic", "manual_upload", "qualified_stub"}
    assert isinstance(get_signature_provider("internal_graphic"), InternalGraphicSignatureProvider)
    assert isinstance(get_signature_provider("manual_upload"), ManualUploadSignatureProvider)
    assert isinstance(get_signature_provider("qualified_stub"), QualifiedSignatureProviderStub)
    with pytest.raises(SignatureProviderNotConfigured):
        get_signature_provider("inesistente")


def test_redazione_ip_e_token_non_in_chiaro() -> None:
    assert redact_ip("203.0.113.5").startswith("ipv:")
    assert "203.0.113.5" not in redact_ip("203.0.113.5")
    assert redact_ip("") == ""


def test_evidence_pack_non_contiene_ip_o_token_in_chiaro_ed_e_verificabile() -> None:
    pack = build_signature_evidence_pack(
        signature_id="sig-1",
        signature_type=SignatureType.GRAPHIC_INTERNAL,
        provider="internal_graphic",
        tenant_id="studio-a",
        client_id="cliente-1",
        matter_id="pratica-1",
        consent_text="Accetto e autorizzo la firma.",
        declaration="Dichiaro di aver letto.",
        original_sha256="a" * 64,
        signed_sha256="b" * 64,
        ip="203.0.113.5",
        user_agent="Mozilla/5.0",
        token="token-super-segreto",
    )
    raw = repr(pack)
    assert "203.0.113.5" not in raw
    assert "token-super-segreto" not in raw
    assert pack["ipHash"].startswith("ipv:")
    assert pack["tokenRef"].startswith("tok:")
    assert pack["originalSha256"] == "a" * 64
    assert pack["signedSha256"] == "b" * 64
    assert len(pack["payloadSha256"]) == 64


def test_firma_grafica_interna_produce_pdf_firmato_senza_mutare_originale() -> None:
    original = _minimal_pdf()
    original_copy = bytes(original)
    provider = get_signature_provider("internal_graphic")
    result = provider.create_signature_request(
        _request(),
        pdf_bytes=original,
        signer_name="Mario Rossi",
        when_label="11/06/2026 15:00",
        reference="PREV-1",
        consent_text="Autorizzo la firma.",
        declaration="Ho letto il documento.",
        ip="203.0.113.5",
        user_agent="UA",
        token="tok",
    )
    assert result.status == "firmato"
    assert result.completed is True
    # Firma elettronica semplice: NON è qualificata.
    assert result.qualified is False
    assert result.signed_pdf is not None
    # Originale immutato; firmato diverso e con hash diverso.
    assert original == original_copy
    assert result.signed_pdf != original
    assert sha256_hex(result.signed_pdf) != sha256_hex(original)
    assert result.evidence["originalSha256"] == sha256_hex(original)
    assert result.evidence["signedSha256"] == sha256_hex(result.signed_pdf)
    # Il PDF firmato resta un PDF valido e leggibile.
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(result.signed_pdf))
    assert len(reader.pages) >= 1


def test_firma_grafica_fallisce_in_modo_sicuro_su_pdf_corrotto() -> None:
    provider = get_signature_provider("internal_graphic")
    with pytest.raises(SignatureProviderError):
        provider.create_signature_request(_request(), pdf_bytes=b"non-e-un-pdf", signer_name="X")
    with pytest.raises(SignatureProviderError):
        apply_visible_signature_stamp(b"", signer_name="X")


def test_upload_manuale_registra_hash_originale_e_firmato() -> None:
    original = _minimal_pdf()
    signed = original + b"%firma-manuale"
    provider = get_signature_provider("manual_upload")
    result = provider.create_signature_request(
        _request(signature_type=SignatureType.MANUAL_UPLOAD),
        original_pdf_bytes=original,
        signed_pdf_bytes=signed,
        consent_text="Confermo che il file caricato è firmato da me.",
        ip="203.0.113.9",
        token="tok",
    )
    assert result.status == "firmato"
    assert result.qualified is False
    assert result.evidence["originalSha256"] == sha256_hex(original)
    assert result.evidence["signedSha256"] == sha256_hex(signed)
    assert result.evidence["originalSha256"] != result.evidence["signedSha256"]
    # Senza file firmato fallisce in modo controllato.
    with pytest.raises(SignatureProviderError):
        provider.create_signature_request(_request(signature_type=SignatureType.MANUAL_UPLOAD))


def test_provider_qualificato_stub_non_dichiara_mai_firma_qualificata() -> None:
    provider = get_signature_provider("qualified_stub")
    # Non è operativo: la creazione richiesta fallisce in modo esplicito.
    with pytest.raises(SignatureProviderNotConfigured):
        provider.create_signature_request(_request(signature_type=SignatureType.QUALIFIED_REMOTE))
    # Lo stato non è mai "firmato"/qualificato e si dichiara non operativo.
    status = provider.get_signature_status("sig-1")
    assert status.status == "non_configurato"
    assert status.completed is False
    assert status.qualified is False
    assert status.operational is False
