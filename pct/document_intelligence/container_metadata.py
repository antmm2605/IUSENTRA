"""Metadati leggibili dei componenti CMS, mai testo del contenuto cifrato."""
from __future__ import annotations


def extract_cms_metadata(content: bytes):
    from asn1crypto.cms import ContentInfo
    from .extraction import ExtractionResult

    try:
        cms = ContentInfo.load(content, strict=True)
        kind = cms["content_type"].native
        if kind == "enveloped_data":
            cms["content"]["encrypted_content_info"]["content_encryption_algorithm"].native
            text = ("Busta CMS cifrata: struttura tecnica letta. Il contenuto è riservato "
                    "al destinatario e non è stato decifrato. Gli atti leggibili restano nelle fonti separate.")
        elif kind == "signed_data" and cms["content"]["encap_content_info"]["content"].native is None:
            text = ("Firma CMS separata: struttura tecnica letta, senza testo autonomo. "
                    "Questa lettura non certifica la validità crittografica della firma.")
        else:
            raise ValueError("Componente CMS diverso da busta cifrata o firma separata")
    except (ValueError, TypeError, KeyError):
        return ExtractionResult(ok=False, text="", pages=[], extraction_engine="cms.metadata.v1",
                                error_code="invalid_cms", error_message="Struttura del componente CMS non riconosciuta.")
    return ExtractionResult(ok=True, text=text, pages=[], extraction_engine="cms.metadata.v1")
