from __future__ import annotations

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
