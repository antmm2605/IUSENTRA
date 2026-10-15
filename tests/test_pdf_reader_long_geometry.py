"""Long readers reserve each original page before its pixels arrive."""
import io
import re

from flask import Flask
from pypdf import PdfWriter
import pytest

from web.bootstrap.fascicoli_document_helpers import pdf_mobile_preview_html


@pytest.mark.parametrize('page_count', [45, 173])
def test_long_reader_reserves_mixed_page_geometry_without_rendering(monkeypatch, page_count):
    from web.services import pdf_reader_text, native_activity_assets

    writer = PdfWriter()
    sizes = ([(600, 900), (900, 600), (500, 500)] * page_count)[:page_count]
    for width, height in sizes:
        writer.add_blank_page(width=width, height=height)
    stream = io.BytesIO()
    writer.write(stream)
    monkeypatch.setattr(pdf_reader_text, 'text_layers', lambda *a, **kw: [])
    monkeypatch.setattr(native_activity_assets, 'native_activity_assets', lambda *a: '')
    with Flask(__name__).test_request_context():
        html, status, _ = pdf_mobile_preview_html(
            nome_documento=f'Controllo {page_count} pagine.pdf',
            page_urls=[f'/pagina/{n}' for n in range(1, page_count + 1)],
            scarica_url='/originale', pdf_payload=stream.getvalue(),
        )
    assert status == 200
    images = re.findall(r'<img\b[^>]*>', html)
    assert len(images) == page_count
    for image, (width, height) in zip(images, sizes, strict=True):
        assert f'width="{width}"' in image
        assert f'height="{height}"' in image
    assert f'/pagina/{page_count}' in images[-1]
