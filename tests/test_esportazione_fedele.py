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


# ---------------------------------------------------------------- le tabelle

def test_la_tabella_tiene_le_colonne_che_aveva():
    """La resa dell'editor rifaceva ogni tabella con uno stile suo.

    Griglia grigia su tutto, quattro punti di margine dentro ogni cella,
    colonne larghe uguali. Su un modulo del tribunale — dove le colonne hanno
    larghezze decise e i bordi ci sono solo dove l'autore li ha disegnati —
    quello che tornava non era piu' quel modulo: le celle di una riga si
    incolonnavano una sotto l'altra.
    """
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    modulo = Table(
        [
            ["Tipologia Credito", "Importo", "Codice Tributo"],
            ["ANTICIPAZIONI FORFETTARIE", "27,00", "738T"],
            ["RICHIESTA D'UFFICIO", "0,00", "—"],
        ],
        colWidths=[85 * mm, 30 * mm, 35 * mm],
        style=TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.black)]),
    )
    atto = _atto([Paragraph("INVITO AL PAGAMENTO", _titolo()), modulo])

    ritorno = None
    try:
        ritorno = _giro(atto)
        with pdfplumber.open(str(atto)) as pdf:
            prima = pdf.pages[0].extract_words()
        with pdfplumber.open(str(ritorno)) as pdf:
            pagine = len(pdf.pages)
            dopo = pdf.pages[0].extract_words()
    finally:
        atto.unlink(missing_ok=True)
        if ritorno:
            ritorno.unlink(missing_ok=True)

    assert pagine == 1, f"il modulo era di una pagina ed e' tornato di {pagine}"

    def _riga_di(parole, testo):
        for p in parole:
            if p["text"] == testo:
                return round(p["top"], 0), round(p["x0"], 0)
        raise AssertionError(f"parola non trovata: {testo}")

    # le tre intestazioni stavano sulla stessa riga, e devono restarci
    y_prima = {t: _riga_di(prima, t)[0] for t in ("Tipologia", "Importo", "Codice")}
    y_dopo = {t: _riga_di(dopo, t)[0] for t in ("Tipologia", "Importo", "Codice")}
    assert len(set(y_dopo.values())) == 1, (
        f"le celle della prima riga si sono incolonnate: {y_dopo}"
    )

    # e ognuna nella sua colonna, dove stava
    for parola in ("Tipologia", "Importo", "Codice"):
        x_prima = _riga_di(prima, parola)[1]
        x_dopo = _riga_di(dopo, parola)[1]
        assert abs(x_dopo - x_prima) < 6, (
            f"«{parola}» e' passata da x={x_prima} a x={x_dopo}"
        )
    assert set(y_prima.values()) and set(y_dopo.values())


def test_la_lettura_delle_pagine_non_si_impianta_su_un_html_costruito_apposta():
    """L'HTML arriva dall'editor, quindi da chi scrive: non puo' far perno.

    Il tag di apertura si cercava con `<section[^>]*class="[^"]*iu-doc-pagina`:
    due quantificatori che si contendono gli stessi caratteri, e su un
    documento fatto di `<section` seguito da mille `class="iu-doc-pagina"` il
    motore prova tutte le divisioni possibili. Il tempo cresce col quadrato:
    un file di pochi megabyte tiene occupato il processo che deve esportare.
    Ora la classe si cerca nel tag gia' ritagliato, e il tempo torna lineare.
    """
    import time

    from pct.editor import _aperture_di_pagina

    cattivo = "<section" + 'class="iu-doc-pagina"' * 60_000
    partenza = time.perf_counter()
    trovate = _aperture_di_pagina(cattivo)
    durata = time.perf_counter() - partenza

    assert trovate == [], "un tag mai chiuso non apre nessuna pagina"
    assert durata < 1.0, (
        f"{len(cattivo)} caratteri hanno impegnato il processo per {durata:.1f}s"
    )


def test_le_pagine_si_leggono_ancora_una_per_una():
    """Il rimedio non deve costare la lettura vera: due pagine, due misure."""
    from pct.editor import _aperture_di_pagina

    html = (
        '<section class="iu-doc-pagina" data-margine-alto="28.3"'
        ' data-margine-sinistro="85" data-interlinea="18"'
        ' data-allineamento="justify" style="font-size: 12.0pt">'
        "<p>Prima</p></section>"
        '<section class="iu-doc-pagina" data-margine-alto="141.7"'
        ' data-margine-sinistro="85" data-interlinea="15"'
        ' style="font-size: 11.0pt"><p>Seconda</p></section>'
    )

    assert len(_aperture_di_pagina(html)) == 2
    # una `<section>` che non e' una pagina non deve entrare nel conto
    assert len(_aperture_di_pagina(
        '<section class="altro"><p>x</p></section>' + html
    )) == 2

    pagine = misure_delle_pagine(html)
    assert [p["alto"] for p in pagine] == [28.3, 141.7]
    assert [p["corpo"] for p in pagine] == [12.0, 11.0]
    assert [p["interlinea"] for p in pagine] == [18.0, 15.0]

    documento = misure_del_documento(html)
    assert documento["font_size_pt"] == 12.0, "il documento prende la prima pagina"


