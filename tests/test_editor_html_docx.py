"""Conversione del documento dell'editor in `.docx`: la forma deve sopravvivere.

Quando l'avvocato salva o scarica un documento dall'editor, il `.docx` deve
essere il documento che ha davanti: titoli che restano titoli, grassetto e
corsivo dove li ha messi, elenchi che restano elenchi, tabelle che restano
tabelle, formule centrate e sottoscrizioni a destra.

Difetto trovato il 14/09/2026 e qui bloccato per sempre: l'HTML veniva avvolto
in un `<div>` e il convertitore trattava quel contenitore come un capoverso,
quindi **ogni** documento salvato dall'editor usciva come un unico paragrafo
senza titoli, senza grassetto, senza elenchi e senza tabelle.
"""

from __future__ import annotations

import io

import pytest
from docx import Document

from pct.editor import html_to_docx


def test_cssom_bordi_sfondo_e_allineamento_verticale():
    from docx.oxml.ns import qn
    documento = Document(io.BytesIO(html_to_docx(
        '<table><tr><td style="border-top: 1.5pt dashed rgb(18, 52, 86);'
        'border-left: none; background-color: rgb(240, 230, 210);'
        'vertical-align: middle; padding-left: 8pt">Testo</td></tr></table>'
    )))
    proprieta = documento.tables[0].cell(0, 0)._tc.tcPr
    assert proprieta.find(qn('w:tcBorders')).find(qn('w:top')).get(qn('w:color')) == '123456'
    assert proprieta.find(qn('w:tcBorders')).find(qn('w:left')).get(qn('w:val')) == 'nil'
    assert proprieta.find(qn('w:shd')).get(qn('w:fill')) == 'F0E6D2'
    assert proprieta.find(qn('w:vAlign')).get(qn('w:val')) == 'center'
    assert proprieta.find(qn('w:tcMar')).find(qn('w:left')).get(qn('w:w')) == '160'


@pytest.mark.parametrize('stile,valore', [
    ('border-width:medium;border-style:none;border-color:currentcolor', 'nil'),
    ('border-width:1px;border-style:solid;border-color:rgb(18,52,86)', 'single'),
])
def test_bordi_cssom_compattati(stile, valore):
    from docx.oxml.ns import qn
    documento = Document(io.BytesIO(html_to_docx(f'<table><tr><td style="{stile}">Testo</td></tr></table>')))
    bordi = documento.tables[0].cell(0, 0)._tc.tcPr.find(qn('w:tcBorders'))
    assert all(bordi.find(qn('w:' + lato)).get(qn('w:val')) == valore for lato in ('top', 'right', 'bottom', 'left'))


def test_riapertura_cella_formattata_non_perde_bordi_e_allineamento(tmp_path):
    from pct.documento_fedele.da_docx import converti_docx
    percorso = tmp_path / 'tabella.docx'
    percorso.write_bytes(html_to_docx('<table><tr><td style="border-top:1pt dashed #123456;border-right:none;vertical-align:middle;background-color:#F0E6D2">Prima</td><td>Seconda</td></tr></table>'))
    risultato = converti_docx(percorso)
    assert 'vertical-align:middle' in risultato.html
    assert 'border-top:1pt dashed #123456' in risultato.html
    assert 'border-right:none' in risultato.html
    assert 'background-color:#f0e6d2' in risultato.html.lower()


def test_colonne_percentuali_conservate_nel_docx():
    documento = Document(io.BytesIO(html_to_docx(
        '<table><tr><td style="width:75%">Descrizione</td>'
        '<td style="width:25%">Importo</td></tr></table>'
    )))
    tabella = documento.tables[0]
    assert tabella.autofit is False
    assert tabella.columns[0].width / tabella.columns[1].width == pytest.approx(3, rel=0.001)
    assert tabella.cell(0, 0).width == tabella.columns[0].width

ATTO = (
    "<h1>ATTO DI CITAZIONE</h1>"
    "<p>Il sottoscritto avvocato espone quanto segue.</p>"
    "<p><strong>Grassetto</strong>, <em>corsivo</em> e <strong><em>entrambi</em></strong>.</p>"
    '<p style="text-align:center"><strong>P.Q.M.</strong></p>'
    "<ul><li>Prima voce</li><li>Seconda voce</li></ul>"
    "<ol><li>Voce numerata</li></ol>"
    "<table><tr><th>Voce</th><th>Importo</th></tr><tr><td>Diritti</td><td>100,00</td></tr></table>"
    '<p style="text-align:right">Avv. Mario Rossi</p>'
)


