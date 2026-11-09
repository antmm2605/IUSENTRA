"""Il lettore mostra all'avvocato il contenuto di ogni formato, senza scaricarlo nel riquadro.

Regola dell'avvocato: «il lettore deve leggere tutti i formati in modo tale che
l'avvocato possa visualizzare tutto». Dalle buste di firma (.p7m anche annidati,
.tsd, .m7m) si estrae il documento senza verificare la firma; i formati che il
browser non sa mostrare danno la pagina «Anteprima non disponibile» con Scarica.
Due percorsi: documenti del fascicolo e allegati PEC.
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from pct.buste_firma import contenuto_marca_temporale, e_busta, nome_senza_buste
from pct.document_crypto import ENC_MAGIC, ChiaveDocumentiMancante, decrypt_doc
from pct.email_client import EmailRicevuta, StatoEmail
from pct.fascicoli import GestioneFascicoli, TipoDocumento
from pct.firme_cades import extract_signed_payload, inspect_signed_document_bytes, is_signed_container
from tests.buste_firma_fixtures import PDF_PROVA, busta_m7m, busta_p7m, busta_p7m_annidata, marca_tsd
from tests.mailbox_test_support import sql_mailbox
from tests.test_email_client import _autentica_admin_session, _cfg_web as _cfg_email
from tests.test_fascicolo_detail_ux import _login, fascicolo_ux  # noqa: F401 - fixture

NON_DISPONIBILE = "Anteprima non disponibile per questo formato."


def _p7m_firmato_davvero(payload: bytes) -> bytes:
    """Busta CAdES con un firmatario reale (certificato di prova autogenerato)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.x509.oid import NameOID

    chiave = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Avvocato di prova")])
    adesso = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chiave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(adesso - dt.timedelta(days=1))
        .not_valid_after(adesso + dt.timedelta(days=30))
        .sign(chiave, hashes.SHA256())
    )
    return (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(payload)
        .add_signer(cert, chiave, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )


def _zip(voci: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivio:
        for nome, dati in voci.items():
            archivio.writestr(nome, dati)
    return buffer.getvalue()


def _immagine(formato: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format=formato)
    return buffer.getvalue()


def _docx() -> bytes:
    from docx import Document

    documento = Document()
    documento.add_paragraph("Memoria di prova leggibile")
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def _odt() -> bytes:
    contenuto = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        "<office:body><office:text><text:p>Atto ODT leggibile</text:p></office:text></office:body>"
        "</office:document-content>"
    ).encode()
    return _zip({"mimetype": b"application/vnd.oasis.opendocument.text", "content.xml": contenuto})


FATTURA_PA = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<p:FatturaElettronica versione="FPR12" xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">'
    b"<FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento><Numero>12</Numero>"
    b"</DatiGeneraliDocumento></DatiGenerali></FatturaElettronicaBody></p:FatturaElettronica>"
)
EML = b"Subject: PEC prova\r\nFrom: cancelleria@example.test\r\nTo: studio@example.test\r\n\r\nCorpo PEC"

