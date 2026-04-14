from __future__ import annotations

import io

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from visible_signature import (
    VISIBLE_SIGNATURE_METADATA_KEY,
    VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    VISIBLE_SIGNATURE_MODE_LATERALE,
    apply_visible_signature_stamp,
    format_visible_signature_datetime,
    has_visible_signature_stamp,
)


def _make_pdf_bytes() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Times-Roman", 12)
    pdf.drawString(72, 780, "R.G.N. 191/2023")
    pdf.drawString(72, 540, "Contenuto di prova per la firma visibile.")
    pdf.save()
    return buffer.getvalue()


def test_format_visible_signature_datetime_italian_style():
    assert (
        format_visible_signature_datetime("2026-04-14T11:32:00+02:00")
        == "14/04/2026 alle ore 11:32"
    )


def test_apply_visible_signature_stamp_adds_vertical_mark_and_metadata():
    stamped = apply_visible_signature_stamp(
        _make_pdf_bytes(),
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        issuer="ArubaPEC per firma qualificata",
        serial="123ABC",
        mode=VISIBLE_SIGNATURE_MODE_LATERALE,
    )

    assert stamped.startswith(b"%PDF")
    assert has_visible_signature_stamp(stamped) is True
    assert VISIBLE_SIGNATURE_METADATA_KEY.encode("ascii") in stamped
    reader = PdfReader(io.BytesIO(stamped))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    metadata = reader.metadata or {}

    assert "Firmato da: AVV. ANTONIO MAMMOLA" in text
    assert "Data e ora firma: 14/04/2026 alle ore 11:32" in text
    assert "Luogo firma: REGGIO CALABRIA" in text
    assert "ArubaPEC per firma qualificata" in str(metadata.get(VISIBLE_SIGNATURE_METADATA_KEY, ""))
    assert "123ABC" in str(metadata.get(VISIBLE_SIGNATURE_METADATA_KEY, ""))


def test_apply_visible_signature_stamp_supporta_modalita_basso_destra():
    stamped = apply_visible_signature_stamp(
        _make_pdf_bytes(),
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    )

    reader = PdfReader(io.BytesIO(stamped))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Firmato digitalmente da AVV. ANTONIO MAMMOLA" in text
    assert "Reggio Calabria - 14/04/2026 alle ore 11:32" in text


def test_apply_visible_signature_stamp_modalita_laterale_aggiunge_prefisso_avv():
    stamped = apply_visible_signature_stamp(
        _make_pdf_bytes(),
        intestatario="Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_LATERALE,
    )

    reader = PdfReader(io.BytesIO(stamped))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Firmato da: AVV. ANTONIO MAMMOLA" in text


def test_apply_visible_signature_stamp_is_idempotent():
    first = apply_visible_signature_stamp(
        _make_pdf_bytes(),
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_LATERALE,
    )
    second = apply_visible_signature_stamp(
        first,
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    )

    assert second == first