@pytest.fixture(scope="module")
def documento():
    return Document(io.BytesIO(html_to_docx(ATTO, "Atto di citazione")))


def _paragrafi(documento):
    return [par for par in documento.paragraphs if par.text.strip()]


def test_il_documento_non_si_appiattisce_in_un_unico_paragrafo(documento):
    """Il difetto originale: tutto il documento in un paragrafo solo."""
    assert len(_paragrafi(documento)) >= 7


def test_i_titoli_restano_titoli(documento):
    primo = _paragrafi(documento)[0]
    assert primo.style.name == "Heading 1"
    assert primo.text == "ATTO DI CITAZIONE"


def test_grassetto_e_corsivo_sopravvivono_anche_annidati(documento):
    riga = next(par for par in _paragrafi(documento) if "Grassetto" in par.text)
    testi = {run.text.strip(): (bool(run.bold), bool(run.italic)) for run in riga.runs if run.text.strip()}
    assert testi.get("Grassetto") == (True, False)
    assert testi.get("corsivo") == (False, True)
    assert testi.get("entrambi") == (True, True), "il corsivo dentro il grassetto e' andato perso"


def test_l_allineamento_del_capoverso_arriva_nel_documento(documento):
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    centrato = next(par for par in _paragrafi(documento) if par.text.strip() == "P.Q.M.")
    destra = next(par for par in _paragrafi(documento) if "Rossi" in par.text)
    assert centrato.alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert destra.alignment == WD_ALIGN_PARAGRAPH.RIGHT


def test_gli_elenchi_restano_elenchi(documento):
    stili = [par.style.name for par in _paragrafi(documento)]
    assert "List Bullet" in stili
    assert "List Number" in stili
    puntati = [par.text for par in _paragrafi(documento) if par.style.name == "List Bullet"]
    assert puntati == ["Prima voce", "Seconda voce"]


def test_le_tabelle_restano_tabelle(documento):
    assert len(documento.tables) == 1
    tabella = documento.tables[0]
    assert [cella.text for cella in tabella.rows[0].cells] == ["Voce", "Importo"]
    assert [cella.text for cella in tabella.rows[1].cells] == ["Diritti", "100,00"]


@pytest.mark.parametrize("corpo", [3, 37, 72])
def test_dimensioni_editor_arrivano_nel_file_word(corpo):
    documento = Document(io.BytesIO(html_to_docx(f'<p style="font-size:{corpo}pt">Testo controllato</p>')))
    assert documento.paragraphs[0].runs[0].font.size.pt == corpo


@pytest.mark.parametrize("interlinea", [0.8, 1.35, 2.5, 4])
def test_interlinea_personalizzata_persistita_come_formato_del_paragrafo(interlinea):
    documento = Document(io.BytesIO(html_to_docx(f'<p style="line-height:{interlinea}">Prima riga<br>Seconda riga</p>')))
    assert documento.paragraphs[0].paragraph_format.line_spacing == pytest.approx(interlinea, abs=0.005)


def test_immagine_in_casella_conservata_e_adattata_nel_docx():
    import base64
    from PIL import Image

    immagine = io.BytesIO()
    Image.new("RGB", (800, 400), "white").save(immagine, format="PNG")
    source = "data:image/png;base64," + base64.b64encode(immagine.getvalue()).decode()
    html = f'<table data-iu-text-box="true" style="width:320px"><tr><td><p>Casella<img src="{source}" style="width:100%;height:auto"></p></td></tr></table>'
    documento = Document(io.BytesIO(html_to_docx(html)))
    assert len(documento.tables) == 1
    assert len(documento.inline_shapes) == 1
    assert documento.inline_shapes[0].width.pt <= 240
    assert documento.inline_shapes[0].height.pt == pytest.approx(documento.inline_shapes[0].width.pt / 2, abs=0.1)
    assert documento.tables[0].cell(0, 0).text == "Casella"


def test_immagine_remota_non_scaricata_dal_convertitore():
    with pytest.raises(ValueError, match="non incorporata"):
        html_to_docx('<p><img src="https://example.invalid/documento.png"></p>')


