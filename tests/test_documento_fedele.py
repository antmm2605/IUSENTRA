"""L'importazione fedele: quello che l'importazione «a testo» perdeva.

Un atto importato male l'avvocato deve riscriverlo: qui la fedelta' non e'
estetica, e' tempo di lavoro. I test girano su PDF veri, generati e riletti,
non su HTML finto.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import pytest
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pct.documento_fedele import FAMIGLIE_EDITOR, converti_file, famiglia_editor, pila_font


def _stile(nome: str = "Times-Roman", corpo: float = 11, allineamento: int = TA_JUSTIFY) -> ParagraphStyle:
    return ParagraphStyle(
        nome + str(allineamento), parent=getSampleStyleSheet()["Normal"],
        alignment=allineamento, fontName=nome, fontSize=corpo, leading=corpo * 1.36,
    )


def _percorso_temporaneo(suffisso: str) -> str:
    """Un percorso temporaneo creato in modo sicuro.

    `tempfile.mktemp` restituisce un nome senza creare il file: fra il nome e
    la scrittura qualcun altro puo' occuparlo. `mkstemp` lo crea subito, con
    permessi ristretti, e restituisce il percorso gia' riservato.
    """
    descrittore, percorso = tempfile.mkstemp(suffix=suffisso)
    os.close(descrittore)
    return percorso


def _pdf(flow, *, pagina=A4, margine: float = 25) -> str:
    percorso = _percorso_temporaneo(".pdf")
    SimpleDocTemplate(
        percorso, pagesize=pagina,
        leftMargin=margine * mm, rightMargin=margine * mm,
        topMargin=margine * mm, bottomMargin=margine * mm,
    ).build(flow)
    return percorso


def _html(percorso: str) -> str:
    documento = converti_file(percorso)
    Path(percorso).unlink(missing_ok=True)
    return "\n".join(pagina.html for pagina in documento.pagine)


TABELLA_ECONOMICA = Table(
    [["Voce", "Importo"], ["Contributo unificato", "EUR 518,00"], ["Compenso", "EUR 2.430,00"]],
    colWidths=[80 * mm, 40 * mm],
    style=TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDDDDD")),
    ]),
)


def test_una_tabella_resta_una_tabella():
    """Letta come testo continuo, una tabella l'avvocato deve riscriverla."""
    html = _html(_pdf([TABELLA_ECONOMICA]))
    assert "<table" in html, "la tabella non e' stata riconosciuta"
    assert html.count("<td") + html.count("<th") == 6, "celle perse o inventate"
    assert "Contributo unificato" in html and "518,00" in html


def test_la_riga_di_intestazione_e_il_suo_sfondo_sopravvivono():
    html = _html(_pdf([TABELLA_ECONOMICA]))
    assert "<th" in html, "la riga di intestazione e' diventata una riga qualsiasi"
    assert "#dddddd" in html.lower(), "lo sfondo dell'intestazione e' andato perso"


def test_grassetto_corsivo_e_sottolineato_restano():
    html = _html(_pdf([Paragraph(
        "Il sottoscritto avv. <b>Mario Rossi</b> espone quanto segue in "
        "<i>fatto</i> e in <u>diritto</u>.", _stile())]))
    assert "<strong>" in html and "Mario Rossi" in html
    assert "<em>" in html and "fatto" in html
    assert "<u>" in html and "diritto" in html


def test_il_filetto_di_una_cella_non_diventa_una_sottolineatura():
    """Il difetto vero: in un atto con tabella bordata usciva sottolineata ogni cella.

    Nel PDF una sottolineatura non e' un attributo del testo, e' una linea
    disegnata sotto le lettere — e lo e' anche il bordo di una cella. Quello
    che li distingue e' quanto la linea sporge oltre il testo.
    """
    html = _html(_pdf([TABELLA_ECONOMICA]))
    sottolineati = re.findall(r"<u>(.*?)</u>", html)
    assert sottolineati == [], f"bordi di cella letti come sottolineature: {sottolineati}"


def test_la_sottolineatura_vera_non_viene_buttata_via_col_filetto():
    """La controprova: stringere la regola non deve perdere il caso buono."""
    html = _html(_pdf([
        Paragraph("Si chiede che il Giudice voglia <u>accogliere il ricorso</u>.", _stile()),
        Spacer(1, 6 * mm),
        TABELLA_ECONOMICA,
    ]))
    sottolineati = re.findall(r"<u>(.*?)</u>", html)
    assert any("accogliere il ricorso" in voce for voce in sottolineati), "persa la sottolineatura vera"
    assert not [v for v in sottolineati if "EUR" in v or "Contributo" in v], "cella sottolineata per errore"


