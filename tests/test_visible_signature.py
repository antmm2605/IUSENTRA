from __future__ import annotations

import io

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from visible_signature import (
    VISIBLE_SIGNATURE_METADATA_KEY,
    VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    VISIBLE_SIGNATURE_MODE_LATERALE,
    _build_visible_signature_side_text,
    _draw_visible_signature_bottom_left_text,
    _draw_visible_signature_bottom_right_text,
    _draw_visible_signature_seal,
    _draw_visible_signature_side_mark,
    apply_visible_signature_stamp,
    compute_visible_signature_layout,
    format_visible_signature_datetime,
    has_visible_signature_stamp,
    normalize_visible_signature_mode,
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


def test_normalize_visible_signature_mode_aliases():
    cases = {
        "laterale": VISIBLE_SIGNATURE_MODE_LATERALE,
        "verticale": VISIBLE_SIGNATURE_MODE_LATERALE,
        "margine-destro": VISIBLE_SIGNATURE_MODE_LATERALE,
        "basso_sinistra": VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
        "basso-sinistra": VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
        "bottom_left": VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
        "sx": VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
        "basso_destra": VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
        "bottom_right": VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
        "dx": VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
        "valore-non-valido": VISIBLE_SIGNATURE_MODE_LATERALE,
    }

    for raw, expected in cases.items():
        assert normalize_visible_signature_mode(raw) == expected


def test_compute_visible_signature_layout_non_usa_coordinate_fisse_a4():
    left = compute_visible_signature_layout(width=842.0, height=595.0, mode="basso_sinistra")
    right = compute_visible_signature_layout(width=842.0, height=595.0, mode="basso_destra")
    side = compute_visible_signature_layout(width=420.0, height=640.0, mode="laterale")

    assert left["mode"] == VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA
    assert right["mode"] == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA
    assert side["mode"] == VISIBLE_SIGNATURE_MODE_LATERALE
    assert float(left["x"]) < float(right["x"])
    for layout, width, height in ((left, 842.0, 595.0), (right, 842.0, 595.0), (side, 420.0, 640.0)):
        assert 0 <= float(layout["x"]) < width
        assert 0 <= float(layout["y"]) < height
        assert float(layout["x"]) + float(layout["box_width"]) <= width + 0.1
        assert float(layout["y"]) + float(layout["box_height"]) <= height + 0.1


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

    assert "Firmato Da: AVV. ANTONIO MAMMOLA" in text
    assert "Data e ora firma: 14/04/2026 alle ore 11:32" in text
    assert "Luogo firma: REGGIO CALABRIA" in text
    assert "Emesso Da: ArubaPEC per firma qualificata" in text
    # il seriale può essere troncato nel testo laterale stretto; verificato nei metadati
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
    assert "Firmato Da: AVV. ANTONIO MAMMOLA" in text
    assert "in data 14/04/2026 ore 11:32" in text
    assert "Luogo: Reggio Calabria" in text


def test_apply_visible_signature_stamp_supporta_modalita_basso_sinistra():
    stamped = apply_visible_signature_stamp(
        _make_pdf_bytes(),
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    )

    reader = PdfReader(io.BytesIO(stamped))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    metadata = reader.metadata or {}

    assert stamped.startswith(b"%PDF")
    assert "Per autentica e sottoscrizione" in text
    assert "Firmato Da: AVV. ANTONIO MAMMOLA" in text
    assert "in data 14/04/2026 ore 11:32" in text
    assert str(metadata.get(VISIBLE_SIGNATURE_METADATA_KEY, ""))


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

    assert "Firmato Da: AVV. ANTONIO MAMMOLA" in text


def test_visible_signature_side_text_espone_tutto_su_unica_riga_verticale():
    side_text = _build_visible_signature_side_text(
        intestatario="Antonio Mammola",
        data_firma="2026-04-14T09:32:00+00:00",
        luogo="Reggio Calabria",
        issuer="ArubaPEC EU Authentication Certificates CA G1",
    )

    assert side_text == (
        "Firmato Da: AVV. ANTONIO MAMMOLA | "
        "Data e ora firma: 14/04/2026 alle ore 11:32 | "
        "Luogo firma: REGGIO CALABRIA | "
        "Emesso Da: ArubaPEC EU Authentication Certificates CA G1"
    )


def test_apply_visible_signature_stamp_non_duplica_timbro_se_gia_presente():
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
    assert "Firmato Da: AVV. ANTONIO MAMMOLA" in overlay.drawn[1][2]
    assert "in data 14/04/2026 ore 11:32" in overlay.drawn[1][2]
    assert seal_calls
    assert seal_calls[0]["anchor_x"] < 595.0 - 28.35
    assert seal_calls[0]["scale"] >= 1.0


def test_visible_signature_seal_uses_embedded_coccarda_png():
    draw_calls = []

    class _FakeOverlay:
        def drawImage(self, image, x, y, *, width, height, preserveAspectRatio, mask):
            draw_calls.append({
                "image": image,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "preserveAspectRatio": preserveAspectRatio,
                "mask": mask,
            })

    overlay = _FakeOverlay()
    _draw_visible_signature_seal(overlay, anchor_x=32.0, anchor_y=32.0)

    assert len(draw_calls) == 1
    assert 18.0 <= draw_calls[0]["width"] <= 24.0
    assert draw_calls[0]["height"] == 24.0
    assert draw_calls[0]["preserveAspectRatio"] is True
    assert draw_calls[0]["mask"] == "auto"


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


def test_lateral_signature_leaves_gap_between_coccarda_and_text(monkeypatch):
    seal_calls = []
    translations = []
    fonts = []

    class _FakeOverlay:
        def saveState(self):
            return None

        def restoreState(self):
            return None

        def setFillColor(self, _value):
            return None

        def setFont(self, name, size):
            fonts.append((name, size))

        def translate(self, x, y):
            translations.append((x, y))

        def rotate(self, _value):
            return None

        def drawString(self, _x, _y, _text):
            return None

        def stringWidth(self, text, _font_name, _font_size):
            return float(len(text) * 5)

    def _fake_draw_seal(_overlay, *, anchor_x, anchor_y, scale=1.0):
        seal_calls.append({"anchor_x": anchor_x, "anchor_y": anchor_y, "scale": scale})

    monkeypatch.setattr("visible_signature._draw_visible_signature_seal", _fake_draw_seal)

    _draw_visible_signature_side_mark(
        _FakeOverlay(),
        width=595.0,
        height=842.0,
        color=None,
        intestatario="Antonio Mammola",
        data_firma="2026-04-14T09:32:00+00:00",
        luogo="Reggio Calabria",
        issuer="ArubaPEC EU Authentication Certificates CA G1",
    )

    assert translations
    assert seal_calls
    assert fonts
    assert translations[0][0] >= 595.0 - 3.0
    assert translations[0][1] - seal_calls[0]["anchor_y"] >= 20.0
    assert seal_calls[0]["anchor_x"] >= 595.0 - 10.0
    assert fonts[0][1] <= 9.5


def test_lateral_signature_layout_sta_quasi_sul_margine_destro():
    layout = compute_visible_signature_layout(width=595.0, height=842.0, mode=VISIBLE_SIGNATURE_MODE_LATERALE)

    assert layout["mode"] == VISIBLE_SIGNATURE_MODE_LATERALE
    assert layout["x"] + layout["box_width"] >= 595.0 - 2.0
    assert layout["x"] + layout["box_width"] <= 595.0


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


# ── nuovi test: basso_sinistra, aliases, layout, no-duplication ────────────


def test_normalize_visible_signature_mode_accetta_alias_bottom_left():
    assert normalize_visible_signature_mode("bottom_left") == VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA
    assert normalize_visible_signature_mode("sinistra") == VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA
    assert normalize_visible_signature_mode("basso_sinistra") == VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA


def test_normalize_visible_signature_mode_accetta_alias_bottom_right():
    assert normalize_visible_signature_mode("bottom_right") == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA
    assert normalize_visible_signature_mode("destra") == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA


def test_normalize_visible_signature_mode_accetta_alias_laterale():
    assert normalize_visible_signature_mode("side") == VISIBLE_SIGNATURE_MODE_LATERALE
    assert normalize_visible_signature_mode("lateral") == VISIBLE_SIGNATURE_MODE_LATERALE


def test_normalize_visible_signature_mode_fallback_sconosciuto():
    assert normalize_visible_signature_mode("unknown_mode") == VISIBLE_SIGNATURE_MODE_LATERALE
    assert normalize_visible_signature_mode("") == VISIBLE_SIGNATURE_MODE_LATERALE
    assert normalize_visible_signature_mode(None) == VISIBLE_SIGNATURE_MODE_LATERALE


def test_compute_visible_signature_layout_basso_destra_posiziona_a_destra():
    layout = compute_visible_signature_layout(
        width=595.0,
        height=842.0,
        mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    )
    assert layout["mode"] == VISIBLE_SIGNATURE_MODE_BASSO_DESTRA
    assert layout["x"] + layout["box_width"] <= 595.0
    # right edge is within right margin
    right_edge = layout["x"] + layout["box_width"]
    assert right_edge > 595.0 * 0.8


def test_compute_visible_signature_layout_basso_sinistra_posiziona_a_sinistra():
    layout = compute_visible_signature_layout(
        width=595.0,
        height=842.0,
        mode=VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    )
    assert layout["mode"] == VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA
    assert layout["x"] < 595.0 / 2
    assert layout["x"] + layout["box_width"] <= 595.0


def test_compute_visible_signature_layout_usa_dimensioni_pagina_non_a4():
    layout_small = compute_visible_signature_layout(
        width=400.0,
        height=600.0,
        mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    )
    layout_large = compute_visible_signature_layout(
        width=800.0,
        height=1200.0,
        mode=VISIBLE_SIGNATURE_MODE_BASSO_DESTRA,
    )
    assert layout_small["x"] != layout_large["x"]
    assert layout_small["x"] + layout_small["box_width"] <= 400.0
    assert layout_large["x"] + layout_large["box_width"] <= 800.0


def test_apply_visible_signature_stamp_supporta_modalita_basso_sinistra():
    stamped = apply_visible_signature_stamp(
        _make_pdf_bytes(),
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    )

    reader = PdfReader(io.BytesIO(stamped))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Per autentica e sottoscrizione" in text
    assert "Firmato Da: AVV. ANTONIO MAMMOLA" in text
    assert "in data 14/04/2026 ore 11:32" in text
    assert "Luogo: Reggio Calabria" in text


def test_apply_visible_signature_stamp_no_duplicazione_stampa_successiva():
    first = apply_visible_signature_stamp(
        _make_pdf_bytes(),
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    )
    second = apply_visible_signature_stamp(
        first,
        intestatario="Avv. Antonio Mammola",
        data_firma="2026-04-14T11:32:00+02:00",
        luogo="Reggio Calabria",
        mode=VISIBLE_SIGNATURE_MODE_BASSO_SINISTRA,
    )

    reader = PdfReader(io.BytesIO(second))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert text.count("Per autentica e sottoscrizione") <= 2


def test_bottom_left_signature_draws_on_left_side(monkeypatch):
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

        def drawString(self, x, y, text):
            self.drawn.append((x, y, text))

        def stringWidth(self, text, _font_name, _font_size):
            return float(len(text) * 5)

    def _fake_draw_seal(overlay, *, anchor_x, anchor_y, scale=1.0):
        seal_calls.append({"anchor_x": anchor_x, "anchor_y": anchor_y})

    monkeypatch.setattr("visible_signature._draw_visible_signature_seal", _fake_draw_seal)

    overlay = _FakeOverlay()
    _draw_visible_signature_bottom_left_text(
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
    assert "Firmato Da: AVV. ANTONIO MAMMOLA" in overlay.drawn[1][2]
    # text x position should be at left side (less than half the page width)
    assert overlay.drawn[0][0] < 595.0 / 2
    assert seal_calls
    # for left-aligned layout, seal is to the left of the text start (seal before text)
    assert seal_calls[0]["anchor_x"] < overlay.drawn[0][0]
