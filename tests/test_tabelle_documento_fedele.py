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


# ===========================================================================
# Righe spezzate in colonne
# ===========================================================================

def _riga_finta(testo: str, x0: float, y0: float, larga: float, corpo: float = 10.0):
    """Una riga con l'ingombro che avrebbe sulla pagina."""
    from pct.documento_fedele.modello import Riga, Tratto
    return Riga(
        tratti=[Tratto(testo=testo, famiglia="Times New Roman", corpo=corpo)],
        bbox=(x0, y0, x0 + larga, y0 + corpo * 1.2),
    )


def test_le_celle_di_una_riga_restano_una_riga_sola():
    """Tre celle affiancate sono una fila, non tre righe una sotto l'altra."""
    from pct.documento_fedele.paragrafi import _file_affiancate

    gruppi = _file_affiancate([
        _riga_finta("Tipologia", 54, 300, 90),
        _riga_finta("Importo", 200, 300.4, 50),
        _riga_finta("Codice", 300, 299.8, 45),
        _riga_finta("Totale a pagare", 54, 320, 110),
    ])

    assert [len(g) for g in gruppi] == [3, 1], (
        "le tre celle della prima riga dovevano stare insieme"
    )
    assert [r.testo for r in gruppi[0]] == ["Tipologia", "Importo", "Codice"]


def test_una_sigla_schiacciata_non_fa_una_fila():
    """Trentadue lettere in sette punti non sono una colonna.

    Certi PDF firmano la pagina con un codice disegnato in un centimetro di
    riga. Messo in una cella larga quanto occupava, va a capo otto volte: una
    pagina ne diventa tre. Quel pezzo non deve entrare in una fila.
    """
    from pct.documento_fedele.paragrafi import _file_affiancate, _testo_compresso

    sigla = _riga_finta("c0b6b422ef54d05e131ff4bdf5f631b7", 500, 300, 7.0, corpo=3.7)
    assert _testo_compresso(sigla)
    assert not _testo_compresso(_riga_finta("Il procedimento r.g.n. 387/2023", 54, 300, 150, corpo=14))

    gruppi = _file_affiancate([
        _riga_finta("Il procedimento r.g.n. 387/2023", 54, 300, 280, corpo=14),
        sigla,
    ])
    assert [len(g) for g in gruppi] == [1, 1], (
        "con un pezzo schiacciato la fila non si fa: si torna ai paragrafi"
    )


def test_la_fila_dichiara_le_colonne_dove_stavano():
    """Ogni cella va dal suo inizio all'inizio di quella dopo."""
    import re

    from pct.documento_fedele.paragrafi import _fila_affiancata

    gruppo = [
        _riga_finta("Tipologia", 154, 300, 90),
        _riga_finta("Importo", 254, 300, 50),
        _riga_finta("Codice", 354, 300, 45),
    ]
    elemento = _fila_affiancata(
        gruppo, sinistra=54.0, destra=554.0, successivo=_riga_finta("dopo", 54, 313, 40),
        interlinea=12.0, corpo_base=10.0, famiglia_base="Times New Roman",
    )

    assert elemento.tipo == "tabella"
    assert 'data-fila="1"' in elemento.html
    assert 'data-bordi="0"' in elemento.html, "una fila non ha filetti da disegnare"
    assert elemento.html.count("<tr>") == 1, "la fila e' una riga sola"

    quote = [float(q) for q in
             re.findall(r'<td style="width:([0-9.]+)%', elemento.html)]
    # colonna larga 500: vuoto 100, poi 100, 100, 200
    assert quote[0] == 20.0, "il vuoto prima della prima cella"
    assert quote[1:] == [20.0, 20.0, 40.0]
    assert abs(sum(quote) - 100.0) < 0.5

    # l'altezza della riga e' il passo fino alla riga dopo, non l'interlinea
    assert "line-height:13pt" in elemento.html
