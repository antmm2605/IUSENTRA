from __future__ import annotations

import io
import sys
from types import SimpleNamespace

from pct import editor


class _FakePdf:
    pages = []

    def __init__(self, page):
        self.pages = [page]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakePdfPage:
    chars = []

    def extract_tables(self):
        return []

    def extract_text(self):
        return "(cid:84)(cid:114)(cid:105)(cid:98)(cid:117)(cid:110)(cid:97)(cid:108)(cid:101)"

    def extract_text_lines(self):
        return []


def _install_fake_pdfplumber(monkeypatch):
    page = _FakePdfPage()
    monkeypatch.setitem(
        sys.modules,
        "pdfplumber",
        SimpleNamespace(open=lambda _stream: _FakePdf(page)),
    )


def test_pdf_to_html_non_mostra_token_cid_quando_ocr_recupera_testo(monkeypatch):
    _install_fake_pdfplumber(monkeypatch)
    monkeypatch.setattr(editor, "_estrai_testo_pymupdf", lambda _data, _page_index: "")
    monkeypatch.setattr(
        editor,
        "_ocr_pagina",
        lambda _data, _page_index, _pagina=None: "Tribunale Ordinario Civile di Palmi",
    )

    html, avvisi, is_scanned, n_pagine = editor.pdf_to_html(b"%PDF fake")

    assert n_pagine == 1
    assert is_scanned is True
    assert "(cid:" not in html
    assert "Tribunale Ordinario Civile di Palmi" in html
    assert any("OCR" in avviso for avviso in avvisi)


def test_documento_to_html_blocca_pdf_cid_senza_fallback_affidabile(monkeypatch):
    _install_fake_pdfplumber(monkeypatch)
    monkeypatch.setattr(editor, "_estrai_testo_pymupdf", lambda _data, _page_index: "")
    monkeypatch.setattr(editor, "_ocr_pagina", lambda _data, _page_index, _pagina=None: "")

    html, avvisi, meta = editor.documento_to_html(b"%PDF fake", "Ordinanza_32473463.pdf")

    assert "(cid:" not in html
    assert 'data-editor-disabled="true"' in html
    assert meta["editor_disabled"] is True
    assert meta["testo_affidabile"] is False
    assert any("testo PDF non leggibile" in avviso for avviso in avvisi)


def _pdf_reportlab(*, layout_complesso: bool) -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(595, 842))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(297, 680, "REPUBBLICA ITALIANA")
    c.drawCentredString(297, 660, "IN NOME DEL POPOLO ITALIANO")
    c.setFont("Helvetica", 11)
    c.drawString(85, 590, "Composta dagli Ill.mi Sigg.ri Magistrati:")
    if layout_complesso:
        c.drawRightString(545, 805, "Numero registro generale 14732/2025")
        c.rect(420, 420, 110, 54)
        c.saveState()
        c.translate(575, 80)
        c.rotate(90)
        c.drawString(0, 0, "Firmato digitalmente da magistrato")
        c.restoreState()
    c.showPage()
    c.save()
    return buffer.getvalue()


def test_documento_to_html_blocca_pdf_con_layout_grafico_non_fedele():
    html, avvisi, meta = editor.documento_to_html(
        _pdf_reportlab(layout_complesso=True),
        "sentenza_cassazione.pdf",
    )

    assert meta["tipo_originale"] == "pdf"
    assert meta["editor_disabled"] is True
    assert meta["layout_preservato"] is False
    assert meta["anteprima_originale_obbligatoria"] is True
    assert meta["editor_disabled_reason"] == "layout PDF complesso"
    assert 'data-editor-disabled="true"' in html
    assert "REPUBBLICA ITALIANA" not in html
    assert any("anteprima originale" in avviso for avviso in avvisi)


def test_documento_to_html_lascia_editabile_pdf_testuale_lineare():
    html, avvisi, meta = editor.documento_to_html(
        _pdf_reportlab(layout_complesso=False),
        "bozza_lineare.pdf",
    )

    assert meta["tipo_originale"] == "pdf"
    assert meta["editor_disabled"] is False
    assert meta["layout_preservato"] is True
    assert meta["anteprima_originale_obbligatoria"] is False
    assert "REPUBBLICA ITALIANA" in html
    assert not avvisi
