"""Le tabelle in due forme (testo e struttura) e i prospetti con la prova dei conti."""

from __future__ import annotations

import io
import json

import pytest

from legal_ocr import tabelle as T
from pct.archivio_letture.estrazione_tabelle import CAMPO, fatti_prospetti, prospetto

NOTA_SPESE = [
    ["Voce", "Importo"],
    ["Fase di studio", "€ 1.215,00"],
    ["Fase introduttiva", "€ 777,00"],
    ["Fase istruttoria", "€ 1.680,00"],
    ["Fase decisionale", "€ 2.025,00"],
    ["Totale compensi", "€ 5.697,00"],
    ["Spese generali 15%", "€ 854,55"],
    ["Cassa avvocati 4%", "€ 262,06"],
    ["Totale", "€ 6.813,61"],
]


def _pdf(*, griglia: bool = True, prosa: bool = False) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    stili = getSampleStyleSheet()
    elementi = [Paragraph("NOTA SPESE - causa Ferraro / Edilnova - R.G. 1234/2025", stili["Title"])]
    if prosa:
        elementi += [Paragraph(
            "Il Tribunale, letti gli atti del 12/03/2026 e del 14/04/2026, condanna al pagamento di € 1.200,00; "
            "considerato che il 20/05/2026 le parti hanno depositato note e che il valore è di € 25.000,00, rinvia.",
            stili["Normal"]) for _ in range(5)]
    else:
        tabella = Table(NOTA_SPESE, colWidths=[250, 120])
        if griglia:
            tabella.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
        elementi += [Spacer(1, 12), tabella]
    SimpleDocTemplate(buffer, pagesize=A4).build(elementi)
    return buffer.getvalue()


def test_blocco_e_struttura_si_ricostruiscono_identici():
    tabella = T.Tabella(2, T.pulisci(NOTA_SPESE))
    testo = T.con_blocchi("Testo della pagina.", [tabella], primo=3)
    assert testo.startswith("Testo della pagina.")
    assert "[TABELLA 3 · pagina 2 · 9 righe × 2 colonne" in testo
    letta = T.leggi_blocchi(testo)
    assert [t.righe for t in letta] == [tabella.righe] and letta[0].pagina == 2
    assert T.senza_blocchi(testo) == "Testo della pagina."


def test_indice_documentale_conserva_testo_e_tabella():
    from pct.document_intelligence.extraction import _extract_pdf

    esito = _extract_pdf(_pdf(griglia=True))
    assert esito.ok
    tabelle = T.leggi_blocchi(esito.text)
    assert len(tabelle) == 1 and tabelle[0].righe[1] == ("Fase di studio", "€ 1.215,00")
    # Il testo dell'autore resta prima del blocco.
    assert esito.text.index("Fase di studio") < esito.text.index("[TABELLA")


def test_motore_di_lettura_unico_porta_le_tabelle_della_pagina():
    from legal_ocr.motore.testo import testo_da_pdf

    pagine = testo_da_pdf(_pdf(griglia=True))
    assert pagine[0].tabelle and pagine[0].tabelle[0].righe[-1] == ("Totale", "€ 6.813,61")
    assert "[TABELLA 1" in pagine[0].testo_con_tabelle() and "[TABELLA" not in pagine[0].testo


def test_pagina_di_prosa_non_produce_tabelle():
    from pct.document_intelligence.extraction import _extract_pdf

    esito = _extract_pdf(_pdf(prosa=True))
    assert "[TABELLA" not in esito.text
    assert T.prospetti_dal_testo(esito.text) == []


def test_tabella_senza_linee_si_legge_come_prospetto():
    from pct.document_intelligence.extraction import _extract_pdf

    esito = _extract_pdf(_pdf(griglia=False))
    tabelle = T.tabelle_del_testo(esito.text)
    assert len(tabelle) == 1 and tabelle[0].origine == T.ORIGINE_PROSPETTO
    assert ("Spese generali 15%", "€ 854,55") in tabelle[0].righe


def test_i_conti_del_prospetto_tornano():
    letto = prospetto(T.Tabella(1, T.pulisci(NOTA_SPESE)))
    assert letto["somma"] == "ok" and f"{letto['totale']:.2f}" == "6813.61"
    assert letto["norma"].startswith("D.M. 55/2014")


def test_ritenuta_e_imponibile_iva():
    righe = [["Compenso professionale", "2.000,00"], ["Spese generali 15%", "300,00"], ["CPA 4%", "92,00"],
             ["Imponibile IVA", "2.392,00"], ["IVA 22%", "526,24"], ["Totale", "2.918,24"],
             ["Ritenuta d'acconto 20%", "-460,00"], ["Netto a pagare", "2.458,24"]]
    assert prospetto(T.Tabella(1, T.pulisci(righe)))["somma"] == "ok"


def test_conti_che_non_tornano_restano_da_verificare():
    from pct.archivio_letture.collaudo import Contesto, collauda

    righe = [["onorario", "1.850,00"], ["maggiorazione 20%", "370,00"], ["spese documentate", "214,60"], ["totale", "2.534,60"]]
    testo = "\n".join(f"{voce} {importo}" for voce, importo in righe)
    fatti = fatti_prospetti(testo, origine="nativo")
    assert len(fatti) == 1 and fatti[0].campo == CAMPO
    somma = next(p for p in fatti[0].prove if p["codice"] == "somma")
    assert somma["esito"] == "errore" and "€ 2.434,60" in somma["dettaglio"]
    assert collauda(fatti[0], Contesto()).verifica == "plausibile"


def test_il_motore_documenti_legge_i_prospetti_e_il_presidio_li_mostra():
    from pct.archivio_letture.collaudo import Contesto
    from pct.archivio_letture.motore_documenti import VERSIONE_MOTORE_DOCUMENTI, leggi_testo
    from pct.archivio_letture.presidi import prospetti_letti

    assert "v16+tabelle" in VERSIONE_MOTORE_DOCUMENTI
    testo = "NOTA SPESE\n" + "\n".join(f"{voce} {importo}" for voce, importo in NOTA_SPESE[1:])
    fatti = leggi_testo(testo, origine="nativo", contesto=Contesto(), nome="nota_spese.pdf")
    vista = prospetti_letti(fatti)
    assert len(vista) == 1 and vista[0]["somma"] == "ok" and vista[0]["totale"] == "6813.61"
    assert vista[0]["righe"][0] == {"voce": "Fase di studio", "importo": "1215.00", "totale": False}


@pytest.mark.parametrize("testo", [
    "Il giudice rinvia all'udienza del 12/03/2027 e assegna termine fino al 01/02/2027.",
    "Visto il D.M. 55/2014 e l'art. 91 c.p.c., liquida € 1.200,00 oltre accessori.",
])
def test_prosa_con_pochi_numeri_non_e_un_prospetto(testo):
    assert fatti_prospetti(testo, origine="nativo") == []


def test_prova_della_tabella_serializzata():
    fatti = fatti_prospetti("\n".join(f"{v} {i}" for v, i in NOTA_SPESE[1:]), origine="ocr")
    dati = json.loads(next(p for p in fatti[0].prove if p["codice"] == "tabella")["dettaglio"])
    assert dati["origine"] == T.ORIGINE_PROSPETTO and len(dati["righe"]) == 8
