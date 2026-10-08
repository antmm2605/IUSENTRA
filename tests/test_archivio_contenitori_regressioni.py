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


def test_txt_fine_riga_registra_esito_negativo_senza_inventare_testo():
    result = estrai_contenuto(b"\r\n\r\n\r\n", "ATT00001.txt")
    assert result.esito == "senza_testo"
    assert result.testo == ""
    assert not result.errori
    assert "nessun contenuto documentale" in result.motivo


def test_zip_con_txt_vuoto_conserva_componenti_e_legge_gli_altri():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("ATT00001.txt", b"\r\n\r\n\r\n")
        archive.writestr("atto.txt", "Atto con contenuto da leggere")
    result = estrai_contenuto(buffer.getvalue(), "fonte.zip")
    assert not result.errori
    assert result.esito == "testo"
    assert "Atto con contenuto" in result.testo
    blank = next(c for c in result.componenti if c['name'] == 'ATT00001.txt')
    assert blank['esito'] == 'senza_testo'
    assert blank['testo'] == ''
    assert blank['sha256']
    assert blank['parent_sha256']
    assert blank['motivo']


def test_zip_con_soli_txt_vuoti_non_produce_fatti():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("vuoto.txt", b"\r\n")
    result = estrai_contenuto(buffer.getvalue(), "vuoti.zip")
    assert result.esito == "senza_testo"
    assert not result.testo
    assert not result.errori
    assert len(result.componenti) == 1


def test_txt_non_vuoto_non_viene_escluso_se_estrattore_fallisce(monkeypatch):
    from pct.document_intelligence.extraction import ExtractionResult

    monkeypatch.setattr('pct.document_intelligence.extraction.extract_text_from_document',
                        lambda *a: ExtractionResult(ok=False, text='', pages=[], extraction_engine='txt',
                                                    error_message='Lettura fallita'))
    result = estrai_contenuto(b'Atto da leggere', 'atto.txt')
    assert result.errori == ['Lettura fallita']
    assert result.esito != 'senza_testo'


def test_email_con_allegato_legge_componenti_separati_con_impronte():
    import hashlib

    email = EmailMessage()
    email['From'] = 'mittente@example.test'
    email['Subject'] = 'Documento allegato'
    email.set_content('Corpo del messaggio')
    payload = b'Contenuto del documento, distinto dal corpo.'
    email.add_attachment(payload, maintype='text', subtype='plain', filename='atto.txt')
    raw = email.as_bytes()
    result = estrai_contenuto(raw, 'messaggio.eml')
    assert not result.errori
    assert len(result.componenti) == 2
    body, attachment = result.componenti
    assert 'Corpo del messaggio' in body['testo']
    assert 'Contenuto del documento' not in body['testo']
    assert attachment['testo'] == payload.decode()
    assert attachment['sha256'] == hashlib.sha256(payload).hexdigest()
    assert attachment['parent_sha256'] == hashlib.sha256(raw).hexdigest()


def test_email_con_allegato_corrotto_non_dichiara_lettura_completa():
    email = EmailMessage()
    email['From'] = 'mittente@example.test'
    email['Subject'] = 'Documento corrotto'
    email.set_content('Corpo leggibile')
    email.add_attachment(b'file non decodificabile', maintype='application', subtype='octet-stream', filename='atto.p7m')
    result = estrai_contenuto(email.as_bytes(), 'messaggio.eml')
    assert result.errori
    assert result.componenti[1]['errori']
    assert result.componenti[1]['testo'] == ''


def test_email_con_percorso_ostile_non_interpreta_allegato():
    email = EmailMessage()
    email['From'] = 'mittente@example.test'
    email['Subject'] = 'Allegato non sicuro'
    email.set_content('Corpo leggibile')
    email.add_attachment(b'Testo non acquisibile', maintype='text', subtype='plain', filename='../atto.txt')
    result = estrai_contenuto(email.as_bytes(), 'messaggio.eml')
    assert result.errori == ['Percorso dell’allegato email non sicuro.']
    assert len(result.componenti) == 1
    assert 'Testo non acquisibile' not in result.testo


def test_zip_con_email_conserva_impronta_del_genitore_diretto():
    import hashlib

    email = EmailMessage()
    email['From'] = 'mittente@example.test'
    email['Subject'] = 'Documento nel contenitore'
    email.set_content('Corpo')
    payload = b'Atto originale'
    email.add_attachment(payload, maintype='text', subtype='plain', filename='atto.txt')
    raw_email = email.as_bytes()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('postacert.eml', raw_email)
    raw_zip = buffer.getvalue()
    result = estrai_contenuto(raw_zip, 'consegna.zip')
    assert not result.errori
    leaf = next(c for c in result.componenti if c['name'] == 'atto.txt')
    assert leaf['parent_sha256'] == hashlib.sha256(raw_email).hexdigest()
    assert leaf['root_container_sha256'] == hashlib.sha256(raw_zip).hexdigest()
    assert leaf['sha256'] == hashlib.sha256(payload).hexdigest()
