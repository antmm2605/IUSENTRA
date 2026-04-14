from __future__ import annotations

import io

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from visible_signature import (
    VISIBLE_SIGNATURE_METADATA_KEY,
    VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    VISIBLE_SIGNATURE_MODE_LATERALE,
    _build_visible_signature_side_text,
    _draw_visible_signature_bottom_right_text,
    _draw_visible_signature_seal,
    apply_visible_signature_stamp,
    format_visible_signature_datetime,
    has_visible_signature_stamp,
    resolve_visible_signature_place,
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


def test_format_visible_signature_datetime_converte_in_fuso_italiano():
    assert (
        format_visible_signature_datetime("2026-04-14T09:32:00+00:00")
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

    assert "Per autentica e sottoscrizione" in text
    assert "Firmato da: AVV. ANTONIO MAMMOLA" in text
    assert "in data 14/04/2026 ore 11:32" in text
    assert "Luogo: Reggio Calabria" in text


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


def test_visible_signature_side_text_espone_tutto_su_unica_riga_verticale():
    side_text = _build_visible_signature_side_text(
        intestatario="Antonio Mammola",
        data_firma="2026-04-14T09:32:00+00:00",
        luogo="Reggio Calabria",
        issuer="ArubaPEC EU Authentication Certificates CA G1",
    )

    assert side_text == (
        "Firmato da: AVV. ANTONIO MAMMOLA | "
        "Data e ora firma: 14/04/2026 alle ore 11:32 | "
        "Luogo firma: REGGIO CALABRIA"
    )


def test_apply_visible_signature_stamp_refreshes_existing_stamp_when_mode_changes():
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

    assert second != first
    reader = PdfReader(io.BytesIO(second))
    metadata = reader.metadata or {}
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Per autentica e sottoscrizione" in text
    assert "Firmato da: AVV. ANTONIO MAMMOLA in data 14/04/2026 ore 11:32" in text
    assert "Luogo: Reggio Calabria" in text
    assert "14/04/2026 alle ore 11:32" in str(metadata.get(VISIBLE_SIGNATURE_METADATA_KEY, ""))


def test_bottom_right_signature_draws_colored_seal(monkeypatch):
    seal_calls = []

    class _FakeOverlay:
        def __init__(self):
            self.drawn = []

        def saveState(self):
            return None

        def restoreState(self):
            return None

        def setFillColor(self, _value):
            return None

        def setFont(self, _name, _size):
            return None

        def drawRightString(self, x, y, text):
            self.drawn.append((x, y, text))

        def stringWidth(self, text, _font_name, _font_size):
            return float(len(text) * 5)

    def _fake_draw_seal(overlay, *, anchor_x, anchor_y, scale=1.0):
        seal_calls.append({
            "overlay": overlay,
            "anchor_x": anchor_x,
            "anchor_y": anchor_y,
            "scale": scale,
        })

    monkeypatch.setattr("visible_signature._draw_visible_signature_seal", _fake_draw_seal)

    overlay = _FakeOverlay()
    _draw_visible_signature_bottom_right_text(
        overlay,
        width=595.0,
        height=842.0,
        color=None,
        intestatario="Antonio Mammola",
        data_firma="2026-04-14T09:32:00+00:00",
        luogo="Reggio Calabria",
    )

    assert len(overlay.drawn) >= 2
    assert overlay.drawn[0][2] == "Per autentica e sottoscrizione"
    assert "Firmato da: AVV. ANTONIO MAMMOLA" in overlay.drawn[1][2]
    assert "in data 14/04/2026 ore 11:32" in overlay.drawn[1][2]
    assert seal_calls
    assert seal_calls[0]["anchor_x"] < 595.0 - 28.35
    assert seal_calls[0]["scale"] >= 1.0


def test_visible_signature_seal_uses_non_grayscale_colors():
    fill_colors = []

    class _FakePath:
        def moveTo(self, *_args):
            return None

        def lineTo(self, *_args):
            return None

        def close(self):
            return None

    class _FakeOverlay:
        def saveState(self):
            return None

        def restoreState(self):
            return None

        def beginPath(self):
            return _FakePath()

        def setStrokeColor(self, _value):
            return None

        def setFillColor(self, value):
            fill_colors.append(value)

        def drawPath(self, *_args, **_kwargs):
            return None

        def circle(self, *_args, **_kwargs):
            return None

        def setLineWidth(self, *_args, **_kwargs):
            return None

    overlay = _FakeOverlay()
    _draw_visible_signature_seal(overlay, anchor_x=32.0, anchor_y=32.0)

    assert fill_colors
    assert any(
        round(getattr(color, "red", 0), 3) != round(getattr(color, "green", 0), 3)
        or round(getattr(color, "green", 0), 3) != round(getattr(color, "blue", 0), 3)
        for color in fill_colors
    )


def test_resolve_visible_signature_place_prefers_city_from_impostazioni_studio():
    assert (
        resolve_visible_signature_place(
            city="TAURIANOVA",
            province="RC",
            address="Via NINO BIXIO 4, 89029 - TAURIANOVA (RC)",
        )
        == "Taurianova"
    )


def test_resolve_visible_signature_place_fallback_to_address_when_city_missing():
    assert (
        resolve_visible_signature_place(
            city="",
            province="",
            address="Via NINO BIXIO 4, 89029 - TAURIANOVA (RC)",
        )
        == "Taurianova"
    )