def test_la_centratura_di_un_titolo_non_diventa_testo_a_sinistra():
    html = _html(_pdf([Paragraph("TRIBUNALE ORDINARIO DI VICENZA",
                                 _stile("Times-Bold", 16, TA_CENTER))]))
    assert "text-align:center" in html


def test_il_carattere_dichiarato_dal_pdf_arriva_all_editor():
    html = _html(_pdf([Paragraph("Atto di citazione", _stile("Times-Roman"))]))
    assert "Times" in html, "il carattere del PDF non e' arrivato all'editor"


def test_formato_e_orientamento_della_pagina_sono_dichiarati():
    percorso = _pdf([Paragraph("Ricorso", _stile())], pagina=landscape(A4))
    documento = converti_file(percorso)
    Path(percorso).unlink(missing_ok=True)
    assert documento.formato["formato"] == "A4"
    assert documento.formato["orientamento"] == "orizzontale"
    assert documento.formato["margini_pt"]["sinistro"] > 0


def test_ogni_font_del_pdf_cade_in_una_famiglia_offerta_dall_editor():
    """Una famiglia fuori tendina si presenta all'avvocato come carattere mancante."""
    for dichiarato in ("TimesNewRomanPSMT", "ArialMT", "Calibri-Bold", "CourierNewPS-BoldMT",
                       "ABCDEF+LiberationSerif", "Garamond-Italic", "Sconosciuto-9"):
        famiglia, _ = famiglia_editor(dichiarato)
        assert famiglia in FAMIGLIE_EDITOR, f"{dichiarato} -> {famiglia} non e' in tendina"
        assert pila_font(dichiarato), "pila CSS vuota"


def test_un_documento_senza_testo_non_fa_saltare_la_conversione():
    documento = converti_file(_pdf([Spacer(1, 10 * mm)]))
    assert documento.pagine, "nessuna pagina restituita"


def _scansione(flow) -> str:
    """Lo stesso atto, ma solo immagine: nessun testo dentro il PDF.

    Si disegna ogni pagina e la si reincolla come figura: e' quello che fa uno
    scanner, ed e' l'unico modo di provare che il riconoscimento ottico parta
    davvero.
    """
    import io

    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as tela

    originale = _pdf(flow)
    percorso = _percorso_temporaneo(".pdf")
    documento = pdfium.PdfDocument(originale)
    foglio = None
    try:
        for indice in range(len(documento)):
            pagina = documento[indice]
            larghezza, altezza = pagina.get_width(), pagina.get_height()
            immagine = pagina.render(scale=200 / 72).to_pil().convert("RGB")
            if foglio is None:
                foglio = tela.Canvas(percorso, pagesize=(larghezza, altezza))
            else:
                foglio.setPageSize((larghezza, altezza))
            deposito = io.BytesIO()
            immagine.save(deposito, format="PNG")
            deposito.seek(0)
            foglio.drawImage(ImageReader(deposito), 0, 0,
                             width=larghezza, height=altezza)
            foglio.showPage()
        if foglio is not None:
            foglio.save()
    finally:
        documento.close()
    Path(originale).unlink(missing_ok=True)
    return percorso


def _tesseract_italiano() -> bool:
    try:
        import pytesseract

        from legal_ocr.motore import runtime

        runtime.configura(pytesseract)
        return "ita" in runtime.lingue_installate(pytesseract)
    except Exception:
        return False


@pytest.mark.skipif(not _tesseract_italiano(), reason="Tesseract italiano non installato")
def test_una_scansione_viene_letta_dal_motore_ocr_unico():
    """In IUSENTRA il riconoscimento ottico ha un solo motore: `legal_ocr/motore/`.

    Un secondo lettore con tarature proprie leggerebbe lo stesso atto in un
    altro modo, ed e' peggio di uno solo (docs/OCR_LEGAL.md).
    """
    percorso = _scansione([
        Paragraph("TRIBUNALE ORDINARIO DI VICENZA", _stile("Times-Roman", 13)),
        Paragraph("Ricorso ex art. 414 c.p.c. nel procedimento R.G. 1084/2026", _stile("Times-Roman", 13)),
    ])
    documento = converti_file(percorso)
    Path(percorso).unlink(missing_ok=True)
    html = "\n".join(pagina.html for pagina in documento.pagine)
    assert 'data-origine="ocr"' in html, f"scansione non riconosciuta: {documento.avvisi}"
    for atteso in ("TRIBUNALE", "VICENZA", "1084", "414"):
        assert atteso.lower() in html.lower(), f"«{atteso}» non riconosciuto"