# nome -> (byte, testo atteso nella risposta oppure None per il PDF)
BUSTE = {
    "sentenza.pdf.p7m.p7m.p7m": busta_p7m_annidata(PDF_PROVA, 3),
    "ordinanza.pdf.p7m.p7m.p7m.p7m.p7m": busta_p7m_annidata(PDF_PROVA, 5),
    "decreto.pdf.p7m.tsd": marca_tsd(busta_p7m(PDF_PROVA)),
    "verbale.pdf.tsd": marca_tsd(PDF_PROVA, "verbale.pdf"),
    "ricorso.pdf.m7m": busta_m7m(busta_p7m(PDF_PROVA)),
}
NON_VISUALIZZABILI = {
    "atti.rar": b"Rar!\x1a\x07\x01\x00" + b"\x00" * 32,
    "atti.7z": b"7z\xbc\xaf\x27\x1c" + b"\x00" * 32,
    "dati.bin": b"\x00\x01\x02\x03 dati sconosciuti",
    "foto.heic": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00",
}
LEGGIBILI = {
    "pec.eml": (EML, "Corpo PEC"),
    "IT01234567890_FPR12.xml": (FATTURA_PA, "FatturaElettronica"),
    "nota.txt": ("Promemoria leggibile".encode(), "Promemoria leggibile"),
    "lettera.rtf": (rb"{\rtf1\ansi Lettera RTF leggibile\par}", "Lettera RTF leggibile"),
    "memoria.docx": (_docx(), "Memoria di prova leggibile"),
    "atto.odt": (_odt(), "Atto ODT leggibile"),
    "scansione.tif": (_immagine("TIFF"), "<img"),
    "scansione.bmp": (_immagine("BMP"), None),
    "scansione.webp": (_immagine("WEBP"), None),
}


# ── Funzioni di dominio ─────────────────────────────────────────────────────


@pytest.mark.parametrize("nome", sorted(BUSTE))
def test_le_buste_si_aprono_fino_al_documento(nome):
    data = BUSTE[nome]
    assert is_signed_container(nome)
    assert e_busta(data)
    assert extract_signed_payload(data) == PDF_PROVA
    esito = inspect_signed_document_bytes(source_name=nome, data=data)
    assert esito.payload_bytes == PDF_PROVA
    assert esito.status.payload_mime == "application/pdf"
    assert esito.status.payload_name == nome.split(".")[0] + ".pdf"


def test_p7m_annidato_tre_volte_con_firme_reali_passa_da_openssl():
    data = _p7m_firmato_davvero(_p7m_firmato_davvero(_p7m_firmato_davvero(PDF_PROVA)))
    esito = inspect_signed_document_bytes(source_name="atto.pdf.p7m.p7m.p7m", data=data)
    assert esito.payload_bytes == PDF_PROVA
    assert esito.status.payload_name == "atto.pdf"


def test_oltre_cinque_livelli_si_ferma_senza_ciclare():
    data = busta_p7m_annidata(PDF_PROVA, 7)
    estratto = extract_signed_payload(data)
    assert estratto and estratto != PDF_PROVA and e_busta(estratto)


def test_una_pec_con_allegato_p7m_non_e_una_busta_m7m():
    pec = (
        b"From: a@example.test\r\nSubject: PEC\r\nMIME-Version: 1.0\r\n"
        b'Content-Type: multipart/mixed; boundary="b"\r\n\r\n--b\r\n'
        b"Content-Type: application/pkcs7-mime\r\nContent-Transfer-Encoding: base64\r\n\r\nMAA=\r\n"
        b"--b\r\nContent-Type: application/timestamp-reply\r\n\r\nx\r\n--b--\r\n"
    )
    assert contenuto_marca_temporale(pec) is None


def test_nome_senza_buste():
    assert nome_senza_buste("a.pdf.p7m.p7m.p7m") == "a.pdf"
    assert nome_senza_buste("a.pdf.P7M.tsd") == "a.pdf"
    assert nome_senza_buste("a.pdf.m7m") == "a.pdf"
    assert nome_senza_buste(".p7m") == ".p7m"


def test_documento_cifrato_senza_chiave_ha_errore_dedicato(monkeypatch):
    monkeypatch.delenv("PCT_DOC_KEY", raising=False)
    with pytest.raises(ChiaveDocumentiMancante, match="chiave dei documenti dello studio non configurata"):
        decrypt_doc(ENC_MAGIC + b"\x00" * 40)


# ── Percorso 1: documenti del fascicolo ─────────────────────────────────────


def _fascicolo_con(cfg, fascicolo, documenti: dict[str, bytes]) -> dict[str, str]:
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    return {
        nome: gf.aggiungi_documento(fascicolo.id, nome, TipoDocumento.ALLEGATO, dati).id
        for nome, dati in documenti.items()
    }


