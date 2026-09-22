"""Il lettore che prende il posto di quello di PyMuPDF.

Questi test lavorano su un PDF costruito qui, con dentro le cose che
l'importazione fedele deve riconoscere: grassetto, corsivo, colore,
sottolineatura, barratura, evidenziatura, collegamento, apice e una tabella
bordata. Se una di queste si perde, l'atto importato va riscritto a mano.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber
import pytest
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from pct.documento_fedele.sorgente import (
    CORSIVO,
    GRASSETTO,
    DocumentoSorgente,
    SorgenteError,
)

URL = "https://www.iusentra.it"


@pytest.fixture
def documento(tmp_path) -> Path:
    percorso = tmp_path / "prova.pdf"
    foglio = canvas.Canvas(str(percorso), pagesize=A4)

    # evidenziatura gialla dietro il titolo
    foglio.setFillColorRGB(1, 0.92, 0.35)
    foglio.rect(25 * mm, 246 * mm, 60 * mm, 6 * mm, stroke=0, fill=1)

    foglio.setFillColorRGB(0, 0, 0)
    foglio.setFont("Helvetica-Bold", 13)
    foglio.drawString(25 * mm, 247.5 * mm, "TITOLO IN GRASSETTO")

    foglio.setFont("Helvetica-Oblique", 11)
    foglio.drawString(25 * mm, 238 * mm, "una riga in corsivo")

    foglio.setFont("Helvetica", 11)
    foglio.drawString(25 * mm, 230 * mm, "testo sottolineato")
    larghezza = foglio.stringWidth("testo sottolineato", "Helvetica", 11)
    foglio.setLineWidth(0.6)
    foglio.line(25 * mm, 228.6 * mm, 25 * mm + larghezza, 228.6 * mm)

    foglio.drawString(25 * mm, 222 * mm, "testo barrato")
    larga = foglio.stringWidth("testo barrato", "Helvetica", 11)
    foglio.line(25 * mm, 223.2 * mm, 25 * mm + larga, 223.2 * mm)

    foglio.setFillColorRGB(0.1, 0.2, 0.8)
    foglio.drawString(25 * mm, 214 * mm, "www.iusentra.it")
    quanto = foglio.stringWidth("www.iusentra.it", "Helvetica", 11)
    foglio.linkURL(URL, (25 * mm, 213 * mm, 25 * mm + quanto, 218 * mm), relative=0)

    foglio.setFillColorRGB(0.75, 0.1, 0.1)
    foglio.drawString(25 * mm, 206 * mm, "riga in rosso")

    foglio.setFillColorRGB(0, 0, 0)
    foglio.setFont("Helvetica", 10)
    y = 180 * mm
    for riga in range(3):
        for colonna, x in enumerate([25 * mm, 70 * mm, 115 * mm]):
            foglio.rect(x, y - riga * 8 * mm, 45 * mm, 8 * mm, stroke=1, fill=0)
            foglio.drawString(x + 2 * mm, y - riga * 8 * mm + 2.5 * mm,
                              f"cella {riga + 1}.{colonna + 1}")

    foglio.showPage()
    foglio.save()
    return percorso


def _span(documento_aperto):
    return [s for r in documento_aperto.pagine[0].righe_grezze() for s in r["spans"]]


def test_le_misure_della_pagina_sono_quelle_del_pdf(documento):
    with DocumentoSorgente(documento) as aperto:
        pagina = aperto.pagine[0]
        assert len(aperto) == 1
        assert pagina.numero == 1
        assert round(pagina.larghezza) == 595
        assert round(pagina.altezza) == 842
        assert pagina.rotazione == 0
        assert pagina.riquadro.get_area() > 0


def test_il_testo_ricostruito_e_quello_che_legge_pdfplumber(documento):
    """Gli spazi nei PDF non sono lettere: se si sbaglia soglia escono attaccati."""
    with DocumentoSorgente(documento) as aperto:
        nostro = ["".join(s["text"] for s in r["spans"])
                  for r in aperto.pagine[0].righe_grezze()]
    with pdfplumber.open(str(documento)) as pdf:
        loro = [r["text"] for r in pdf.pages[0].extract_text_lines()]
    assert nostro == loro
    assert "TITOLO IN GRASSETTO" in nostro
    assert "cella 1.1 cella 1.2 cella 1.3" in nostro


def test_il_collegamento_arriva_con_il_suo_riquadro(documento):
    with DocumentoSorgente(documento) as aperto:
        collegamenti = aperto.pagine[0].collegamenti
    assert len(collegamenti) == 1
    riquadro, indirizzo = collegamenti[0]
    assert indirizzo == URL
    assert riquadro.width > 10 and riquadro.height > 2


def test_la_sottolineatura_e_la_barratura_sono_due_filetti(documento):
    with DocumentoSorgente(documento) as aperto:
        filetti = aperto.pagine[0].filetti
    assert len(filetti) == 2
    for x0, x1, _y in filetti:
        assert x1 - x0 > 5


def test_le_celle_bordate_non_diventano_filetti(documento):
    """Il bordo di una cella alta non e' una sottolineatura."""
    with DocumentoSorgente(documento) as aperto:
        pagina = aperto.pagine[0]
        assert len(pagina.filetti) == 2  # solo le due linee vere
        assert len([r for r in pagina.rettangoli if r.get("stroke")]) == 9