def test_pagina_importata_conserva_orientamento_margini_e_stile_ereditato():
    html = '<section class="iu-doc-pagina" data-larghezza="841.9" data-altezza="595.3" data-margine-alto="42" data-margine-basso="36" data-margine-sinistro="50" data-margine-destro="48" style="font-family:Arial;font-size:14pt;line-height:1.35"><p>Testo della pagina</p></section>'
    documento = Document(io.BytesIO(html_to_docx(html)))
    pagina = documento.sections[0]
    assert pagina.page_width.pt == pytest.approx(841.9, abs=0.05)
    assert pagina.page_height.pt == pytest.approx(595.3, abs=0.05)
    assert pagina.top_margin.pt == 42
    assert pagina.bottom_margin.pt == 36
    assert pagina.left_margin.pt == 50
    assert pagina.right_margin.pt == 48
    assert documento.paragraphs[0].runs[0].font.name == "Arial"
    assert documento.paragraphs[0].runs[0].font.size.pt == 14
    assert documento.paragraphs[0].paragraph_format.line_spacing == pytest.approx(1.35)


def test_elenco_non_regolare_non_elimina_testo_del_documento():
    documento = Document(io.BytesIO(html_to_docx('<ul><strong>Intestazione</strong><em>Indirizzo</em><li>Voce</li><em>Coda</em></ul>')))
    assert [p.text for p in documento.paragraphs] == ['Intestazione', 'Indirizzo', 'Voce', 'Coda']


def test_punto_elenco_unicode_non_dipende_dai_codici_privati_symbol():
    from docx.oxml.ns import qn

    documento = Document(io.BytesIO(html_to_docx('<ul><li>Voce controllata</li></ul>')))
    livelli = documento.part.numbering_part.element.findall('.//' + qn('w:lvl'))
    puntati = [livello for livello in livelli if livello.find(qn('w:numFmt')).get(qn('w:val')) == 'bullet']
    assert puntati
    for livello in puntati:
        assert livello.find(qn('w:lvlText')).get(qn('w:val')) in {'•', '○', '▪'}
        assert livello.find('.//' + qn('w:rFonts')).get(qn('w:ascii')) == 'Arial'


def test_collegamento_conserva_indirizzo_testo_e_formattazione():
    documento = Document(io.BytesIO(html_to_docx('<p>Prima <a href="https://example.org/prova"><strong>Fonte</strong></a> dopo</p>')))
    from pct.documento_fedele.da_docx import _pezzi_del_paragrafo
    pezzi = list(_pezzi_del_paragrafo(documento.paragraphs[0]))
    assert [(run.text, href) for run, href in pezzi] == [('Prima ', None), ('Fonte', 'https://example.org/prova'), (' dopo', None)]
    assert pezzi[1][0].bold is True


def test_collegamento_attivo_non_consentito_non_viene_esportato():
    with pytest.raises(ValueError, match="collegamento"):
        html_to_docx('<p><a href="javascript:alert(1)">Fonte</a></p>')


def test_il_testo_non_si_incolla_fra_un_blocco_e_il_successivo(documento):
    """Sintomo del difetto: «ATTO DI CITAZIONEIl sottoscritto…» in un blocco solo."""
    for paragrafo in _paragrafi(documento):
        assert "CITAZIONEIl" not in paragrafo.text


def test_un_documento_senza_contenitore_si_converte_ugualmente():
    documento = Document(io.BytesIO(html_to_docx("<h2>Memoria</h2><p>Testo.</p>", "Memoria")))
    stili = [(par.style.name, par.text) for par in documento.paragraphs if par.text.strip()]
    assert stili == [("Heading 2", "Memoria"), ("Normal", "Testo.")]


def test_un_html_non_valido_non_fa_perdere_il_testo():
    documento = Document(io.BytesIO(html_to_docx("<p>Testo senza chiusura", "Prova")))
    assert any("Testo senza chiusura" in par.text for par in documento.paragraphs)


def test_l_interruzione_di_pagina_dell_editor_diventa_interruzione_nel_documento():
    """Le pagine dell'originale restano pagine: stesso marcatore di editor e PDF."""
    html = '<p>Prima pagina</p><hr class="iu-ted-page-break" data-iu-page-break="true"><p>Seconda pagina</p>'
    documento = Document(io.BytesIO(html_to_docx(html, "Prova")))
    assert _interruzioni_di_pagina(documento) == 1