def _apri_fascicolo(client, fascicolo, id_doc):
    return client.get(f"/fascicoli/{fascicolo.id}/documenti/{id_doc}/visualizza?viewer=mobile")


def test_fascicolo_buste_mostrano_il_pdf_contenuto(fascicolo_ux):  # noqa: F811
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    ids = _fascicolo_con(cfg, fascicolo, BUSTE)
    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        for nome, id_doc in ids.items():
            risposta = _apri_fascicolo(client, fascicolo, id_doc)
            assert risposta.status_code == 200, nome
            assert "data-document-pages" in risposta.get_data(as_text=True), nome
            pagina = client.get(
                f"/fascicoli/{fascicolo.id}/documenti/{id_doc}/visualizza?viewer=mobile&page=1"
            )
            assert pagina.mimetype == "image/png", nome


def test_fascicolo_formati_non_visualizzabili_danno_la_pagina_scarica(fascicolo_ux):  # noqa: F811
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    archivio = _zip({"cartella/dati.bin": b"\x00\x01", "programma.exe": b"MZ\x00"})
    ids = _fascicolo_con(cfg, fascicolo, {**NON_VISUALIZZABILI, "archivio.zip": archivio})
    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        for nome, id_doc in ids.items():
            risposta = _apri_fascicolo(client, fascicolo, id_doc)
            html = risposta.get_data(as_text=True)
            assert risposta.status_code == 200, nome
            assert risposta.mimetype == "text/html", nome
            assert "attachment" not in risposta.headers.get("Content-Disposition", ""), nome
            assert "Anteprima non disponibile per questo formato" in html, nome
            assert "Scarica documento" in html and f"/documenti/{id_doc}/scarica" in html, nome
        elenco = _apri_fascicolo(client, fascicolo, ids["archivio.zip"]).get_data(as_text=True)
        assert "File contenuti nell" in elenco
        assert "cartella/dati.bin" in elenco and "programma.exe" in elenco


def test_fascicolo_formati_gia_leggibili_continuano_ad_aprirsi(fascicolo_ux):  # noqa: F811
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    ids = _fascicolo_con(cfg, fascicolo, {nome: dati for nome, (dati, _) in LEGGIBILI.items()})
    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        for nome, id_doc in ids.items():
            risposta = _apri_fascicolo(client, fascicolo, id_doc)
            html = risposta.get_data(as_text=True) if risposta.mimetype.startswith("text/") else ""
            atteso = LEGGIBILI[nome][1]
            assert risposta.status_code == 200, nome
            assert NON_DISPONIBILE not in html, nome
            assert "attachment" not in risposta.headers.get("Content-Disposition", ""), nome
            if atteso:
                assert atteso in html, nome


def test_fascicolo_documento_cifrato_senza_chiave(fascicolo_ux, monkeypatch):  # noqa: F811
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    ids = _fascicolo_con(cfg, fascicolo, {"memoria.pdf": PDF_PROVA})
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    Path(gf.percorso_documento(fascicolo.id, ids["memoria.pdf"])).write_bytes(ENC_MAGIC + b"\x00" * 64)
    monkeypatch.delenv("PCT_DOC_KEY", raising=False)
    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        vista = _apri_fascicolo(client, fascicolo, ids["memoria.pdf"])
        assert vista.status_code == 200
        assert "Documento cifrato: chiave dei documenti dello studio non configurata" in vista.get_data(as_text=True)
        assert "Impossibile visualizzare il documento" not in vista.get_data(as_text=True)
        scarica = client.get(f"/fascicoli/{fascicolo.id}/documenti/{ids['memoria.pdf']}/scarica")
        assert scarica.status_code == 302
        with client.session_transaction() as sessione:
            messaggi = [testo for _categoria, testo in sessione.get("_flashes", [])]
        assert any("Documento cifrato: chiave dei documenti dello studio non configurata" in m for m in messaggi)


