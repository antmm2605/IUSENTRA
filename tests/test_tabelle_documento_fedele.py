"""Quando una griglia e' una tabella e quando non lo e'.

Senza filetti disegnati, la ricerca «a testo» trova un incolonnamento
dappertutto. Su un paragrafo giustificato lungo ne inventava una di seicento
celle: e siccome le righe finite in tabella escono dai paragrafi, il testo
dell'atto spariva e l'avvocato apriva l'editor su una griglia vuota.

Questi test tengono ferme le due cose insieme: le tabelle vere devono
sopravvivere, quelle inventate no.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from pct.documento_fedele import converti_file

PERIODO = (
    "Con atto di citazione ritualmente notificato la parte attrice conveniva "
    "in giudizio la societa' convenuta, esponendo che il contratto era stato "
    "inadempiuto sotto piu' profili e chiedendo la risoluzione oltre al "
    "risarcimento del danno. "
)


def _stile(corpo: float = 11) -> ParagraphStyle:
    return ParagraphStyle(
        f"giustificato{corpo}", parent=getSampleStyleSheet()["Normal"],
        alignment=TA_JUSTIFY, fontName="Times-Roman", fontSize=corpo,
        leading=corpo * 1.36,
    )


def _html(flow) -> str:
    descrittore, percorso = tempfile.mkstemp(suffix=".pdf")
    os.close(descrittore)
    SimpleDocTemplate(
        percorso, pagesize=A4,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=25 * mm, bottomMargin=25 * mm,
    ).build(flow)
    try:
        documento = converti_file(percorso)
        return "".join(pagina.html for pagina in documento.pagine)
    finally:
        Path(percorso).unlink(missing_ok=True)


def _testo(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def test_un_atto_di_solo_testo_non_diventa_una_griglia_vuota():
    """Il difetto vero: l'atto spariva e restava una tabella di celle vuote."""
    html = _html([Paragraph(PERIODO * 12, _stile())])

    assert "<table" not in html, "un paragrafo giustificato e' stato preso per una tabella"
    testo = _testo(html)
    assert "Con atto di citazione" in testo, "il testo dell'atto non e' arrivato nell'editor"
    assert "risarcimento del danno" in testo
    assert "&nbsp;" not in html or html.count("&nbsp;") < 5


def test_un_elenco_numerato_resta_un_elenco():
    html = _html([
        Paragraph("PREMESSO CHE", _stile()),
        ListFlowable(
            [
                ListItem(Paragraph("in data 4 febbraio 2025 le parti stipulavano contratto;", _stile())),
                ListItem(Paragraph("il corrispettivo pattuito era di euro 48.500,00 oltre IVA;", _stile())),
                ListItem(Paragraph("l'opera veniva consegnata con quattro mesi di ritardo.", _stile())),
            ],
            bulletType="1",
        ),
    ])

    assert "<table" not in html, "un elenco numerato e' stato preso per una tabella"
    testo = _testo(html)
    assert "48.500,00" in testo
    assert "quattro mesi di ritardo" in testo


def test_una_tabella_con_i_filetti_resta_tabella_anche_se_ha_celle_vuote():
    """Un modulo da compilare e' fatto apposta di celle vuote."""
    modulo = Table(
        [["Nome", ""], ["Cognome", ""], ["Codice fiscale", ""]],
        colWidths=[50 * mm, 90 * mm],
        style=TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.black)]),
    )
    html = _html([modulo])

    assert "<table" in html, "il modulo bordato ha perso la griglia"
    assert html.count("<td") + html.count("<th") == 6
    assert "Codice fiscale" in _testo(html)


def test_una_tabella_senza_filetti_ma_con_le_celle_piene_resta_tabella():
    """La ricerca «a testo» serve ancora: molte tabelle negli atti non hanno bordi."""
    prospetto = Table(
        [
            ["Contributo unificato", "EUR 518,00"],
            ["Marca da bollo", "EUR 27,00"],
            ["Compenso", "EUR 2.430,00"],
            ["Spese generali", "EUR 364,50"],
        ],
        colWidths=[80 * mm, 40 * mm],
    )
    html = _html([prospetto])

    assert "<table" in html, "una tabella senza filetti e' stata buttata via"
    testo = _testo(html)
    assert "Contributo unificato" in testo and "2.430,00" in testo


def test_le_colonne_che_tagliano_una_parola_non_sono_colonne():
    """Il bordo che passa in mezzo a una parola tradisce la griglia inventata.

    Su una carta intestata seguita dall'atto la ricerca «a testo» trovava tre
    colonne e tagliava dove capitava: «Avvocato Roberto Montagnes | e». Le
    righe finite in quella griglia uscivano dai paragrafi, e il documento
    tornava di tre pagine piu' lungo.
    """
    intestazione = ParagraphStyle(
        "intestazione", parent=getSampleStyleSheet()["Normal"],
        alignment=TA_JUSTIFY, fontName="Times-Roman", fontSize=9, leading=11,
    )
    html = _html([
        Paragraph("STUDIO LEGALE MONTAGNESE", intestazione),
        Paragraph("Avvocato Roberto Montagnese", intestazione),
        Paragraph("Patrocinante in Cassazione", intestazione),
        Paragraph("Via N. Bixio, 4 - Tel e Fax 0966 - 611363", intestazione),
        Paragraph("89029 TAURIANOVA (RC)", intestazione),
        Paragraph(PERIODO * 10, _stile()),
    ])

    assert "<table" not in html, "la carta intestata e' stata presa per una tabella"
    testo = _testo(html)
    assert "Avvocato Roberto Montagnese" in testo, "una parola e' stata tagliata a meta'"
    assert "Con atto di citazione" in testo


def test_un_modulo_con_poche_parole_non_e_una_scansione():
    """Poche parole non bastano a dirlo: conta se la pagina ha tracciati.

    Una nota di iscrizione a ruolo, o un invito al pagamento del tribunale, di
    parole ne ha poche e ha la griglia disegnata. Trattandola da scansione si
    perde la griglia insieme alle caselle, e quello che torna nell'editor e' un
    elenco di frasi sciolte.

    Una scansione, invece, e' una fotografia: dentro ha un disegno solo — la
    sua immagine — e di righe e rettangoli non ne ha.
    """
    from pct.documento_fedele.conversione import _e_scansione

    # tanto testo: non e' una scansione, comunque sia fatta
    assert not _e_scansione(4000, 0)
    assert not _e_scansione(4000, 90)

    # poche parole e la griglia disegnata: e' un modulo
    assert not _e_scansione(25, 90)
    assert not _e_scansione(25, 4)

    # poche parole e nessun tracciato: e' una fotografia
    assert _e_scansione(25, 0)
    assert _e_scansione(25, 3)

    # niente testo: scansione anche col timbro vettoriale sopra
    assert _e_scansione(0, 90)