def test_una_linea_orizzontale_qualunque_non_spezza_la_pagina():
    documento = Document(io.BytesIO(html_to_docx("<p>Testo</p><hr><p>Altro testo</p>", "Prova")))
    assert _interruzioni_di_pagina(documento) == 0
    assert [par.text for par in _paragrafi(documento)] == ["Testo", "Altro testo"]


def test_casella_editor_conserva_identita_e_larghezza_dopo_riaperture(tmp_path):
    from lxml import html as html_parser
    from pct.documento_fedele.da_docx import converti_docx

    contenuto = '<table data-iu-text-box="true" style="width:360px"><tr><td><p>Riquadro controllato</p></td></tr></table>'
    for ciclo in range(3):
        percorso = tmp_path / f'riquadro-{ciclo}.docx'
        percorso.write_bytes(html_to_docx(contenuto))
        contenuto = converti_docx(percorso).html
        caselle = html_parser.fromstring(contenuto).xpath('.//table[@data-iu-text-box="true"]')
        assert len(caselle) == 1
        assert 'width:270pt' in caselle[0].get('style')
        assert caselle[0].text_content() == 'Riquadro controllato'


def test_tabella_ordinaria_non_diventa_casella_editor(tmp_path):
    from pct.documento_fedele.da_docx import converti_docx

    percorso = tmp_path / 'tabella.docx'
    percorso.write_bytes(html_to_docx('<table><tr><td>Voce</td></tr></table>'))
    assert 'data-iu-text-box' not in converti_docx(percorso).html


def test_immagine_nella_cella_conserva_ordine_testo_e_dimensione(tmp_path):
    from lxml import html as html_parser
    from PIL import Image
    from docx.shared import Pt
    from pct.documento_fedele.da_docx import converti_docx

    figura = io.BytesIO()
    Image.new('RGB', (240, 120), 'blue').save(figura, format='PNG')
    figura.seek(0)
    documento = Document()
    cella = documento.add_table(rows=1, cols=1).cell(0, 0)
    run = cella.paragraphs[0].add_run('Prima ')
    run.bold = True
    run.add_picture(figura, width=Pt(120))
    run.add_text(' dopo')
    percorso = tmp_path / 'cella-immagine.docx'
    documento.save(percorso)
    for _ in range(3):
        contenuto = converti_docx(percorso).html
        cella_html = html_parser.fromstring(contenuto).xpath('.//td | .//th')[0]
        assert len(cella_html.xpath('.//img')) == 1
        assert 'width:120pt' in cella_html.xpath('.//img')[0].get('style')
        assert cella_html.text_content() == 'Prima  dopo'
        assert contenuto.index('Prima') < contenuto.index('<img') < contenuto.index('dopo')
        percorso.write_bytes(html_to_docx(contenuto))
        figura_salvata = Document(percorso).inline_shapes[0]
        assert all(figura_salvata._inline.get(distanza) == '0'
                   for distanza in ('distT', 'distB', 'distL', 'distR'))


def test_immagine_casella_conserva_ingrandimento_esplicito():
    import base64
    from PIL import Image

    figura = io.BytesIO()
    Image.new('RGB', (240, 120), 'blue').save(figura, format='PNG')
    sorgente = base64.b64encode(figura.getvalue()).decode('ascii')
    documento = Document(io.BytesIO(html_to_docx(
        '<table data-iu-text-box="true" style="width:360px"><tr><td>'
        f'<img src="data:image/png;base64,{sorgente}" style="width:343.6px">'
        '</td></tr></table>'
    )))
    assert documento.inline_shapes[0].width.pt == pytest.approx(257.7)
    assert documento.inline_shapes[0].height.pt == pytest.approx(128.85)


def test_immagine_nel_corpo_non_diventa_paragrafo_separato(tmp_path):
    from PIL import Image
    from lxml import html as html_parser
    from docx.shared import Pt
    from pct.documento_fedele.da_docx import converti_docx

    figura = io.BytesIO()
    Image.new('RGB', (20, 10), 'blue').save(figura, format='PNG')
    figura.seek(0)
    documento = Document()
    paragrafo = documento.add_paragraph('Prima ')
    paragrafo.add_run().add_picture(figura, width=Pt(15))
    paragrafo.add_run(' dopo')
    percorso = tmp_path / 'corpo-immagine.docx'
    documento.save(percorso)
    for _ in range(3):
        contenuto = converti_docx(percorso).html
        radice = html_parser.fromstring(contenuto)
        assert len(radice.xpath('./p')) == 1
        assert len(radice.xpath('./p/img')) == 1
        assert radice.text_content() == 'Prima  dopo'
        assert contenuto.index('Prima') < contenuto.index('<img') < contenuto.index('dopo')
        percorso.write_bytes(html_to_docx(contenuto))