def test_il_modulo_non_chiama_mai_tesseract_per_conto_proprio():
    """La regola, verificata sul sorgente: un solo motore OCR in tutto il progetto."""
    for modulo in Path("pct/documento_fedele").glob("*.py"):
        sorgente = modulo.read_text(encoding="utf-8")
        for vietata in ("image_to_data", "image_to_string", "image_to_boxes"):
            assert vietata not in sorgente, f"{modulo.name} chiama Tesseract direttamente ({vietata})"


def test_quando_il_riconoscimento_non_riesce_il_motivo_e_scritto(monkeypatch):
    """Un guasto si legge, non si indovina.

    La prima stesura inghiottiva ogni eccezione: un semplice import mancante
    spegneva il riconoscimento su tutte le scansioni senza dirlo a nessuno.
    """
    from pct.documento_fedele import conversione

    monkeypatch.setattr(conversione, "_ocr_pagina",
                        lambda *a, **k: (None, "Tesseract non configurato (prova)"))
    percorso = _scansione([Paragraph("Atto", _stile())])
    documento = converti_file(percorso)
    Path(percorso).unlink(missing_ok=True)
    assert any("Tesseract non configurato (prova)" in avviso for avviso in documento.avvisi), \
        f"il motivo del guasto non compare negli avvisi: {documento.avvisi}"


def test_i_caratteri_del_pdf_arrivano_alla_tendina_dell_editor():
    """Un carattere fuori tendina si presenta all'avvocato come «carattere mancante»."""
    percorso = _pdf([
        Paragraph("Atto in Times", _stile("Times-Roman")),
        Paragraph("Nota in Helvetica", _stile("Helvetica")),
        Paragraph("Codice in Courier", _stile("Courier")),
    ])
    documento = converti_file(percorso)
    Path(percorso).unlink(missing_ok=True)
    assert documento.caratteri, "nessun carattere dichiarato"
    fuori = [voce for voce in documento.caratteri if voce not in FAMIGLIE_EDITOR]
    assert not fuori, f"caratteri fuori dalla tendina dell'editor: {fuori}"


def test_il_corredo_di_word_e_riconosciuto_carattere_per_carattere():
    """Un atto che arriva da fuori studio e' scritto con i font di Word.

    Se il carattere non e' dichiarato, l'importazione lo ricade su un ripiego e
    l'atto cambia aspetto sotto gli occhi dell'avvocato.
    """
    atteso = {
        "Georgia": "Georgia", "BookAntiqua": "Book Antiqua", "Palatino Linotype": "Palatino Linotype",
        "BookmanOldStyle": "Bookman Old Style", "CenturySchoolbook": "Century Schoolbook",
        "Constantia": "Constantia", "Perpetua": "Perpetua", "Rockwell": "Rockwell", "Sylfaen": "Sylfaen",
        "Tahoma": "Tahoma", "SegoeUI": "Segoe UI", "TrebuchetMS": "Trebuchet MS",
        "CenturyGothic": "Century Gothic", "Candara": "Candara", "Corbel": "Corbel",
        "GillSansMT": "Gill Sans MT", "ArialNarrow": "Arial Narrow", "ArialBlack": "Arial Black",
        "Impact": "Impact", "ComicSansMS": "Comic Sans MS", "Consolas": "Consolas",
        "LucidaConsole": "Lucida Console", "CambriaMath": "Cambria Math",
    }
    for dichiarato, famiglia in atteso.items():
        letta, _ = famiglia_editor(dichiarato)
        assert letta == famiglia, f"{dichiarato} letto come {letta}, atteso {famiglia}"


def test_i_cloni_metrici_tornano_al_carattere_di_word():
    """Un PDF prodotto su Linux dichiara Carlito, ma il documento e' in Calibri."""
    for clone, originale in [("Carlito", "Calibri"), ("LiberationSerif", "Times New Roman"),
                             ("LiberationSans", "Arial"), ("Caladea", "Cambria"),
                             ("Gelasio", "Georgia"), ("Tinos", "Times New Roman")]:
        letta, _ = famiglia_editor(clone)
        assert letta == originale, f"{clone} letto come {letta}, atteso {originale}"


def test_la_tendina_dell_importazione_e_quella_dell_editor():
    """Due liste di font si disallineano al primo carattere aggiunto: la fonte e' una.

    Il catalogo si legge da `pct.catalogo_caratteri`, che non importa niente.
    Quando stava dentro `pct.template_atti` — che tira dentro il driver di
    PostgreSQL — bastava un ambiente senza quel driver perche' l'importazione
    trovasse tre caratteri invece di quarantasei e ogni atto tornasse in Times
    New Roman.
    """
    from pct.catalogo_caratteri import EDITOR_FONT_CATALOG

    catalogo = {str(voce["label"]) for voce in EDITOR_FONT_CATALOG.values()}
    assert set(FAMIGLIE_EDITOR) == catalogo, "la tendina dell'importazione non e' quella dell'editor"
    assert len(catalogo) > 20, "il catalogo dei caratteri non si e' caricato"


