"""Il giro completo: PDF importato, riesportato, e rimesso accanto all'originale.

L'avvocato apre un atto nell'editor, cambia una data e lo risalva. Quello che
esce non e' piu' lo stesso file — e' un documento ricostruito — ma deve
sembrarlo: stesso numero di pagine, righe negli stessi punti, margini quelli.

Qui la promessa e' scritta in numeri, perche' finora era un'occhiata: le
pagine devono essere quelle e le parole devono stare dove stavano, entro un
millimetro. Senza questi test una taratura fatta su un atto si porta dietro
tutti gli altri senza che nessuno se ne accorga.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pdfplumber
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

from pct.documento_fedele import converti_file
from pct.editor import html_to_pdf, misure_del_documento, misure_delle_pagine
from pct.verifica_fedelta import confronta

PERIODO = (
    "Con atto di citazione ritualmente notificato la parte attrice conveniva "
    "in giudizio la societa' convenuta, esponendo che il contratto era stato "
    "inadempiuto sotto piu' profili e chiedendo la risoluzione oltre al "
    "risarcimento del danno patito. "
)


def _corpo(corpo: float = 12, interlinea: float = 24) -> ParagraphStyle:
    return ParagraphStyle(
        f"corpo{corpo}x{interlinea}", parent=getSampleStyleSheet()["Normal"],
        alignment=TA_JUSTIFY, fontName="Times-Roman",
        fontSize=corpo, leading=interlinea, spaceAfter=0,
    )


def _titolo() -> ParagraphStyle:
    return ParagraphStyle(
        "titolo", parent=getSampleStyleSheet()["Normal"], alignment=TA_CENTER,
        fontName="Times-Bold", fontSize=14, leading=24, spaceAfter=0,
    )


def _atto(flow, **margini) -> Path:
    descrittore, percorso = tempfile.mkstemp(suffix=".pdf")
    os.close(descrittore)
    misure = {"leftMargin": 25 * mm, "rightMargin": 25 * mm,
              "topMargin": 25 * mm, "bottomMargin": 25 * mm}
    misure.update(margini)
    SimpleDocTemplate(percorso, pagesize=A4, **misure).build(flow)
    return Path(percorso)


def _giro(sorgente: Path) -> Path:
    documento = converti_file(str(sorgente))
    html = "".join(pagina.html for pagina in documento.pagine)
    arrivo = sorgente.with_name(sorgente.stem + "-ritorno.pdf")
    arrivo.write_bytes(html_to_pdf(html, sorgente.stem))
    return arrivo


def _misure(sorgente: Path) -> str:
    documento = converti_file(str(sorgente))
    return "".join(pagina.html for pagina in documento.pagine)


# ---------------------------------------------------------------- le misure

def test_la_pagina_dichiara_le_proprie_misure():
    atto = _atto([Paragraph(PERIODO * 6, _corpo())])
    try:
        misure = misure_del_documento(_misure(atto))
    finally:
        atto.unlink(missing_ok=True)

    assert misure, "la pagina non ha portato con se' nessuna misura"
    assert 20 <= misure["margin_top_mm"] <= 30
    assert 20 <= misure["margin_left_mm"] <= 30
    assert misure["paragraph_spacing_pt"] == 0, (
        "l'interlinea e' gia' dichiarata: lo stacco fra paragrafi la raddoppierebbe"
    )


def test_ogni_pagina_porta_le_sue_misure_non_quelle_della_prima():
    """La prima pagina ha la carta intestata e comincia piu' in alto."""
    atto = _atto(
        [Paragraph(PERIODO * 4, _corpo()), PageBreak(), Paragraph(PERIODO * 4, _corpo())],
        topMargin=12 * mm,
    )
    try:
        pagine = misure_delle_pagine(_misure(atto))
    finally:
        atto.unlink(missing_ok=True)

    assert len(pagine) == 2, "le pagine non sono state contate una per una"
    for misure in pagine:
        assert misure["larghezza"] > 0 and misure["altezza"] > 0
        assert misure["corpo"] > 0 and misure["interlinea"] > 0


# ---------------------------------------------------------------- il giro

