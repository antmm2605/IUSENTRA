"""Guardrail dei difetti osservati con upload ed export reali il 06/10/2026."""
import fitz
import pytest
from io import BytesIO

from legal_ocr.tratti import tratti_del_testo
from web.services.document_ocr_documento import _rifinisci, riconosci_pagina
from web.services.documento_testo_riconosciuto import html_consentito, stile_consentito


def test_native_mixed_size_lines_keep_individual_vertical_positions():
    from legal_ocr.tratti import con_tratti

    blocks = [{"tipo": "paragrafo", "testo": "Titolo Prima riga Seconda riga",
               "riquadro": [40, 100, 400, 230]}]
    words = [dict(text=text, left=left, top=top, width=35, height=height,
                  baseline=top + height, corpo=12 if top == 100 else 11)
             for text, left, top, height in [("Titolo", 40, 100, 55),
                 ("Prima", 40, 171, 50), ("riga", 80, 171, 50),
                 ("Seconda", 40, 225, 50), ("riga", 80, 225, 50)]]
    blocks[0]["riquadro"][3] = 280
    result = con_tratti(blocks, words)[0]
    assert result["a_capo"] == [7, 18]
    assert result["righe_native_top"] == [0, 71, 125]
    optical = [{key: value for key, value in word.items() if key != "baseline"} for word in words]
    assert "righe_native_top" not in con_tratti(blocks, optical)[0]


def test_graphics_background_preserves_table_box_and_picture_without_mutating_pdf():
    from PIL import Image
    from web.services.document_ocr_anteprima import fondo_grafico_da_pdf

    with fitz.open() as pdf:
        page = pdf.new_page(width=600, height=400)
        page.draw_rect(fitz.Rect(40, 40, 250, 140), color=(0, 0, 0), fill=(1, .9, .6))
        picture = BytesIO()
        Image.new('RGB', (20, 20), '#123456').save(picture, format='PNG')
        page.insert_image(fitz.Rect(320, 200, 380, 260), stream=picture.getvalue())
        page.insert_text((60, 90), 'Testo nativo da rileggere')
        before = page.get_text()
        graphics = fondo_grafico_da_pdf(page, 1)
        assert page.get_text() == before
        assert len(page.get_images()) == 1
        with Image.open(BytesIO(graphics.dati)) as image:
            assert image.size == (600, 400)
            assert image.getpixel((70, 70))[0] > 240  # sfondo della casella
            assert image.getpixel((350, 230))[2] > image.getpixel((350, 230))[0] + 40
            # Il testo rimosso non è duplicato sotto quello modificabile.
            assert all(min(image.getpixel((x, y))) > 120 for x in range(60, 185) for y in range(78, 94))


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
