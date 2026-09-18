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

fitz = pytest.importorskip("pymupdf", reason="PyMuPDF non installato")


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
    """Lo stesso atto, ma solo immagine: nessun testo dentro il PDF."""
    originale = _pdf(flow)
    percorso = _percorso_temporaneo(".pdf")
    sorgente, esito = fitz.open(originale), fitz.open()
    for pagina in sorgente:
        pix = pagina.get_pixmap(dpi=200)
        nuova = esito.new_page(width=pagina.rect.width, height=pagina.rect.height)
        nuova.insert_image(nuova.rect, stream=pix.tobytes("png"))
    esito.save(percorso)
    sorgente.close()
    esito.close()
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
    """Due liste di font si disallineano al primo carattere aggiunto: la fonte e' una."""
    from pct.template_atti import EDITOR_FONT_CATALOG

    catalogo = {str(voce["label"]) for voce in EDITOR_FONT_CATALOG.values()}
    assert set(FAMIGLIE_EDITOR) == catalogo, "la tendina dell'importazione non e' quella dell'editor"