def test_un_atto_di_due_pagine_torna_di_due_pagine():
    atto = _atto([
        Paragraph("TRIBUNALE DI PALMI", _titolo()),
        Paragraph(PERIODO * 9, _corpo()),
        PageBreak(),
        Paragraph(PERIODO * 9, _corpo()),
    ])
    ritorno = None
    try:
        ritorno = _giro(atto)
        with pdfplumber.open(str(atto)) as pdf:
            prima = len(pdf.pages)
        with pdfplumber.open(str(ritorno)) as pdf:
            dopo = len(pdf.pages)
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    assert dopo == prima, f"l'atto era di {prima} pagine ed e' tornato di {dopo}"


def test_le_parole_restano_dove_erano():
    atto = _atto([
        Paragraph("TRIBUNALE DI PALMI", _titolo()),
        Paragraph(PERIODO * 8, _corpo()),
    ])
    ritorno = None
    try:
        ritorno = _giro(atto)
        esito = confronta(atto, ritorno)
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    assert esito.parole_perse_totali == 0, (
        f"{esito.parole_perse_totali} parole non si ritrovano: {esito.sommario()}"
    )
    assert esito.entro_tolleranza >= 80.0, (
        f"il documento si e' spostato: {esito.sommario()}"
    )


def test_la_prima_riga_resta_sul_margine():
    """Reportlab la farebbe scendere di nove punti, e con lei tutta la pagina."""
    atto = _atto([Paragraph(PERIODO * 6, _corpo())])
    ritorno = None
    try:
        ritorno = _giro(atto)
        with pdfplumber.open(str(atto)) as pdf:
            alto_prima = min(p["top"] for p in pdf.pages[0].extract_words())
        with pdfplumber.open(str(ritorno)) as pdf:
            alto_dopo = min(p["top"] for p in pdf.pages[0].extract_words())
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    assert abs(alto_dopo - alto_prima) < 2.9, (
        f"la prima riga e' passata da {alto_prima:.1f} a {alto_dopo:.1f} punti"
    )


def test_le_righe_giustificate_arrivano_al_margine_destro():
    """Ogni andata a capo e' gia' segnata: la riga prima era piena."""
    atto = _atto([Paragraph(PERIODO * 8, _corpo())])
    ritorno = None
    try:
        ritorno = _giro(atto)
        with pdfplumber.open(str(atto)) as pdf:
            destro_prima = max(p["x1"] for p in pdf.pages[0].extract_words())
        with pdfplumber.open(str(ritorno)) as pdf:
            destro_dopo = max(p["x1"] for p in pdf.pages[0].extract_words())
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    assert abs(destro_dopo - destro_prima) < 2.9, (
        f"il margine destro e' passato da {destro_prima:.1f} a {destro_dopo:.1f} punti"
    )


# ---------------------------------------------------------------- la testata

def _intestato(nome: str = "carta") -> Path:
    """Un atto di due pagine con la stessa carta intestata in cima a tutte e due."""
    descrittore, percorso = tempfile.mkstemp(suffix=".pdf")
    os.close(descrittore)
    stretto = ParagraphStyle(
        "carta", parent=getSampleStyleSheet()["Normal"], alignment=TA_CENTER,
        fontName="Times-Bold", fontSize=11, leading=12, spaceAfter=0,
    )
    testata = [
        Paragraph("STUDIO LEGALE ROSSI", stretto),
        Paragraph("Via Roma 1 - 70121 Bari", stretto),
        Paragraph("PEC: studio@pec.it", stretto),
    ]
    flow = testata + [Paragraph(PERIODO * 7, _corpo())]
    flow += [PageBreak()] + testata + [Paragraph(PERIODO * 7, _corpo())]
    SimpleDocTemplate(percorso, pagesize=A4,
                      leftMargin=25 * mm, rightMargin=25 * mm,
                      topMargin=15 * mm, bottomMargin=20 * mm).build(flow)
    return Path(percorso)


