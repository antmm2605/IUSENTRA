"""Il DOCX che rientra dall'editor deve ritrovare quello che aveva.

L'avvocato esporta l'atto in Word, lo modifica, lo ricarica. Se al rientro
perde gli allineamenti, il carattere o il colore, l'esportazione in Word non
e' un giro utile: e' un modo per rovinare l'atto.
"""

from __future__ import annotations

import re

import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt, RGBColor

from pct.documento_fedele.da_docx import DocxError, converti_docx


def _scrivi(costruisci, tmp_path, nome: str = "atto.docx"):
    documento = Document()
    costruisci(documento)
    percorso = tmp_path / nome
    documento.save(str(percorso))
    return converti_docx(percorso)


def _testo(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def test_gli_allineamenti_arrivano_tutti(tmp_path):
    def costruisci(d):
        titolo = d.add_paragraph("TRIBUNALE ORDINARIO DI NAPOLI")
        titolo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        corpo = d.add_paragraph("Con il presente atto si espone quanto segue.")
        corpo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        firma = d.add_paragraph("Avv. Antonio Affinito")
        firma.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    html = _scrivi(costruisci, tmp_path).html
    assert "text-align:center" in html, "il titolo centrato e' finito a sinistra"
    assert "text-align:justify" in html, "il giustificato e' andato perso"
    assert "text-align:right" in html, "la firma a destra e' finita a sinistra"


def test_paragrafi_della_cella_conservano_spazi_e_interlinea(tmp_path):
    import io
    from pct.editor import html_to_docx

    def costruisci(d):
        cella = d.add_table(rows=1, cols=1).cell(0, 0)
        primo = cella.paragraphs[0]
        primo.text = "Prima riga"
        primo.paragraph_format.space_before = Pt(0)
        primo.paragraph_format.space_after = Pt(0)
        primo.paragraph_format.line_spacing = 1.0
        secondo = cella.add_paragraph("Seconda riga")
        secondo.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        secondo.paragraph_format.space_before = Pt(3)
        secondo.paragraph_format.space_after = Pt(6)
        secondo.paragraph_format.line_spacing = 1.5

    html = _scrivi(costruisci, tmp_path).html
    assert 'margin-bottom:0pt;line-height:1.00' in html
    assert 'margin-top:3pt;margin-bottom:6pt;line-height:1.50' in html
    esportato = Document(io.BytesIO(html_to_docx(html)))
    paragrafi = esportato.tables[0].cell(0, 0).paragraphs
    assert [p.text for p in paragrafi] == ["Prima riga", "Seconda riga"]
    assert paragrafi[0].paragraph_format.line_spacing == 1.0
    assert paragrafi[0].paragraph_format.space_after.pt == 0
    assert paragrafi[1].paragraph_format.line_spacing == 1.5
    assert paragrafi[1].paragraph_format.space_before.pt == 3
    assert paragrafi[1].paragraph_format.space_after.pt == 6
    assert paragrafi[1].alignment == WD_ALIGN_PARAGRAPH.RIGHT


def test_margini_cella_diretti_prevalgono_sullo_stile_e_ritornano(tmp_path):
    import io
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from pct.editor import html_to_docx

    def costruisci(d):
        cella = d.add_table(rows=1, cols=1).cell(0, 0)
        cella.text = "Margini della cella"
        margini = OxmlElement("w:tcMar")
        lato = OxmlElement("w:left")
        lato.set(qn("w:w"), "180")
        lato.set(qn("w:type"), "dxa")
        margini.append(lato)
        cella._tc.get_or_add_tcPr().append(margini)

    html = _scrivi(costruisci, tmp_path).html
    assert "padding-left:9pt" in html
    assert "padding-right:5.4pt" in html
    assert "padding-top:0pt" in html
    esportato = Document(io.BytesIO(html_to_docx(html)))
    margini = esportato.tables[0].cell(0, 0)._tc.tcPr.find(qn("w:tcMar"))
    assert margini.find(qn("w:left")).get(qn("w:w")) == "180"
    assert margini.find(qn("w:right")).get(qn("w:w")) == "108"


def test_spaziatura_dell_elenco_arriva_e_ritorna(tmp_path):
    import io
    from pct.editor import html_to_docx

    def costruisci(d):
        p = d.add_paragraph("Voce da conservare", style="List Number")
        p.paragraph_format.line_spacing = 1.25
        p.paragraph_format.space_after = Pt(7)

    html = _scrivi(costruisci, tmp_path).html
    assert re.search(r'<li style="[^"]*margin-bottom:7pt;line-height:1.25', html)
    paragrafo = Document(io.BytesIO(html_to_docx(html))).paragraphs[0]
    assert paragrafo.paragraph_format.line_spacing == 1.25
    assert paragrafo.paragraph_format.space_after.pt == 7


def test_spaziatura_predefinita_del_docx_arriva_nell_editor_e_ritorna(tmp_path):
    import io
    from pct.editor import html_to_docx

    originale = Document()
    originale.add_paragraph('Spaziatura ereditata dal documento')
    percorso = tmp_path / 'spaziatura.docx'
    originale.save(percorso)
    html = converti_docx(percorso).html
    assert 'margin-top:0pt' in html
    assert 'margin-bottom:10pt' in html
    assert 'line-height:1.15' in html
    risultato = Document(io.BytesIO(html_to_docx(html)))
    formato = risultato.paragraphs[0].paragraph_format
    assert formato.space_before.pt == 0
    assert formato.space_after.pt == 10
    assert formato.line_spacing == pytest.approx(1.15, abs=0.005)


def test_interlinea_singola_e_spazi_zero_prevalgono_sui_default(tmp_path):
    def costruisci(d):
        formato = d.add_paragraph('Nessuno spazio aggiunto').paragraph_format
        formato.space_before = Pt(0)
        formato.space_after = Pt(0)
        formato.line_spacing = 1.0

    html = _scrivi(costruisci, tmp_path).html
    assert 'margin-top:0pt' in html and 'margin-bottom:0pt' in html
    assert 'line-height:1.00' in html


def test_grassetto_corsivo_sottolineato_e_barrato_restano(tmp_path):
    def costruisci(d):
        p = d.add_paragraph()
        p.add_run("grassetto").bold = True
        p.add_run(" corsivo").italic = True
        p.add_run(" sottolineato").underline = True
        p.add_run(" barrato").font.strike = True

    html = _scrivi(costruisci, tmp_path).html
    assert "<strong>" in html and "<em>" in html
    assert "<u>" in html, "il sottolineato e' andato perso"
    assert "<s>" in html, "il barrato e' andato perso"


def test_il_colore_del_testo_arriva(tmp_path):
    def costruisci(d):
        p = d.add_paragraph()
        p.add_run("nero")
        rosso = p.add_run(" rilievo")
        rosso.font.color.rgb = RGBColor(0xBF, 0x19, 0x19)

    html = _scrivi(costruisci, tmp_path).html
    assert "#bf1919" in html.lower(), "il colore del testo e' andato perso"


def test_carattere_e_corpo_si_leggono_anche_quando_sono_ereditati(tmp_path):
    """In un DOCX quasi niente e' scritto dove lo si cerca: quasi tutto si eredita."""
    def costruisci(d):
        normale = d.styles["Normal"]
        normale.font.name = "Times New Roman"
        normale.font.size = Pt(12)
        d.add_paragraph("testo che non dichiara niente di suo")
        grande = d.add_paragraph()
        pezzo = grande.add_run("questo invece dichiara")
        pezzo.font.size = Pt(18)

    esito = _scrivi(costruisci, tmp_path)
    assert "Times New Roman" in esito.caratteri, (
        f"il carattere ereditato non e' stato letto: {esito.caratteri}"
    )
    assert "18" in esito.html, "il corpo dichiarato sul tratto e' andato perso"


def test_rientri_e_interlinea_arrivano(tmp_path):
    def costruisci(d):
        p = d.add_paragraph("paragrafo rientrato")
        p.paragraph_format.first_line_indent = Mm(10)
        p.paragraph_format.left_indent = Mm(15)
        p.paragraph_format.line_spacing = 1.5

    html = _scrivi(costruisci, tmp_path).html
    assert "text-indent" in html, "il rientro di prima riga e' andato perso"
    assert "margin-left" in html, "il rientro del paragrafo e' andato perso"
    assert "line-height" in html, "l'interlinea e' andata persa"


def test_gli_elenchi_restano_elenchi(tmp_path):
    def costruisci(d):
        d.add_paragraph("PREMESSO CHE")
        d.add_paragraph("primo punto", style="List Number")
        d.add_paragraph("secondo punto", style="List Number")
        d.add_paragraph("un punto puntato", style="List Bullet")

    html = _scrivi(costruisci, tmp_path).html
    assert '<ol data-iu-word-list="true">' in html, "l'elenco numerato e' diventato una sequenza di paragrafi"
    assert '<ul data-iu-word-list="true">' in html, "l'elenco puntato e' diventato una sequenza di paragrafi"
    from lxml import html as html_parser
    assert len(html_parser.fromstring(html).xpath(".//li")) == 3
    assert "primo punto" in _testo(html)


def test_la_tabella_con_intestazione_in_grassetto_ha_i_th(tmp_path):
    def costruisci(d):
        tabella = d.add_table(rows=3, cols=2)
        tabella.style = "Table Grid"
        dati = [("Voce", "Importo"), ("Contributo unificato", "EUR 518,00"),
                ("Compenso", "EUR 2.430,00")]
        for indice, (a, b) in enumerate(dati):
            tabella.rows[indice].cells[0].text = a
            tabella.rows[indice].cells[1].text = b
        for cella in tabella.rows[0].cells:
            for paragrafo in cella.paragraphs:
                for pezzo in paragrafo.runs:
                    pezzo.bold = True

    html = _scrivi(costruisci, tmp_path).html
    assert "<table" in html
    assert html.count("<th") == 2, "la riga di intestazione e' diventata una riga qualsiasi"
    assert html.count("<td") == 4
    assert "Contributo unificato" in _testo(html)


def test_una_tabella_in_mezzo_al_testo_resta_al_suo_posto(tmp_path):
    """Chi legge paragrafi e tabelle separatamente si ritrova le tabelle in fondo."""
    def costruisci(d):
        d.add_paragraph("PRIMA della tabella")
        tabella = d.add_table(rows=1, cols=2)
        tabella.rows[0].cells[0].text = "cella sinistra"
        tabella.rows[0].cells[1].text = "cella destra"
        d.add_paragraph("DOPO la tabella")

    html = _scrivi(costruisci, tmp_path).html
    posizione_prima = html.index("PRIMA")
    posizione_tabella = html.index("<table")
    posizione_dopo = html.index("DOPO")
    assert posizione_prima < posizione_tabella < posizione_dopo, (
        "la tabella non e' rimasta fra i due paragrafi"
    )


def test_formato_e_margini_della_pagina_sono_dichiarati(tmp_path):
    def costruisci(d):
        sezione = d.sections[0]
        sezione.page_width, sezione.page_height = Mm(210), Mm(297)
        sezione.left_margin = sezione.right_margin = Mm(25)
        d.add_paragraph("atto")

    esito = _scrivi(costruisci, tmp_path)
    assert esito.formato["formato"] == "A4"
    assert esito.formato["orientamento"] == "verticale"
    assert esito.formato["margini_pt"]["sinistro"] == pytest.approx(70.9, abs=1.0)


def test_una_pagina_orizzontale_viene_riconosciuta(tmp_path):
    def costruisci(d):
        sezione = d.sections[0]
        sezione.page_width, sezione.page_height = Mm(297), Mm(210)
        d.add_paragraph("prospetto")

    esito = _scrivi(costruisci, tmp_path)
    assert esito.formato["orientamento"] == "orizzontale"


def test_un_documento_vuoto_non_fa_saltare_la_conversione(tmp_path):
    esito = _scrivi(lambda d: None, tmp_path)
    assert esito.pagine
    assert esito.avvisi


def test_un_file_che_non_e_un_docx_viene_rifiutato(tmp_path):
    finto = tmp_path / "finto.docx"
    finto.write_bytes(b"non sono un documento")
    with pytest.raises(DocxError, match="illeggibile"):
        converti_docx(finto)


# ---------------------------------------------------------------------------
# Quello che un atto ha davvero, oltre al testo formattato
# ---------------------------------------------------------------------------

def test_il_formato_dichiarato_su_uno_stile_viene_letto(tmp_path):
    """Un atto scritto con gli stili di Word — cioe' quasi ogni atto — non
    dichiara niente sul paragrafo: sta tutto sullo stile."""
    def costruisci(d):
        corpo = d.styles.add_style("CorpoAtto", 1)
        corpo.font.name = "Times New Roman"
        corpo.font.size = Pt(12)
        corpo.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        corpo.paragraph_format.first_line_indent = Mm(10)
        corpo.paragraph_format.space_after = Pt(6)
        corpo.paragraph_format.line_spacing = 1.4
        d.add_paragraph("Paragrafo che non dichiara niente di suo.", style="CorpoAtto")

    html = _scrivi(costruisci, tmp_path).html
    assert "text-align:justify" in html, "il giustificato dello stile e' andato perso"
    assert "text-indent" in html, "il rientro dello stile e' andato perso"
    assert "margin-bottom" in html, "la spaziatura dello stile e' andata persa"
    assert "line-height" in html, "l'interlinea dello stile e' andata persa"


def test_il_collegamento_porta_con_se_il_suo_testo(tmp_path):
    """Chi legge solo `paragraph.runs` salta quello che sta dentro un
    collegamento: non perde il link, perde l'indirizzo scritto."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def costruisci(d):
        paragrafo = d.add_paragraph()
        relazione = d.part.relate_to(
            "https://www.iusentra.it",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
            is_external=True,
        )
        collegamento = OxmlElement("w:hyperlink")
        collegamento.set(qn("r:id"), relazione)
        pezzo = OxmlElement("w:r")
        testo = OxmlElement("w:t")
        testo.text = "www.iusentra.it"
        pezzo.append(testo)
        collegamento.append(pezzo)
        paragrafo._p.append(collegamento)

    html = _scrivi(costruisci, tmp_path).html
    assert "www.iusentra.it" in _testo(html), "il testo del collegamento e' sparito"
    assert "<a href" in html, "il collegamento e' diventato testo semplice"
    assert "iusentra.it" in html


def test_un_a_capo_dentro_il_paragrafo_resta_un_a_capo(tmp_path):
    def costruisci(d):
        paragrafo = d.add_paragraph()
        paragrafo.add_run("Studio legale Affinito")
        paragrafo.add_run().add_break()
        paragrafo.add_run("via Duomo 118, Napoli")

    html = _scrivi(costruisci, tmp_path).html
    assert "<br>" in html, "le due righe dell'indirizzo sono diventate una sola"
    assert "Studio legale" in _testo(html) and "via Duomo" in _testo(html)


def test_un_salto_di_pagina_apre_una_pagina_nuova(tmp_path):
    from docx.enum.text import WD_BREAK

    def costruisci(d):
        d.add_paragraph("prima pagina")
        salto = d.add_paragraph()
        salto.add_run().add_break(WD_BREAK.PAGE)
        d.add_paragraph("seconda pagina")

    esito = _scrivi(costruisci, tmp_path)
    assert len(esito.pagine) == 2, "il salto di pagina e' stato ignorato"
    assert 'data-pagina="2"' in esito.html


def test_il_logo_dello_studio_arriva_nell_editor(tmp_path):
    from docx.shared import Inches
    from PIL import Image

    def costruisci(d):
        logo = tmp_path / "logo.png"
        Image.new("RGB", (120, 40), (30, 60, 140)).save(str(logo))
        d.add_picture(str(logo), width=Inches(1.6))
        d.add_paragraph("atto con intestazione")

    esito = _scrivi(costruisci, tmp_path)
    assert "<img" in esito.html, "il logo e' sparito"
    assert "data:image/" in esito.html, "l'immagine non porta con se' i suoi dati"
    assert esito.pagine[0].immagini == 1


def test_le_larghezze_delle_colonne_sono_quelle_dichiarate(tmp_path):
    def costruisci(d):
        tabella = d.add_table(rows=2, cols=2)
        tabella.columns[0].width = Mm(120)
        tabella.columns[1].width = Mm(40)
        tabella.rows[0].cells[0].text = "descrizione lunga"
        tabella.rows[0].cells[1].text = "EUR 1,00"

    html = _scrivi(costruisci, tmp_path).html
    larghezze = re.findall(r"width:([0-9.]+)%", html)
    assert larghezze, "le colonne non hanno larghezza: l'editor le fara' uguali"
    assert float(larghezze[0]) > float(larghezze[1]), (
        f"la colonna larga non e' la prima: {larghezze}"
    )


def test_spaziatura_table_grid_precede_docdefaults(tmp_path):
    def costruisci(d):
        tabella = d.add_table(rows=1, cols=1)
        tabella.style = 'Table Grid'
        tabella.cell(0, 0).text = 'Testo della cella'

    from lxml import html as html_parser
    risultato = html_parser.fromstring(_scrivi(costruisci, tmp_path).html)
    stile = risultato.xpath('//td/p')[0].get('style')
    assert 'line-height:1' in stile
    assert 'margin-bottom:0pt' in stile


def test_bordi_sfondo_e_geometria_tabella_roundtrip(tmp_path):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from pct.editor import html_to_docx
    import io

    def costruisci(d):
        t = d.add_table(rows=1, cols=2)
        t.style = 'Table Grid'
        t.columns[0].width = Mm(120)
        t.columns[1].width = Mm(40)
        t.cell(0, 0).text = 'Descrizione'
        t.cell(0, 1).text = 'Valore'
        bordi = OxmlElement('w:tcBorders')
        sopra = OxmlElement('w:top')
        for chiave, valore in [('val', 'double'), ('sz', '12'), ('color', '224488')]:
            sopra.set(qn('w:' + chiave), valore)
        bordi.append(sopra)
        t.cell(0, 0)._tc.get_or_add_tcPr().append(bordi)
        sfondo = OxmlElement('w:shd')
        sfondo.set(qn('w:fill'), 'FFEEDD')
        t.cell(0, 0)._tc.get_or_add_tcPr().append(sfondo)

    risultato = _scrivi(costruisci, tmp_path)
    assert 'border-top:1.5pt double #224488' in risultato.html
    assert 'border-bottom:0.5pt solid #000000' in risultato.html
    assert 'background-color:#ffeedd' in risultato.html
    ritorno = Document(io.BytesIO(html_to_docx(risultato.html)))
    cella = ritorno.tables[0].cell(0, 0)
    sopra = cella._tc.tcPr.find(qn('w:tcBorders')).find(qn('w:top'))
    assert sopra.get(qn('w:val')) == 'double'
    assert sopra.get(qn('w:sz')) == '12'
    assert sopra.get(qn('w:color')) == '224488'
    assert cella._tc.tcPr.find(qn('w:shd')).get(qn('w:fill')) == 'FFEEDD'
    assert ritorno.sections[0].page_width == Document(tmp_path / 'atto.docx').sections[0].page_width


def test_un_elenco_annidato_resta_annidato(tmp_path):
    def costruisci(d):
        d.add_paragraph("punto principale", style="List Number")
        sotto = d.add_paragraph("sotto punto", style="List Number")
        numerazione = sotto._p.get_or_add_pPr().get_or_add_numPr()
        livello = numerazione.get_or_add_ilvl()
        livello.val = 1
        d.add_paragraph("altro punto principale", style="List Number")

    html = _scrivi(costruisci, tmp_path).html
    assert html.count('<ol data-iu-word-list="true">') == 2, f"l'annidamento e' andato perso: {html}"
    assert "sotto punto" in _testo(html)
    from lxml import html as html_parser
    radice = html_parser.fromstring(html)
    assert radice.xpath('//ol/li/ol/li'), html


def test_elenco_editor_annidato_roundtrip_conserva_livello_e_testo(tmp_path):
    from pct.editor import html_to_docx
    from lxml import html as html_parser
    percorso = tmp_path / 'elenco-editor.docx'
    percorso.write_bytes(html_to_docx(
        '<ol><li>Prima voce<ol><li>Voce figlia<ul><li>Dettaglio</li></ul>'
        '</li></ol></li><li>Seconda voce</li></ol>'
    ))
    risultato = converti_docx(percorso)
    radice = html_parser.fromstring(risultato.html)
    assert radice.xpath('//ol/li/ol/li/ul/li')[0].text_content() == 'Dettaglio'
    assert [n.text_content() for n in radice.xpath('//section/ol/li')] == [
        'Prima voceVoce figliaDettaglio', 'Seconda voce',
    ]


def test_a_capo_non_raddoppiati_da_salvataggi_ripetuti(tmp_path):
    from pct.editor import html_to_docx
    from lxml import html as html_parser
    fonte = '<p>Prima<br>Seconda<br>Terza</p><table><tr><td><br></td></tr></table>'
    percorso = tmp_path / 'a-capo.docx'
    for _ in range(3):
        percorso.write_bytes(html_to_docx(fonte))
        fonte = converti_docx(percorso).html
        radice = html_parser.fromstring(fonte)
        assert len(radice.xpath('//section/p/br')) == 2
        assert len(radice.xpath('//td//br')) == 1
        assert radice.xpath('//section/p')[0].text_content() == 'PrimaSecondaTerza'

def test_sezioni_con_misure_diverse_e_cambio_pagina_roundtrip(tmp_path):
    from docx.enum.section import WD_ORIENT, WD_SECTION
    from docx.enum.text import WD_BREAK
    from pct.editor import html_to_docx
    from lxml import html as parser
    documento = Document()
    documento.sections[0].page_width = Mm(210)
    documento.sections[0].page_height = Mm(297)
    documento.sections[0].left_margin = Mm(20)
    documento.add_paragraph('Sezione verticale')
    seconda = documento.add_section(WD_SECTION.NEW_PAGE)
    seconda.orientation = WD_ORIENT.LANDSCAPE
    seconda.page_width, seconda.page_height = Mm(297), Mm(210)
    seconda.left_margin = Mm(35)
    documento.add_paragraph('Sezione orizzontale')
    documento.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    documento.add_paragraph('Ancora nella seconda sezione')
    percorso = tmp_path / 'sezioni.docx'
    documento.save(percorso)
    for _ in range(3):
        risultato = converti_docx(percorso)
        radice = parser.fromstring(risultato.html)
        pagine = radice.xpath('//section')
        assert [p.get('data-sezione-word') for p in pagine] == ['1', '2', '2']
        assert [p.orientamento for p in risultato.pagine] == ['verticale', 'orizzontale', 'orizzontale']
        assert float(pagine[0].get('data-margine-sinistro')) == pytest.approx(Mm(20).pt, abs=.02)
        assert float(pagine[1].get('data-margine-sinistro')) == pytest.approx(Mm(35).pt, abs=.02)
        percorso.write_bytes(html_to_docx(risultato.html))
        riaperto = Document(percorso)
        assert len(riaperto.sections) == 2
        assert riaperto.sections[1].orientation == WD_ORIENT.LANDSCAPE
        assert riaperto.sections[1].start_type == WD_SECTION.NEW_PAGE
        assert riaperto.sections[1].left_margin.pt == pytest.approx(Mm(35).pt, abs=.1)
        assert [p.text for p in riaperto.paragraphs if p.text] == [
            'Sezione verticale', 'Sezione orizzontale', 'Ancora nella seconda sezione',
        ]


@pytest.mark.parametrize('tipo', [0, 1, 3, 4])
def test_tipo_sezione_nativa_conservato(tmp_path, tipo):
    from docx.enum.section import WD_SECTION
    from pct.editor import html_to_docx
    documento = Document()
    documento.add_paragraph('Prima sezione')
    documento.add_section(WD_SECTION(tipo))
    documento.add_paragraph('Seconda sezione')
    percorso = tmp_path / 'tipo-sezione.docx'
    documento.save(percorso)
    risultato = converti_docx(percorso)
    percorso.write_bytes(html_to_docx(risultato.html))
    riaperto = Document(percorso)
    assert len(riaperto.sections) == 2
    assert int(riaperto.sections[1].start_type) == tipo

def test_sezione_finale_vuota_non_persa(tmp_path):
    from docx.enum.section import WD_SECTION
    from pct.editor import html_to_docx
    d = Document()
    d.add_paragraph('Testo nella prima sezione')
    d.add_section(WD_SECTION.NEW_PAGE).left_margin = Mm(40)
    p = tmp_path / 'sezione-vuota.docx'
    d.save(p)
    esito = converti_docx(p)
    assert len(esito.pagine) == 2
    p.write_bytes(html_to_docx(esito.html))
    r = Document(p)
    assert len(r.sections) == 2
    assert r.sections[1].left_margin.pt == pytest.approx(Mm(40).pt, abs=.1)


def test_intestazioni_piedi_varianti_e_campi_roundtrip(tmp_path):
    from docx.enum.section import WD_SECTION
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from pct.editor import html_to_docx
    from lxml import html as parser
    d = Document()
    d.add_paragraph('Corpo prima sezione')
    first = d.sections[0]
    first.header_distance, first.footer_distance = Mm(12), Mm(10)
    first.different_first_page_header_footer = True
    d.settings.odd_and_even_pages_header_footer = True
    first.header.paragraphs[0].text = 'Intestazione ordinaria'
    first.first_page_header.paragraphs[0].text = 'Prima pagina'
    first.even_page_header.paragraphs[0].text = 'Pagina pari'
    footer = first.footer.paragraphs[0]
    footer.add_run('Pagina ')
    for kind, value in [('begin', None), (None, ' PAGE '), ('separate', None), (None, '1'), ('end', None)]:
        run = OxmlElement('w:r')
        node = OxmlElement('w:fldChar' if kind else ('w:instrText' if value.startswith(' PAGE') else 'w:t'))
        if kind:
            node.set(qn('w:fldCharType'), kind)
        else:
            node.text = value
        run.append(node)
        footer._p.append(run)
    d.add_section(WD_SECTION.NEW_PAGE)
    d.add_paragraph('Corpo seconda sezione')
    p = tmp_path / 'header-footer.docx'
    d.save(p)
    for _ in range(3):
        result = converti_docx(p)
        root = parser.fromstring(result.html)
        assert root.xpath('//*[@data-iu-word-field="PAGE"]')
        assert root.xpath('//*[@data-iu-word-kind="first"]')
        assert root.xpath('//*[@data-iu-word-kind="even"]')
        p.write_bytes(html_to_docx(result.html))
        r = Document(p)
        assert [p.text for p in r.paragraphs if p.text] == ['Corpo prima sezione', 'Corpo seconda sezione']
        assert r.sections[0].header.paragraphs[0].text == 'Intestazione ordinaria'
        assert r.sections[0].first_page_header.paragraphs[0].text == 'Prima pagina'
        assert r.sections[0].even_page_header.paragraphs[0].text == 'Pagina pari'
        assert r.sections[0].footer._element.findall('.//' + qn('w:fldSimple'))[0].get(qn('w:instr')) == 'PAGE'
        assert r.sections[1].header.is_linked_to_previous
        assert r.sections[1].footer.is_linked_to_previous
        assert r.sections[0].different_first_page_header_footer
        assert r.settings.odd_and_even_pages_header_footer
        assert abs(r.sections[0].header_distance.mm - 12) < .05
        assert abs(r.sections[0].footer_distance.mm - 10) < .05


def test_paragrafi_vuoti_e_segno_elenco_nativo(tmp_path):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from pct.editor import html_to_docx
    d = Document()
    d.add_paragraph('Prima')
    blank = d.add_paragraph()
    rpr = OxmlElement('w:rPr')
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '39')
    rpr.append(sz)
    blank._p.get_or_add_pPr().append(rpr)
    item = d.add_paragraph('Voce', 'List Bullet')
    numbering = d.part.numbering_part.element
    num_id = item.style.element.find(qn('w:pPr')).find(qn('w:numPr')).find(qn('w:numId')).get(qn('w:val'))
    num = next(n for n in numbering.findall(qn('w:num')) if n.get(qn('w:numId')) == num_id)
    aid = num.find(qn('w:abstractNumId')).get(qn('w:val'))
    abstract = next(n for n in numbering.findall(qn('w:abstractNum')) if n.get(qn('w:abstractNumId')) == aid)
    abstract.find(qn('w:lvl')).find(qn('w:lvlText')).set(qn('w:val'), '-')
    path = tmp_path / 'vuoti-elenco.docx'
    d.save(path)
    result = converti_docx(path)
    assert 'data-iu-word-empty-size="19.5"' in result.html
    assert 'data-iu-word-list-glyph="-"' in result.html
    path.write_bytes(html_to_docx(result.html))
    rebuilt = Document(path)
    assert [p.text for p in rebuilt.paragraphs] == ['Prima', '', 'Voce']
    assert rebuilt.paragraphs[1]._p.find(qn('w:pPr')).find(qn('w:rPr')).find(qn('w:sz')).get(qn('w:val')) == '39'
    assert rebuilt.paragraphs[2].paragraph_format.left_indent.pt == 18
    assert rebuilt.paragraphs[2].paragraph_format.first_line_indent.pt == -18
    assert any(x.get(qn('w:val')) == '-' for x in rebuilt.part.numbering_part.element.iter(qn('w:lvlText')))
    reopened = converti_docx(path)
    assert 'data-iu-word-list-glyph="-"' in reopened.html
    assert '<ul data-iu-word-list="true">' in reopened.html



def test_spaziatura_lettere_mezzo_punto_sottolineatura_spessa(tmp_path):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
    from pct.editor import html_to_docx
    d = Document()
    d.styles['Normal'].font.size = Pt(14.5)
    p = d.add_paragraph()
    p.add_run('Base')
    r = p.add_run(' Firma')
    r.font.size = Pt(14)
    spacing = OxmlElement('w:spacing')
    spacing.set(qn('w:val'), '66')
    r._r.get_or_add_rPr().append(spacing)
    underline = OxmlElement('w:u')
    underline.set(qn('w:val'), 'thick')
    r._r.get_or_add_rPr().append(underline)
    path = tmp_path / 'lettere.docx'
    d.save(path)
    result = converti_docx(path)
    path.write_bytes(html_to_docx(result.html))
    r = Document(path).paragraphs[0].runs[-1]
    assert r.font.size.pt == 14
    assert r._r.find(qn('w:rPr')).find(qn('w:spacing')).get(qn('w:val')) == '66'
    assert r._r.find(qn('w:rPr')).find(qn('w:u')).get(qn('w:val')) == 'thick'