def test_un_rientro_di_sette_punti_si_dichiara_lo_stesso():
    """Sotto gli otto punti il rientro non apre un capoverso, ma esiste.

    In un atto con gli elenchi a filo di margine, il corpo del testo sta sette
    punti piu' dentro. Scartare quel rientro — perche' non basta a dire «qui
    comincia un capoverso nuovo» — appoggiava tutto il corpo al margine: sette
    punti a ogni riga, piu' del doppio del millimetro che il banco tollera, e
    le righe centrate scivolavano di tre e mezzo per giunta.
    """
    from pct.documento_fedele.modello import Riga, Tratto
    from pct.documento_fedele.paragrafi import _stile_paragrafo
    from pct.documento_fedele.taratura import Taratura

    assert Taratura.RIENTRO_DICHIARATO < 7.0 < Taratura.RIENTRO_MINIMO, (
        "il caso interessante e' proprio quello in mezzo alle due soglie"
    )

    def _riga(x0: float, y0: float, larga: float) -> Riga:
        return Riga(
            tratti=[Tratto(testo="parole del corpo", famiglia="Times New Roman", corpo=12.0)],
            bbox=(x0, y0, x0 + larga, y0 + 14.0),
        )

    # il corpo sta a 79.4, il margine della pagina a 72.4: sette punti
    blocco = [_riga(79.4, 300, 400), _riga(79.4, 321, 400)]
    stile = _stile_paragrafo(blocco, None, sinistra=72.4, destra=479.4,
                             corpo_base=12.0, interlinea=21.0)

    assert any(s.startswith("margin-left:7") for s in stile), (
        f"il rientro di sette punti doveva essere dichiarato: {stile}"
    )


def test_il_segno_dell_elenco_e_quello_dell_autore():
    """Un trattino non deve tornare pallino, e men che meno «(cid:127)».

    L'elenco dei testimoni di una memoria e' puntato con un trattino. Chi
    riscriveva il documento ci metteva il segno di riserva di reportlab, preso
    da un altro carattere: quando quel carattere il pallino non ce l'ha, nel
    PDF finisce la sigla del glifo mancante — «(cid:127)» in mezzo a un atto
    da depositare.
    """
    import io
    import re

    import pdfplumber

    from pct.documento_fedele.modello import Riga, Tratto
    from pct.documento_fedele.paragrafi import _elenco
    from pct.editor import html_to_pdf

    def _voce(testo: str, y: float) -> list[Riga]:
        return [Riga(
            tratti=[Tratto(testo=f"- {testo}", famiglia="Times New Roman", corpo=12.0)],
            bbox=(85.0, y, 400.0, y + 14.0),
        )]

    elemento = _elenco(
        [_voce("Avv. Brosio Elio", 300), _voce("Ing. Abate Saverio", 321)],
        numerato=False, corpo_base=12.0, famiglia_base="Times New Roman",
        sinistra=85.0, destra=510.0,
    )
    assert 'data-segno="-"' in elemento.html, (
        f"il segno dell'autore doveva restare scritto: {elemento.html[:120]}"
    )

    pagina = (
        '<section class="iu-doc-pagina" data-pagina="1"'
        ' data-larghezza="595.3" data-altezza="841.9"'
        ' data-margine-alto="56.7" data-margine-basso="56.7"'
        ' data-margine-sinistro="85" data-margine-destro="56.7"'
        ' data-interlinea="18" data-allineamento="left"'
        ' style="font-family:\'Times New Roman\', serif;font-size:12.0pt">'
        f"{elemento.html}</section>"
    )
    with pdfplumber.open(io.BytesIO(html_to_pdf(pagina))) as pdf:
        testo = pdf.pages[0].extract_text() or ""

    assert "(cid:" not in testo, f"nel PDF e' finita la sigla di un glifo: {testo!r}"
    assert "•" not in testo, "il trattino e' diventato un pallino"
    assert re.search(r"-\s+Avv\. Brosio Elio", testo), (
        f"la voce doveva tornare col suo trattino: {testo!r}"
    )