def test_la_carta_intestata_non_allunga_la_pagina():
    """Resa a mano, centrata e senza misure, occupava il doppio dell'altezza.

    Su una citazione di sedici pagine erano trentotto punti di scarto: la
    testata spingeva giu' il corpo e da li' in fondo non c'era piu' una riga
    al suo posto.
    """
    atto = _intestato()
    ritorno = None
    try:
        ritorno = _giro(atto)
        with pdfplumber.open(str(atto)) as pdf:
            righe_prima = sorted({round(p["top"], 1) for p in pdf.pages[0].extract_words()})
        with pdfplumber.open(str(ritorno)) as pdf:
            pagine_dopo = len(pdf.pages)
            righe_dopo = sorted({round(p["top"], 1) for p in pdf.pages[0].extract_words()})
        esito = confronta(atto, ritorno)
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    assert pagine_dopo == 2, f"l'atto era di due pagine ed e' tornato di {pagine_dopo}"
    assert esito.parole_perse_totali == 0, esito.sommario()
    # la prima riga del corpo, quella subito sotto la testata
    corpo_prima = righe_prima[3]
    corpo_dopo = righe_dopo[3]
    assert abs(corpo_dopo - corpo_prima) < 2.9, (
        f"sotto la testata il corpo e' passato da {corpo_prima:.1f} a {corpo_dopo:.1f} punti"
    )


def test_la_riga_piena_resta_piena_anche_se_e_l_ultima():
    """Una riga che arrivava al margine destro era giustificata.

    Se il capoverso ne ha una sola — un capitolo di prova, una voce di elenco —
    chi riscrive il PDF la tratta come riga di chiusura e la lascia corta: le
    parole si stringono a sinistra e l'ultima finisce a due centimetri da dove
    stava, anche se la riga e' al suo posto in verticale.
    """
    atto = _atto([
        Paragraph(PERIODO * 2, _corpo()),
        Paragraph(PERIODO * 2, _corpo()),
        Paragraph(PERIODO * 2, _corpo()),
    ])
    ritorno = None
    try:
        ritorno = _giro(atto)
        with pdfplumber.open(str(atto)) as pdf:
            prima = pdf.pages[0].extract_words()
        with pdfplumber.open(str(ritorno)) as pdf:
            dopo = pdf.pages[0].extract_words()
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    # il bordo destro delle righe piene: nell'originale finiscono tutte li'
    def _bordi(parole):
        per_riga: dict[float, float] = {}
        for p in parole:
            chiave = round(p["top"], 0)
            per_riga[chiave] = max(per_riga.get(chiave, 0.0), p["x1"])
        return per_riga

    bordi_prima, bordi_dopo = _bordi(prima), _bordi(dopo)
    destro = max(bordi_prima.values())
    piene = [y for y, x1 in bordi_prima.items() if destro - x1 < 1.5]
    assert len(piene) >= 3, "l'atto di prova non ha righe piene da confrontare"

    scostate = [
        y for y in piene
        if y in bordi_dopo and abs(bordi_dopo[y] - bordi_prima[y]) > 2.9
    ]
    assert not scostate, (
        f"{len(scostate)} righe piene su {len(piene)} sono tornate corte"
    )


def test_il_numero_di_pagina_resta_in_fondo_al_foglio():
    """Nel flusso non ci starebbe: sotto l'ultima riga resta fermo un interlinea.

    Un piede che nell'originale sfiora il bordo del foglio, messo in fila col
    testo, scivola alla pagina dopo e si porta dietro tutto il resto: un atto
    di sei pagine ne faceva undici. Si disegna dov'era.
    """
    descrittore, percorso = tempfile.mkstemp(suffix=".pdf")
    os.close(descrittore)

    def _numero(tela, documento):
        tela.setFont("Times-Roman", 10)
        tela.drawCentredString(A4[0] / 2, 18, str(documento.page))

    SimpleDocTemplate(
        percorso, pagesize=A4,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    ).build(
        [Paragraph(PERIODO * 7, _corpo()), PageBreak(),
         Paragraph(PERIODO * 7, _corpo())],
        onFirstPage=_numero, onLaterPages=_numero,
    )
    atto = Path(percorso)

    ritorno = None
    try:
        with pdfplumber.open(str(atto)) as pdf:
            assert len(pdf.pages) == 2, "l'atto di prova non e' di due pagine"
            fondo_prima = max(p["top"] for p in pdf.pages[0].extract_words())
        ritorno = _giro(atto)
        with pdfplumber.open(str(ritorno)) as pdf:
            pagine = len(pdf.pages)
            fondo_dopo = max(p["top"] for p in pdf.pages[0].extract_words())
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    assert pagine == 2, f"l'atto era di due pagine ed e' tornato di {pagine}"
    assert abs(fondo_dopo - fondo_prima) < 2.9, (
        f"il numero di pagina e' passato da {fondo_prima:.1f} a {fondo_dopo:.1f} punti"
    )
