"""Esportazione della bozza in Word (.docx) con python-docx.

Base normativa: art. 20 D.Lgs. 82/2005 (documento informatico sottoscrivibile
con firma digitale). La nota per l'avvocato si esporta solo su richiesta, in
un documento separato, per non confonderla con il testo contrattuale.
"""

from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

_ROSSO = RGBColor(0xB4, 0x23, 0x18)


def _paragrafo_con_segnaposti(doc, testo: str) -> None:
    paragrafo = doc.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    resto = testo
    while "[" in resto and "]" in resto[resto.index("["):]:
        inizio = resto.index("[")
        fine = resto.index("]", inizio) + 1
        paragrafo.add_run(resto[:inizio])
        evidenza = paragrafo.add_run(resto[inizio:fine])
        evidenza.bold = True
        evidenza.font.color.rgb = _ROSSO
        resto = resto[fine:]
    paragrafo.add_run(resto)


def bozza_docx(bozza: dict) -> bytes:
    doc = Document()
    stile = doc.styles["Normal"]
    stile.font.name = "Times New Roman"
    stile.font.size = Pt(12)

    titolo = doc.add_paragraph()
    titolo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = titolo.add_run(bozza["titolo"])
    run.bold = True
    run.font.size = Pt(14)

    doc.add_paragraph("Tra")
    for indice, comparente in enumerate(bozza["comparenti"]):
        _paragrafo_con_segnaposti(doc, comparente["testo"] + (";" if indice == 0 else "."))
        if indice == 0:
            doc.add_paragraph("e")
    if bozza["premesse"]:
        doc.add_paragraph().add_run("Premesso che").bold = True
        for premessa in bozza["premesse"]:
            _paragrafo_con_segnaposti(doc, f"– {premessa};")
        doc.add_paragraph("tutto ciò premesso, che costituisce parte integrante del contratto, si conviene e si stipula quanto segue.")
    else:
        doc.add_paragraph("si conviene e si stipula quanto segue.")

    for articolo in bozza["articoli"]:
        intestazione = doc.add_paragraph()
        intestazione.add_run(f"Art. {articolo['numero']} – {articolo['titolo']}").bold = True
        _paragrafo_con_segnaposti(doc, articolo["testo"])

    if bozza["allegati"]:
        doc.add_paragraph().add_run("Allegati").bold = True
        for numero, allegato in enumerate(bozza["allegati"], start=1):
            doc.add_paragraph(f"{numero}. {allegato}")

    _paragrafo_con_segnaposti(doc, bozza["luogo_data"])
    tabella = doc.add_table(rows=2, cols=len(bozza["firme"]))
    for colonna, ruolo in enumerate(bozza["firme"]):
        tabella.cell(0, colonna).text = f"Il {ruolo}" if not ruolo.startswith(("Prima", "Seconda", "Primo", "Secondo")) else ruolo
        tabella.cell(1, colonna).text = "______________________"
    if bozza["approvazione_specifica"]:
        doc.add_paragraph()
        doc.add_paragraph("Per specifica approvazione ai sensi degli artt. 1341 e 1342 c.c.")
        firme = doc.add_table(rows=1, cols=len(bozza["firme"]))
        for colonna, _ruolo in enumerate(bozza["firme"]):
            firme.cell(0, colonna).text = "______________________"

    uscita = io.BytesIO()
    doc.save(uscita)
    return uscita.getvalue()


def nota_docx(bozza: dict) -> bytes:
    """Nota interna per l'avvocato: forma, bloccanti, valutazioni, adempimenti e norme."""
    nota = bozza["nota_avvocato"]
    doc = Document()
    doc.add_heading(f"Nota per l'avvocato — {bozza['titolo']}", level=1)
    doc.add_paragraph(nota["avvertenza"])
    sezioni = (("Bloccanti", nota["bloccanti"]), ("Valutazioni dell'avvocato", nota["punti_avvocato"]),
               ("Adempimenti", nota["adempimenti"]))
    doc.add_heading("Forma", level=2)
    doc.add_paragraph(nota["forma"]["forma"].replace("_", " ") + (f" — {nota['forma']['nota']}" if nota["forma"]["nota"] else ""))
    for titolo, voci in sezioni:
        doc.add_heading(titolo, level=2)
        if not voci:
            doc.add_paragraph("Nessuno.")
        for voce in voci:
            doc.add_paragraph(f"{voce['messaggio']} ({voce['norma']})" if voce.get("norma") else voce["messaggio"], style="List Bullet")
    doc.add_heading("Elementi da completare", level=2)
    for voce in bozza["da_completare"] or ["Nessuno."]:
        doc.add_paragraph(voce, style="List Bullet")
    doc.add_heading("Riferimenti normativi", level=2)
    for riferimento in nota["riferimenti"]:
        doc.add_paragraph(riferimento, style="List Bullet")
    uscita = io.BytesIO()
    doc.save(uscita)
    return uscita.getvalue()
