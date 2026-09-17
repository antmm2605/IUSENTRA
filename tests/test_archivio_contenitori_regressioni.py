"""Regressioni dei contenitori reali: MIME, CMS e ZIP non sono testo binario."""
from email.message import EmailMessage
from io import BytesIO
import zipfile

from asn1crypto.cms import ContentInfo

from pct.document_intelligence.extraction import extract_text_from_document
from web.services.archivio_testo_contenitori import estrai_contenuto


def _cms_cifrato():
    return ContentInfo({
        "content_type": "enveloped_data",
        "content": {"version": "v0", "recipient_infos": [],
                    "encrypted_content_info": {
                        "content_type": "data",
                        "content_encryption_algorithm": {"algorithm": "aes256_cbc", "parameters": bytes(16)},
                        "encrypted_content": b"TESTO_CIFRATO_NON_LEGGIBILE" * 20,
                    }},
    }).dump()


def test_email_senza_estensione_non_indicizza_base64_o_busta_cifrata():
    email = EmailMessage()
    email["From"] = "mittente@example.test"
    email["To"] = "destinatario@example.test"
    email["Subject"] = "Deposito telematico"
    email.set_content("Si trasmette il deposito.")
    email.add_attachment(_cms_cifrato(), maintype="application", subtype="octet-stream", filename="Atto.enc")
    result = extract_text_from_document(email.as_bytes(), "oggetto-importato.bin", "bin")
    assert result.ok
    assert result.extraction_engine == "email.message.v2"
    assert "Si trasmette il deposito" in result.text
    assert "non è stato decifrato" in result.text
    assert "TESTO_CIFRATO_NON_LEGGIBILE" not in result.text
    assert "Content-Transfer-Encoding" not in result.text
    assert len(result.text) < 1500


def test_estensione_cms_non_basta_a_dichiarare_struttura_letta():
    result = extract_text_from_document(b"una frase leggibile", "Atto.enc", "enc")
    assert not result.ok
    assert result.text == ""


def test_zip_con_firma_separata_valida_legge_il_testo_senza_certificare_firma():
    signature = ContentInfo({"content_type": "signed_data", "content": {
        "version": "v1", "digest_algorithms": [],
        "encap_content_info": {"content_type": "data"}, "signer_infos": [],
    }}).dump()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("comunicazione.txt", "Comunicazione della cancelleria")
        archive.writestr("smime.p7s", signature)
    result = estrai_contenuto(buffer.getvalue(), "ricevuta.zip")
    assert not result.errori
    assert "Comunicazione della cancelleria" in result.testo
    assert "non verificata" in result.testo


def test_zip_con_percorso_ostile_resta_bloccato():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../fuori.txt", "contenuto")
    result = estrai_contenuto(buffer.getvalue(), "ricevuta.zip")
    assert result.errori


def test_pdf_senza_pagine_non_risulta_letto(monkeypatch):
    monkeypatch.setattr("legal_ocr.motore.testo.testo_da_pdf", lambda *a, **k: [])
    result = estrai_contenuto(b"%PDF-1.4\ntroncato", "identita.pdf")
    assert result.errori
    assert not result.testo
