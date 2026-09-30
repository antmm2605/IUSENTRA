"""Firma già presente e posizionamento automatico del timbro visibile.

Base: Specifiche tecniche DGSIA (D.M. 44/2011) art. 15 c. 2 — firme multiple parallele o
indipendenti ammesse, ordine non significativo, nessuna posizione prescritta per il timbro;
art. 20 e 24 CAD — la nuova firma non deve alterare il contenuto leggibile né le altre firme.
"""

from __future__ import annotations

import datetime as dt
import io

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from visible_signature import (
    VISIBLE_SIGNATURE_METADATA_KEY,
    VISIBLE_SIGNATURE_MODE_LATERALE,
    FirmaGiaPresente,
    analizza_firme_visibili,
    apply_visible_signature_stamp,
    firme_digitali_presenti,
    ha_timbro_visibile,
    riquadro_firma_pades,
    stesso_firmatario,
    verifica_firma_gia_presente,
)

WIDTH, HEIGHT = A4


def _atto(pagine: int = 2, *, timbri_laterali: bool = False, riga_in_basso: bool = False) -> bytes:
    """PDF simile alla copia ministeriale: timbri verticali «Firmato Da: … Serial#: …» sui due margini."""

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for indice in range(pagine):
        pdf.setFont("Helvetica", 11)
        pdf.drawString(72, 760, f"Visto dell'atto generico - pagina {indice + 1}")
        pdf.drawString(72, 500, "Contenuto dell'atto.")
        if riga_in_basso:
            pdf.drawString(60, 12, "Piè di pagina che occupa l'intera fascia inferiore " * 3)
        if timbri_laterali:
            pdf.setFont("Helvetica", 6)
            pdf.saveState()
            pdf.translate(WIDTH - 10, 40)
            pdf.rotate(90)
            pdf.drawString(0, 0, "Firmato Da: MARIO ROSSI Emesso Da: ARUBAPEC S.P.A. NG CA 3 Serial#: 3d724c28aa")
            pdf.restoreState()
            pdf.saveState()
            pdf.translate(12, 40)
            pdf.rotate(90)
            pdf.drawString(0, 0, "Firmato Da: GIULIA VERDI Emesso Da: INFOCERT FIRMA QUALIFICATA 2 Serial#: 1a2b3c")
            pdf.restoreState()
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _timbra(pdf: bytes, nome: str, seriale: str, mode: str = VISIBLE_SIGNATURE_MODE_LATERALE) -> bytes:
    return apply_visible_signature_stamp(
        pdf, intestatario=nome, serial=seriale, issuer="ArubaPEC EU Qualified Certificates CA G1",
        luogo="Bari", data_firma=dt.datetime(2026, 9, 30, 10, 15), mode=mode,
    )


def _zone(pdf: bytes) -> list[str]:
    metadati = analizza_firme_visibili(pdf)["timbri_metadati"]
    return [t["zona"] for t in metadati]


def test_riconosce_i_timbri_ministeriali_sui_due_margini():
    analisi = analizza_firme_visibili(_atto(timbri_laterali=True))
    zone = {(t["firmatario"], t["zona"]) for t in analisi["timbri"]}
    assert ("MARIO ROSSI", "destra") in zone and ("GIULIA VERDI", "sinistra") in zone
    rossi = next(t for t in analisi["timbri"] if t["firmatario"] == "MARIO ROSSI")
    assert rossi["seriale"].lower() == "3d724c28aa"


def test_stesso_firmatario_gia_visibile_documento_invariato():
    atto = _atto(timbri_laterali=True)
    assert _timbra(atto, "Avv. Mario Rossi", "3D724C28AA") == atto
    assert ha_timbro_visibile(atto, intestatario="Mario Rossi", serial="3d724c28aa")


def test_nuovo_firmatario_con_margini_occupati_va_in_basso_nell_ultima_pagina():
    atto = _atto(timbri_laterali=True)
    firmato = _timbra(atto, "Avv. Anna Bianchi", "ABCDEF01")
    assert firmato != atto
    assert _zone(firmato) == ["basso"]
    analisi = analizza_firme_visibili(firmato)
    # Il nuovo timbro è solo nell'ultima pagina e non si sovrappone a nulla di preesistente.
    prima = analizza_firme_visibili(atto)
    assert len(analisi["pagine"][0]["frammenti"]) == len(prima["pagine"][0]["frammenti"])
    metadati = analisi["metadati"]
    assert "Anna Bianchi" in metadati and "Bari" in metadati and "30/09/2026" in metadati