def test_una_riga_centrata_si_centra_sulla_colonna_del_testo():
    """Centrato su cosa: sulla cornice della pagina, o sulla colonna?

    Quando qualcosa sporge a sinistra — una carta intestata, un elenco a filo
    di margine — la cornice comincia prima della colonna del testo. L'autore
    ha centrato il titolo sulla colonna; chi riscriveva centrava sulla
    cornice, e ogni riga centrata dell'atto cadeva qualche punto a sinistra:
    il nome del tribunale, il «CONTRO», il numero di pagina.
    """
    from pct.documento_fedele.modello import Riga, Tratto
    from pct.documento_fedele.paragrafi import _stile_paragrafo

    def _riga(x0: float, x1: float) -> Riga:
        return Riga(
            tratti=[Tratto(testo="TRIBUNALE CIVILE DI PALMI",
                           famiglia="Times New Roman", corpo=16.0)],
            bbox=(x0, 300.0, x1, 318.0),
        )

    # la cornice comincia a 68.7, la colonna del testo a 79.4
    cornice_sx, cornice_dx = 68.7, 450.8
    # riga centrata sulla colonna [79.4, 450.8]: centro 265.1
    blocco = [_riga(148.3, 381.9)]

    stile = _stile_paragrafo(blocco, None, sinistra=cornice_sx, destra=cornice_dx,
                             corpo_base=12.0, interlinea=24.0)
    assert "text-align:center" in stile

    rientro = [s for s in stile if s.startswith("margin-left:")]
    assert rientro, f"il centro andava spostato a destra: {stile}"
    valore = float(rientro[0].split(":")[1].rstrip("pt"))
    # centro voluto 265.1, centro della cornice 259.75: cinque punti e mezzo,
    # che si recuperano aggiungendone il doppio a sinistra
    atteso = 2 * (265.1 - (cornice_sx + cornice_dx) / 2)
    assert abs(valore - atteso) < 0.6, f"atteso ~{atteso:.1f}pt, trovato {valore}pt"

    # una riga gia' centrata sulla cornice non deve prendere nessun rientro
    centrata = [_riga(200.0, 319.5)]
    assert not [s for s in _stile_paragrafo(
        centrata, None, sinistra=cornice_sx, destra=cornice_dx,
        corpo_base=12.0, interlinea=24.0) if s.startswith("margin-")]


def test_un_elenco_non_aggiunge_stacco_alle_voci():
    """Sei testimoni non devono spostare in giu' mezza pagina.

    Le voci di un elenco stanno alla stessa distanza delle righe del testo:
    quella distanza e' gia' scritta nell'interlinea di ogni voce. Chi
    riscriveva ce ne aggiungeva una sua — tre punti a voce — e su un elenco di
    sei testimoni la firma in fondo alla pagina scivolava di diciotto punti.
    """
    import io
    import re

    import pdfplumber

    from pct.documento_fedele.modello import Riga, Tratto
    from pct.documento_fedele.paragrafi import _elenco
    from pct.editor import html_to_pdf

    PASSO = 24.0

    def _voce(testo: str, y: float) -> list[Riga]:
        return [Riga(
            tratti=[Tratto(testo=f"- {testo}", famiglia="Times New Roman", corpo=12.0)],
            bbox=(79.4, y, 300.0, y + 14.0),
        )]

    partenza = 233.4
    voci = [_voce(f"Testimone numero {n}", partenza + n * PASSO) for n in range(6)]
    elemento = _elenco(voci, numerato=False, corpo_base=12.0,
                       famiglia_base="Times New Roman",
                       sinistra=79.4, destra=450.8, interlinea_pagina=PASSO)

    altezze = {float(a) for a in re.findall(r'line-height:([0-9.]+)pt', elemento.html)}
    assert altezze == {PASSO}, f"ogni voce doveva dichiarare il suo passo: {altezze}"

    pagina = (
        '<section class="iu-doc-pagina" data-pagina="1"'
        ' data-larghezza="595.3" data-altezza="841.9"'
        ' data-margine-alto="56.7" data-margine-basso="56.7"'
        ' data-margine-sinistro="79.4" data-margine-destro="144.5"'
        ' data-interlinea="24" data-allineamento="left"'
        ' style="font-family:\'Times New Roman\', serif;font-size:12.0pt">'
        f"{elemento.html}</section>"
    )
    with pdfplumber.open(io.BytesIO(html_to_pdf(pagina))) as pdf:
        cime = [r["top"] for r in pdf.pages[0].extract_text_lines()]

    assert len(cime) == 6, f"le voci erano sei e sono tornate {len(cime)}"
    passi = [b - a for a, b in zip(cime, cime[1:])]
    for passo in passi:
        assert abs(passo - PASSO) < 1.0, (
            f"fra una voce e l'altra ci sono {passo:.1f} punti invece di {PASSO}"
        )