@pytest.mark.parametrize('indirizzo', ['/fascicoli/7FFD0C5D#documenti', 'https://example.com/prova', '#sezione'])
def test_collegamento_alla_radice_conservato_in_tre_cicli(tmp_path, indirizzo):
    from lxml import html as html_parser
    from pct.documento_fedele.da_docx import converti_docx

    contenuto = f'<a href="{indirizzo}"><strong>Riferimento tecnico</strong></a>'
    percorso = tmp_path / 'collegamento.docx'
    for _ in range(3):
        percorso.write_bytes(html_to_docx(contenuto))
        contenuto = converti_docx(percorso).html
        collegamento = html_parser.fromstring(contenuto).xpath('.//a')[0]
        assert collegamento.get('href') == indirizzo
        assert collegamento.text_content() == 'Riferimento tecnico'
        assert collegamento.xpath('.//strong')


def test_collegamento_alla_radice_rifiuta_script():
    with pytest.raises(ValueError, match='non consentito'):
        html_to_docx('<a href="javascript:alert(1)">Riferimento</a>')


def test_alias_font_browser_non_sostituisce_nome_nativo_docx():
    documento = Document(io.BytesIO(html_to_docx(
        '<p style="font-family:\'iu-8c48c434f1730e18ac82f59f\', Arial">Testo</p>'
    )))
    assert documento.paragraphs[0].runs[0].font.name == 'Arial'


def test_cambio_pagina_docx_non_crea_sezioni_in_tre_cicli(tmp_path):
    from docx.enum.text import WD_BREAK
    from pct.documento_fedele.da_docx import converti_docx

    percorso = tmp_path / 'pagine-stessa-sezione.docx'
    documento = Document()
    documento.add_paragraph('Prima pagina controllata')
    documento.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    documento.add_paragraph('Seconda pagina controllata')
    documento.save(percorso)
    for _ in range(3):
        contenuto = converti_docx(percorso)
        assert len(contenuto.pagine) == 2
        assert contenuto.html.count('data-sezione-word="1"') == 2
        percorso.write_bytes(html_to_docx(contenuto.html))
        riaperto = Document(percorso)
        assert len(riaperto.sections) == 1
        assert _interruzioni_di_pagina(riaperto) == 1
        assert 'Prima pagina controllata' in [p.text for p in riaperto.paragraphs]
        assert 'Seconda pagina controllata' in [p.text for p in riaperto.paragraphs]


def test_sezioni_senza_provenienza_word_restano_distinte():
    documento = Document(io.BytesIO(html_to_docx(
        '<section class="iu-doc-pagina"><p>Prima</p></section>'
        '<section class="iu-doc-pagina"><p>Seconda</p></section>'
    )))
    assert len(documento.sections) == 2


def _interruzioni_di_pagina(documento) -> int:
    marca = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    return sum(
        1
        for paragrafo in documento.paragraphs
        for run in paragrafo.runs
        for interruzione in run._element.findall(f".//{marca}br")
        if interruzione.get(f"{marca}type") == "page"
    )


def test_regioni_word_native_non_diventano_testo_del_corpo():
    import io
    from docx import Document
    from docx.oxml.ns import qn
    from pct.editor import html_to_docx
    pagina = '<section class="iu-doc-pagina" data-sezione-word="1" data-iu-word-first-page="true" data-iu-word-even-pages="true" data-iu-word-header-distance="34" data-iu-word-footer-distance="28">'
    h = pagina + (
        '<div data-iu-word-region="header"><p><b>Intestazione</b></p></div>'
        '<div data-iu-word-region="header" data-iu-word-kind="first"><p>Prima pagina</p></div>'
        '<div data-iu-word-region="header" data-iu-word-kind="even"><p>Pagina pari</p></div>'
        '<p>Solo corpo</p>'
        '<div data-iu-word-region="footer"><p>Pagina <span data-iu-word-field="PAGE">1</span>'
        ' di <span data-iu-word-field="NUMPAGES">2</span></p></div></section>'
    )
    d = Document(io.BytesIO(html_to_docx(h)))
    assert [p.text for p in d.paragraphs] == ['Solo corpo']
    s = d.sections[0]
    assert s.header.paragraphs[0].text == 'Intestazione'
    assert s.header.paragraphs[0].runs[0].bold
    assert s.first_page_header.paragraphs[0].text == 'Prima pagina'
    assert s.even_page_header.paragraphs[0].text == 'Pagina pari'
    assert s.different_first_page_header_footer
    assert d.settings.odd_and_even_pages_header_footer
    assert abs(s.header_distance.pt - 34) < .1
    assert abs(s.footer_distance.pt - 28) < .1
    fields = s.footer._element.findall('.//' + qn('w:fldSimple'))
    assert [f.get(qn('w:instr')) for f in fields] == ['PAGE', 'NUMPAGES']
    assert all(f.get(qn('w:dirty')) == 'true' for f in fields)