def test_catena_di_firmatari_occupa_destra_sinistra_basso_alto():
    documento = _atto(timbri_laterali=False)
    firmatari = [("Avv. Anna Bianchi", "A1"), ("Avv. Luca Neri", "B2"), ("Avv. Sara Blu", "C3"), ("Avv. Paolo Gialli", "D4")]
    for nome, seriale in firmatari:
        documento = _timbra(documento, nome, seriale)
    # Il primo timbro è quello laterale destro consueto; i successivi cercano le zone libere.
    assert _zone(documento) == ["laterale", "sinistra", "basso", "alto"]
    # Ripetere la firma di un titolare già presente non aggiunge nulla.
    assert _timbra(documento, "Avv. Luca Neri", "B2") == documento


def test_fascia_bassa_occupata_passa_in_alto():
    atto = _atto(timbri_laterali=True, riga_in_basso=True)
    assert _zone(_timbra(atto, "Avv. Anna Bianchi", "ABCDEF01")) == ["alto"]


def test_stesso_firmatario_confronta_seriale_poi_nome():
    assert stesso_firmatario({"firmatario": "ROSSI MARIO", "seriale": "00:3D:72"}, intestatario="x", serial="3d72")
    assert not stesso_firmatario({"firmatario": "MARIO ROSSI", "seriale": "3D72"}, intestatario="Mario Rossi", serial="FFFF")
    assert stesso_firmatario({"firmatario": "MARIO ROSSI", "seriale": ""}, intestatario="Avv. Rossi Mario")
    assert not stesso_firmatario({"firmatario": "MARIO ROSSI", "seriale": ""}, intestatario="Mario Bianchi")


def _certificato(nome: str):
    chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    soggetto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome)])
    oggi = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(soggetto).issuer_name(soggetto).public_key(chiave.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(oggi - dt.timedelta(days=1))
        .not_valid_after(oggi + dt.timedelta(days=30)).sign(chiave, hashes.SHA256())
    )
    return cert, chiave


def _cades(contenuto: bytes, cert, chiave) -> bytes:
    return (
        pkcs7.PKCS7SignatureBuilder().set_data(contenuto).add_signer(cert, chiave, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )


def test_busta_cades_dello_stesso_certificato_non_si_firma_di_nuovo():
    cert, chiave = _certificato("MARIO ROSSI")
    busta = _cades(_atto(), cert, chiave)
    firme = firme_digitali_presenti(busta)
    assert firme and firme[0]["firmatario"] == "MARIO ROSSI"
    with pytest.raises(FirmaGiaPresente) as errore:
        verifica_firma_gia_presente(busta, intestatario="MARIO ROSSI", serial=format(cert.serial_number, "X"))
    assert "già firmato da MARIO ROSSI con lo stesso dispositivo" in str(errore.value)
    assert errore.value.firmatario == "MARIO ROSSI"


def test_busta_cades_di_altro_certificato_si_puo_cofirmare():
    cert, chiave = _certificato("MARIO ROSSI")
    altro, _ = _certificato("ANNA BIANCHI")
    busta = _cades(_atto(), cert, chiave)
    verifica_firma_gia_presente(busta, intestatario="ANNA BIANCHI", serial=format(altro.serial_number, "X"))
    # Stesso titolare con un certificato rinnovato (seriale diverso): cofirma ammessa.
    rinnovato, _ = _certificato("MARIO ROSSI")
    verifica_firma_gia_presente(busta, intestatario="MARIO ROSSI", serial=format(rinnovato.serial_number, "X"))


def test_riquadro_pades_evita_testo_e_timbri():
    atto = _atto(timbri_laterali=True, riga_in_basso=True)
    x0, y0, x1, y1 = riquadro_firma_pades(atto)
    assert y0 > HEIGHT / 2 and x1 - x0 >= 200
    pulito = _atto()
    x0, y0, x1, y1 = riquadro_firma_pades(pulito)
    assert y0 < 20 and x1 - x0 >= 200


def test_documento_senza_timbri_usa_il_percorso_consueto():
    firmato = _timbra(_atto(), "Avv. Anna Bianchi", "A1")
    from pypdf import PdfReader

    metadati = str(PdfReader(io.BytesIO(firmato)).metadata.get(VISIBLE_SIGNATURE_METADATA_KEY))
    assert "Anna Bianchi" in metadati and "Modalita firma visibile: laterale" in metadati


def test_interfaccia_comunica_la_firma_gia_presente():
    from pathlib import Path

    radice = Path(__file__).resolve().parents[1] / "frontend/src/components"
    deposito = (radice / "FascicoloDepositoPage.tsx").read_text(encoding="utf-8")
    assert "if (result?.gia_firmato === true)" in deposito
    assert "la firma dell’avvocato con lo stesso dispositivo: firma non ripetuta." in deposito
    fascicolo = (radice / "FascicoliPage.tsx").read_text(encoding="utf-8")
    assert "if (signedPayload.gia_firmato === true)" in fascicolo