def test_ogni_pagina_misura_le_righe_sulla_propria_colonna():
    """La seconda pagina non ha per forza i margini della prima.

    Chi riscrive il PDF allarga un paragrafo finche' le righe non tornano
    quelle che aveva. Ma misurava sempre sulla colonna della **prima** pagina:
    su una pagina piu' stretta non si accorgeva che l'intestazione andava a
    capo, e quella riga in piu' spingeva giu' tutto il resto di ottanta punti.
    """
    import io
    import re

    import pdfplumber

    from pct.editor import html_to_pdf, misure_delle_pagine

    def _pagina(numero: int, sinistro: float, testo: str) -> str:
        return (
            f'<section class="iu-doc-pagina" data-pagina="{numero}"'
            f' data-larghezza="595.3" data-altezza="841.9"'
            f' data-margine-alto="40" data-margine-basso="40"'
            f' data-margine-sinistro="{sinistro}" data-margine-destro="144.4"'
            f' data-interlinea="24" data-allineamento="left"'
            f' style="font-family:\'Times New Roman\', serif;font-size:12.0pt">'
            # con questo rientro destro l'intestazione sta su una riga nella
            # colonna della prima pagina (166,5 punti per 162,6 che le
            # servono) e non ci sta in quella della seconda (159,5)
            f'<p style="text-align:center;line-height:10pt;margin-right:212pt">{testo}</p>'
            f'<p style="text-align:left;line-height:24pt">corpo della pagina {numero}</p>'
            f"</section>"
        )

    # la prima pagina e' larga, la seconda stretta: sette punti di differenza
    html = _pagina(1, 72.4, "STUDIO LEGALE POLIFRONE") + _pagina(2, 79.4, "STUDIO LEGALE POLIFRONE")

    pagine = misure_delle_pagine(html)
    assert [p["sinistro"] for p in pagine] == [72.4, 79.4], (
        "le due pagine devono restare distinte"
    )

    with pdfplumber.open(io.BytesIO(html_to_pdf(html))) as pdf:
        assert len(pdf.pages) == 2
        for numero, pagina in enumerate(pdf.pages, 1):
            righe = pagina.extract_text_lines()
            intestazione = [r for r in righe if "STUDIO" in r["text"] or "POLIFRONE" in r["text"]]
            assert len(intestazione) == 1, (
                f"pagina {numero}: l'intestazione e' andata a capo -> "
                f"{[r['text'] for r in intestazione]}"
            )
            corpo = [r for r in righe if r["text"].startswith("corpo")]
            assert corpo, f"pagina {numero}: manca il corpo"
            # il corpo sta subito sotto l'intestazione, non ottanta punti piu' giu'
            assert corpo[0]["top"] - intestazione[0]["top"] < 40, (
                f"pagina {numero}: il corpo e' scivolato a "
                f"{corpo[0]['top'] - intestazione[0]['top']:.0f} punti dall'intestazione"
            )
    assert re.search(r'data-margine-sinistro="79.4"', html)


def test_una_pagina_con_il_solo_numero_esiste_lo_stesso():
    """L'ultima pagina di un atto spesso non ha testo: solo il suo numero.

    Il piede si disegna sulla tela, non entra nel flusso. Una pagina che nel
    flusso non mette niente non veniva creata: reportlab chiudeva il documento
    sull'ultimo salto pagina, e una memoria di nove pagine ne tornava otto.
    """
    import io

    import pdfplumber

    from pct.editor import html_to_pdf

    def _pagina(numero: int, corpo: str) -> str:
        return (
            f'<section class="iu-doc-pagina" data-pagina="{numero}"'
            f' data-larghezza="595.3" data-altezza="841.9"'
            f' data-margine-alto="56.7" data-margine-basso="56.7"'
            f' data-margine-sinistro="85" data-margine-destro="56.7"'
            f' data-interlinea="18" data-allineamento="left"'
            f' style="font-family:\'Times New Roman\', serif;font-size:12.0pt">'
            f"{corpo}"
            f'<footer class="iu-doc-piede" data-alto="800">'
            f'<p style="text-align:center;line-height:12pt">{numero}</p></footer>'
            f"</section>"
        )

    # tre pagine, e l'ultima porta solo il numero
    html = (_pagina(1, "<p>Prima pagina con il suo testo.</p>")
            + _pagina(2, "<p>Seconda pagina con il suo testo.</p>")
            + _pagina(3, ""))

    with pdfplumber.open(io.BytesIO(html_to_pdf(html))) as pdf:
        assert len(pdf.pages) == 3, (
            f"le pagine erano tre e sono tornate {len(pdf.pages)}"
        )
        ultima = (pdf.pages[2].extract_text() or "").strip()
        assert ultima == "3", f"l'ultima pagina doveva portare il suo numero: {ultima!r}"
