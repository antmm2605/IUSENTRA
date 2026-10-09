"""Dimensioni reali del PDF consegnato al secondo lettore locale."""

import sys
from types import SimpleNamespace

import pypdfium2
import pytest
from PIL import Image, ImageDraw

from legal_ocr.motore import consenso


def _capture_render(monkeypatch):
    observed = []

    def process_pdf(content, **options):
        # Il motore OCR è isolato, ma PDF, pagina e rendering sono reali:
        # un semplice controllo degli argomenti non rileva il dimezzamento.
        with pypdfium2.PdfDocument(content) as document:
            page = document[0]
            bitmap = page.render(scale=options['dpi'] / 72)
            try:
                observed.append((bitmap.width, bitmap.height, options))
            finally:
                bitmap.close()
                page.close()
        provenance = SimpleNamespace(ocr_confidence=.93, ocr_model='pp-ocr')
        return SimpleNamespace(pages=[SimpleNamespace(markdown='DATO LETTO', provenance=provenance)])

    monkeypatch.setitem(sys.modules, 'pdf_inspector', SimpleNamespace(process_pdf_with_ocr_bytes=process_pdf))
    monkeypatch.setattr(consenso, 'secondo_lettore_disponibile', lambda: True)
    monkeypatch.setattr(consenso, 'cartella_modelli', lambda: '/modelli-locali')
    return observed


@pytest.mark.parametrize('options,expected', [
    ({}, (360, 144)),
    ({'dpi': 216}, (360, 144)),
    ({'dpi': 216, 'preserva_risoluzione': False}, (360, 144)),
    ({'dpi': 216, 'preserva_risoluzione': True}, (720, 288)),
    ({'dpi': 150, 'preserva_risoluzione': True}, (720, 288)),
    ({'dpi': 36, 'preserva_risoluzione': True}, (720, 288)),
])
def test_pdf_render_preserves_opted_in_crop_and_legacy_default(monkeypatch, options, expected):
    observed = _capture_render(monkeypatch)
    with Image.new('RGB', (720, 288), 'white') as image:
        ImageDraw.Draw(image).text((60, 80), 'CAMPO 123', fill='black')
        original = image.tobytes()
        reading = consenso.leggi_con_secondo_lettore(image, **options)
        assert image.tobytes() == original
    assert len(observed) == 1
    # PDFium arrotonda verso l'alto coordinate PDF frazionarie: al massimo
    # un pixel di bordo aggiunto, mai perdita della risoluzione richiesta.
    width, height, _ = observed[0]
    assert expected[0] <= width <= expected[0] + 1
    assert expected[1] <= height <= expected[1] + 1
    assert reading and reading.testo == 'DATO LETTO' and reading.confidenza == .93
    assert reading.motore == 'pdf-inspector:pp-ocr'
    assert observed[0][2]['offline'] is True
    assert observed[0][2]['model_directory'] == '/modelli-locali'
    assert observed[0][2]['mode'] == 'force'


def test_measured_zoom_reaches_reader_without_being_cancelled(monkeypatch):
    observed = _capture_render(monkeypatch)
    with Image.new('RGB', (360, 144), 'white') as source:
        enlarged = source.resize((720, 288), Image.Resampling.LANCZOS)
        try:
            consenso.leggi_con_secondo_lettore(source, dpi=216, preserva_risoluzione=True)
            consenso.leggi_con_secondo_lettore(enlarged, dpi=216, preserva_risoluzione=True)
        finally:
            enlarged.close()
    assert [(width, height) for width, height, _ in observed] == [(360, 144), (720, 288)]