def test_l_evidenziatura_gialla_viene_vista_e_il_bianco_no(documento):
    with DocumentoSorgente(documento) as aperto:
        evidenziature = aperto.pagine[0].evidenziature
    assert len(evidenziature) == 1
    riquadro, colore = evidenziature[0]
    assert colore == "#ffea59"
    assert riquadro.width > 100


def test_grassetto_e_corsivo_arrivano_nei_flag(documento):
    with DocumentoSorgente(documento) as aperto:
        span = _span(aperto)
    titolo = next(s for s in span if s["text"].startswith("TITOLO"))
    corsivo = next(s for s in span if "corsivo" in s["text"])
    diritto = next(s for s in span if s["text"].startswith("testo sottolineato"))
    assert titolo["flags"] & GRASSETTO
    assert corsivo["flags"] & CORSIVO
    assert not diritto["flags"] & GRASSETTO
    assert not diritto["flags"] & CORSIVO


def test_il_colore_del_testo_arriva_come_intero(documento):
    with DocumentoSorgente(documento) as aperto:
        span = _span(aperto)
    rosso = next(s for s in span if "rosso" in s["text"])
    nero = next(s for s in span if s["text"].startswith("testo barrato"))
    assert rosso["color"] == 0xBF1919
    assert nero["color"] == 0x000000


def test_ogni_span_porta_i_suoi_caratteri_con_il_riquadro(documento):
    with DocumentoSorgente(documento) as aperto:
        span = _span(aperto)
    uno = next(s for s in span if s["text"].startswith("riga in rosso"))
    assert "".join(c["c"] for c in uno["chars"]) == uno["text"]
    for carattere in uno["chars"]:
        x0, y0, x1, y1 = carattere["bbox"]
        assert x1 >= x0 and y1 > y0


def test_il_corpo_dichiarato_e_quello_scritto_nel_pdf(documento):
    with DocumentoSorgente(documento) as aperto:
        span = _span(aperto)
    titolo = next(s for s in span if s["text"].startswith("TITOLO"))
    cella = next(s for s in span if s["text"].startswith("cella"))
    assert titolo["size"] == 13.0
    assert cella["size"] == 10.0


def test_la_pagina_si_puo_disegnare_intera_e_a_ritaglio(documento):
    from pct.documento_fedele.geometria import Riquadro

    with DocumentoSorgente(documento) as aperto:
        pagina = aperto.pagine[0]
        intera = pagina.png(dpi=72)
        pezzo = pagina.png(dpi=72, ritaglio=Riquadro(50, 100, 250, 200))
    assert intera.startswith(b"\x89PNG")
    assert pezzo.startswith(b"\x89PNG")
    assert len(pezzo) < len(intera)


def test_una_pagina_orizzontale_dichiara_le_sue_misure(tmp_path):
    percorso = tmp_path / "orizzontale.pdf"
    foglio = canvas.Canvas(str(percorso), pagesize=landscape(A4))
    foglio.setFont("Helvetica", 12)
    foglio.drawString(30 * mm, 100 * mm, "pagina orizzontale")
    foglio.showPage()
    foglio.save()
    with DocumentoSorgente(percorso) as aperto:
        pagina = aperto.pagine[0]
    assert pagina.larghezza > pagina.altezza


def test_un_file_che_non_e_un_pdf_viene_rifiutato(tmp_path):
    finto = tmp_path / "finto.pdf"
    finto.write_bytes(b"non sono un PDF")
    with pytest.raises(SorgenteError, match="illeggibile"):
        DocumentoSorgente(finto)


def test_si_puo_aprire_anche_dai_byte(documento):
    with DocumentoSorgente(documento.read_bytes()) as aperto:
        assert len(aperto) == 1
        assert aperto.pagine[0].righe_grezze()