def test_regioni_word_tabelle_collegamenti_e_collegamento_precedente():
    import io
    from docx import Document
    from pct.editor import html_to_docx
    h = (
        '<section class="iu-doc-pagina" data-sezione-word="1">'
        '<div data-iu-word-region="header"><table><tr><td><p>Logo</p></td>'
        '<td><p><a href="https://example.org/">Studio</a></p></td></tr></table></div>'
        '<p>Prima sezione</p></section>'
        '<section class="iu-doc-pagina" data-sezione-word="2">'
        '<div data-iu-word-region="header" data-iu-word-linked="true">'
        '<p>Logo già presente nella sezione precedente</p></div>'
        '<p>Seconda sezione</p></section>'
    )
    d = Document(io.BytesIO(html_to_docx(h)))
    assert [p.text for p in d.paragraphs if p.text] == ['Prima sezione', 'Seconda sezione']
    assert len(d.tables) == 0
    assert len(d.sections[0].header.tables) == 1
    assert d.sections[1].header.is_linked_to_previous
    assert len(d.sections[1].header.tables) == 1
    assert any(r.target_ref == 'https://example.org/' for r in d.sections[0].header.part.rels.values())


def test_regione_word_o_campo_non_consentiti_rifiutati():
    import pytest
    from pct.editor import html_to_docx
    with pytest.raises(ValueError, match='Regione'):
        html_to_docx('<div data-iu-word-region="external"><p>Testo</p></div>')
    with pytest.raises(ValueError, match='Campo Word'):
        html_to_docx('<p><span data-iu-word-field="INCLUDETEXT">Testo</span></p>')


def test_sezione_di_pagina_annidata_nella_regione_word_rifiutata():
    import pytest
    from pct.editor import html_to_docx
    with pytest.raises(ValueError, match='sezione di pagina'):
        html_to_docx('<div data-iu-word-region="header"><section class="iu-doc-pagina"><p>Testo</p></section></div>')


def test_tabella_con_celle_unite_preserva_geometria_e_contenuti():
    import io
    from docx import Document
    from pct.editor import html_to_docx
    h = ('<table><tr><td rowspan="2">Verticale</td><td colspan="2">Orizzontale</td></tr>'
         '<tr><td>Sinistra</td><td>Destra</td></tr></table>')
    d = Document(io.BytesIO(html_to_docx(h)))
    t = d.tables[0]
    assert len(t.columns) == 3
    assert len(t.rows) == 2
    assert t.cell(0, 0)._tc is t.cell(1, 0)._tc
    assert t.cell(0, 1)._tc is t.cell(0, 2)._tc
    assert t.cell(0, 0).text == 'Verticale'
    assert t.cell(0, 1).text == 'Orizzontale'
    assert t.cell(1, 1).text == 'Sinistra'
    assert t.cell(1, 2).text == 'Destra'
    from pct.documento_fedele.da_docx import converti_docx
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'celle-unite.docx'
        source.write_bytes(html_to_docx(h))
        imported = converti_docx(source).html
        assert 'rowspan="2"' in imported
        assert 'colspan="2"' in imported
        assert imported.count('Verticale') == 1
        restored = Document(io.BytesIO(html_to_docx(imported))).tables[0]
        assert len(restored.columns) == 3
        assert restored.cell(0, 0)._tc is restored.cell(1, 0)._tc
        assert restored.cell(0, 1)._tc is restored.cell(0, 2)._tc