# ── Percorso 2: allegati PEC ────────────────────────────────────────────────


def _casella_con(tmp_path: Path, allegati: dict[str, bytes]):
    cfg = _cfg_email(tmp_path)
    casella = sql_mailbox(cfg["EMAIL_CASELLA_DB"])
    cartella = Path(cfg["EMAIL_CASELLA_DB"]).parent / "allegati" / "MAIL-LETTORE"
    cartella.mkdir(parents=True, exist_ok=True)
    voci = []
    for nome, dati in allegati.items():
        (cartella / nome).write_bytes(dati)
        voci.append({
            "nome": nome,
            "mime": "application/octet-stream",
            "size": len(dati),
            "percorso_rel": f"MAIL-LETTORE/{nome}",
            "nome_file": nome,
        })
    casella.aggiungi(EmailRicevuta(
        id="MAIL-LETTORE",
        cartella="INBOX",
        stato=StatoEmail.LETTA,
        mittente="cancelleria@giustiziapec.it",
        oggetto="Comunicazione con allegati di ogni formato",
        data="2026-11-09T10:00:00",
        corpo_testo="Allegati di prova.",
        allegati=voci,
    ))
    return cfg, list(allegati)


def test_pec_buste_mostrano_il_pdf_contenuto(tmp_path):
    from web.app import create_app

    cfg, nomi = _casella_con(tmp_path, BUSTE)
    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        for indice, nome in enumerate(nomi):
            inline = client.get(f"/email/messaggio/MAIL-LETTORE/allegato/{indice}")
            assert inline.status_code == 200, nome
            assert inline.mimetype == "application/pdf", nome
            assert inline.data == PDF_PROVA, nome
            lettore = client.get(f"/email/messaggio/MAIL-LETTORE/allegato/{indice}?viewer=mobile")
            assert lettore.status_code == 200, nome
            assert lettore.mimetype == "text/html", nome
            originale = client.get(f"/email/messaggio/MAIL-LETTORE/allegato/{indice}?download=1")
            assert originale.data == BUSTE[nome], nome


def test_pec_formati_non_visualizzabili_danno_la_pagina_scarica(tmp_path):
    from web.app import create_app

    archivio = _zip({"cartella/dati.bin": b"\x00\x01", "programma.exe": b"MZ\x00"})
    cfg, nomi = _casella_con(tmp_path, {**NON_VISUALIZZABILI, "archivio.zip": archivio})
    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        for indice, nome in enumerate(nomi):
            risposta = client.get(f"/email/messaggio/MAIL-LETTORE/allegato/{indice}?viewer=mobile")
            html = risposta.get_data(as_text=True)
            assert risposta.mimetype == "text/html", nome
            assert "Anteprima non disponibile per questo formato" in html, nome
            assert f"/allegato/{indice}?download=1" in html, nome
        elenco = client.get(
            f"/email/messaggio/MAIL-LETTORE/allegato/{nomi.index('archivio.zip')}?viewer=mobile"
        ).get_data(as_text=True)
        assert "cartella/dati.bin" in elenco and "programma.exe" in elenco


def test_pec_formati_gia_leggibili_continuano_ad_aprirsi(tmp_path):
    from web.app import create_app

    cfg, nomi = _casella_con(tmp_path, {nome: dati for nome, (dati, _) in LEGGIBILI.items()})
    app = create_app(cfg)
    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        for indice, nome in enumerate(nomi):
            risposta = client.get(f"/email/messaggio/MAIL-LETTORE/allegato/{indice}?viewer=mobile")
            html = risposta.get_data(as_text=True) if risposta.mimetype.startswith("text/") else ""
            atteso = LEGGIBILI[nome][1]
            assert risposta.status_code == 200, nome
            assert NON_DISPONIBILE not in html, nome
            if atteso:
                assert atteso in html, nome
