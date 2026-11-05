"""Anteprima di un allegato PDF malformato: niente errore 500 (05/11/2026)."""

import web.services.pdf_reader_text as testo_pdf
from web.bootstrap.fascicoli_document_helpers import pdf_mobile_preview_html


def test_pdf_malformato_mostra_le_pagine_senza_testo(monkeypatch):
    def ricorsione(*_a, **_k):
        raise RecursionError("annotazioni cicliche")

    monkeypatch.setattr(testo_pdf, "text_layers", ricorsione)
    import web.services.native_activity_assets as asset_nativi

    monkeypatch.setattr(asset_nativi, "native_activity_assets", lambda _nome: "")
    from flask import Flask

    with Flask(__name__).test_request_context("/"):
        html, stato, _ = pdf_mobile_preview_html(nome_documento="allegato.pdf", page_urls=["/p/1"], scarica_url="/s",
                                                 pdf_payload=b"%PDF-1.4 rotto", page_dimensions=[])
    assert stato == 200 and "/p/1" in html


def test_link_di_pagina_illeggibili_non_tolgono_il_testo(monkeypatch):
    def malformato(*_a, **_k):
        raise RecursionError("annotazioni cicliche")

    monkeypatch.setattr(testo_pdf, "page_links", malformato)
    from reportlab.pdfgen import canvas
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Testo di prova")
    c.save()
    livelli = testo_pdf.text_layers(buf.getvalue())
    assert livelli and "Testo" in str(livelli[0])
