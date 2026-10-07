"""Guardrail dei difetti osservati con upload ed export reali il 06/10/2026."""
import fitz
import pytest

from legal_ocr.tratti import tratti_del_testo
from web.services.document_ocr_documento import _rifinisci, riconosci_pagina
from web.services.documento_testo_riconosciuto import html_consentito, stile_consentito


def test_native_pdf_text_is_not_rewritten_by_ocr_corrections():
    source = "Societa, attivita, punteggiatura: ; ! ? ( ) - fonte nativa controllata."
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((60, 90), source, fontsize=12)
    page.insert_text((60, 115), "Questo documento controlla la conservazione del testo dell'autore.")
    data = pdf.tobytes()
    pdf.close()
    result = riconosci_pagina(data, "native.pdf", 1)
    assert result.origine == "testo"
    assert result.correzioni == []
    assert source in " ".join(result.paragraphs)


def test_ocr_corrections_remain_enabled_for_scanned_text():
    blocks = [{"tipo": "paragrafo", "testo": "Societa, attivita: ( )", "pagina": 1}]
    _, paragraphs, corrections, _ = _rifinisci(blocks)
    assert corrections
    assert "Società" in " ".join(paragraphs)
    assert "attività" in " ".join(paragraphs)


def test_mixed_family_and_size_traits_preserve_text_and_styles():
    words = [{"text": "Avvocato", "word": 0, "famiglia": "Arial", "corpo": 12},
             {"text": "monospaziato", "word": 1, "famiglia": "Courier New", "corpo": 12},
             {"text": "grande", "word": 2, "famiglia": "Times New Roman", "corpo": 16}]
    traits = tratti_del_testo("Avvocato monospaziato grande", words)
    assert "".join(trait["testo"] for trait in traits) == "Avvocato monospaziato grande"
    assert next(t for t in traits if t["testo"] == "monospaziato")["famiglia"] == "Courier New"
    assert next(t for t in traits if t["testo"] == "grande")["corpo"] == 16


def test_inline_styles_keep_native_font_size_without_layout_or_active_content():
    clean = html_consentito('<p><span style="font-family:Courier New;font-size:8pt;color:#123456;position:fixed;margin-left:20pt;background:url(https://example.org/a)" onclick="alert(1)">È € ( )</span></p>')
    assert "font-family:'Courier New'" in clean
    assert "font-size:8pt" in clean
    assert "color:#123456" in clean
    assert "position" not in clean and "margin-left" not in clean
    assert "url(" not in clean and "onclick" not in clean
    assert "È € ( )" in clean


@pytest.mark.parametrize("marker", ["5)", "a)", "IV.", "•"])
def test_inline_fonts_do_not_remove_the_original_list_marker(marker):
    clean = html_consentito(f'<ol><li data-iu-ocr-marker="{marker}"><span style="font-family:Arial;font-size:12pt">Testo</span></li></ol>')
    assert f'data-iu-ocr-marker="{marker}"' in clean
    assert "font-size:12pt" in clean


def test_invalid_font_sizes_and_font_urls_are_rejected():
    assert stile_consentito("font-family:url(x);font-size:999pt", inline=True) == ""
    assert stile_consentito("font-family:Arial;font-size:12pt;color:#123456", solo_colore=True) == "color:#123456"
