"""Portable contracts, not a substitute for native OCR and real browser acceptance."""
from io import BytesIO
import sys
from types import SimpleNamespace

import pytest

from pct.document_intelligence import pdf_inspector_engine as engine
from pct.document_intelligence.extraction import extract_text_from_document


def pdf_bytes(texts):
    from reportlab.pdfgen import canvas
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    for text in texts:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def install_inspector(monkeypatch, process):
    monkeypatch.setitem(sys.modules, 'pdf_inspector', SimpleNamespace(process_pdf_with_ocr_bytes=process))


def response(texts, routed=(), hosted=()):
    return SimpleNamespace(
        pages=[SimpleNamespace(page_number=i, markdown=t) for i, t in enumerate(texts, 1)],
        markdown='\n\n'.join(texts), pages_routed_to_ocr=list(routed), pages_recommending_hosted=list(hosted),
    )


def test_all_pages_offline_in_order_without_eight_page_truncation(monkeypatch):
    texts = [f'Pagina {i}: quantità e totale € 1.234,56' for i in range(1, 13)]
    original = pdf_bytes(texts)
    calls = []
    def process(content, **options):
        calls.append(options)
        assert content == original
        return response(texts)
    install_inspector(monkeypatch, process)
    result = extract_text_from_document(original, 'atto.pdf', 'pdf')
    assert result.ok and len(result.pages) == 12
    assert [p.page_number for p in result.pages] == list(range(1, 13))
    assert result.pages[-1].text == texts[-1]
    assert all(c['offline'] is True for c in calls)
    assert result.extraction_engine == engine.ENGINE_VERSION


@pytest.mark.parametrize('pages', [[2], [1, 3], []])
def test_partial_or_unordered_pages_fail_closed(monkeypatch, pages):
    bad = response(['test'] * len(pages))
    for page, number in zip(bad.pages, pages):
        page.page_number = number
    install_inspector(monkeypatch, lambda *_a, **_k: bad)
    result = engine.extract_pdf_inspected(pdf_bytes(['prima', 'seconda']))
    assert not result.ok and not result.text and not result.pages
    assert 'tutte le pagine' in result.error_message


@pytest.mark.parametrize('raw', ['(cid:1)(cid:2)', 'RRoobbeerrttoo MMoonnttaaggnneessee'])
def test_corrupt_native_layer_is_replaced_not_fused(monkeypatch, raw):
    calls = []
    def process(content, **options):
        calls.append(options)
        return response(['Testo corretto senza duplicazioni' if options.get('mode') == 'force' else raw])
    install_inspector(monkeypatch, process)
    monkeypatch.setattr(engine, '_small_box_values', lambda image, existing: ([], []))
    result = engine.extract_pdf_inspected(pdf_bytes([raw]))
    assert result.ok and result.text == 'Testo corretto senza duplicazioni'
    assert len(calls) == 2 and calls[1]['mode'] == 'force' and calls[1]['offline'] is True
    assert any('originale invariato' in w for w in result.warnings)


def test_scanned_page_box_value_and_hosted_advice_remain_local(monkeypatch):
    calls = []
    def process(content, **options):
        calls.append(options)
        return response(['Fattura numero'], routed=[1], hosted=[1])
    install_inspector(monkeypatch, process)
    monkeypatch.setattr(engine, '_small_box_values', lambda image, existing: (
        ['Valore letto nel riquadro (0.100,0.100,0.050,0.020): 05'], []))
    result = engine.extract_pdf_inspected(pdf_bytes(['']))
    assert result.ok and ': 05' in result.text
    assert len(calls) == 1 and calls[0]['offline'] is True
    assert any('nessun invio a servizi esterni' in w for w in result.warnings)


def test_native_failure_is_not_binary_success_even_inside_p7m(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('modello locale assente')
    install_inspector(monkeypatch, fail)
    original = pdf_bytes(['Titolo del documento'])
    monkeypatch.setattr('pct.document_intelligence.extraction._unwrap_p7m_payload',
                        lambda *_: (original, 'atto.pdf', []))
    result = extract_text_from_document(b'PKCS7 envelope', 'atto.pdf.p7m', 'p7m')
    assert not result.ok and not result.text
    assert result.error_code == 'pdf_inspector_failed'


def test_signed_envelope_with_pdf_extension_reads_payload_not_signature(monkeypatch):
    payload = pdf_bytes(['Provvedimento reale'])
    monkeypatch.setattr('pct.document_intelligence.extraction._unwrap_p7m_payload',
                        lambda *_: (payload, 'atto.pdf', []))
    install_inspector(monkeypatch, lambda *_a, **_k: response(['Provvedimento reale']))
    result = extract_text_from_document(b'\x30\x82firma binaria', 'atto.pdf', 'pdf')
    assert result.ok and result.text == 'Provvedimento reale'
    assert result.extraction_engine == f'cades:{engine.ENGINE_VERSION}'


def test_unreadable_der_envelope_never_indexes_signature_strings(monkeypatch):
    original = b'\x30\x82firma binaria certificato Aruba'
    monkeypatch.setattr('pct.document_intelligence.extraction._unwrap_p7m_payload',
                        lambda *_: (original, 'atto.pdf', []))
    result = extract_text_from_document(original, 'atto.pdf', 'pdf')
    assert not result.ok and not result.text
    assert result.error_code == 'pdf_payload_unavailable'


def test_plain_markdown_and_ordinary_doubled_letters():
    assert engine.plain_markdown('# Titolo\n**quantità** <u>verificata</u>') == 'Titolo\nquantità verificata'
    assert not engine.duplicated_glyphs('avvocato, atto, ricevuta, allegato')


@pytest.mark.parametrize('timeout_at', [None, 2])
def test_short_fields_include_boxes_after_32_and_continue_after_one_timeout(monkeypatch, timeout_at):
    from PIL import Image, ImageDraw
    import pytesseract
    page = Image.new('RGB', (1200, 2000), 'white')
    draw = ImageDraw.Draw(page)
    for index in range(40):
        y = 30 + index * 45
        draw.rectangle((60, y, 200, y + 32), outline='black', width=2)
        draw.rectangle((100, y + 8, 115, y + 24), fill='black')
    calls = []
    def read_box(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == timeout_at:
            raise RuntimeError('Timeout di collaudo')
        return {'text': [f'{len(calls):02}'], 'conf': [96]}
    monkeypatch.setattr(pytesseract, 'image_to_data', read_box)
    values, warnings = engine._small_box_values(page, '')
    assert len(calls) == 40
    assert len(values) == (39 if timeout_at else 40)
    assert values[-1].endswith(': 40')
    assert len(warnings) == (1 if timeout_at else 0)
