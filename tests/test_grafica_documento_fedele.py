"""I timbri e le firme disegnati a vettori non devono sparire.

`estrai_grafica` raggruppa i tracciati vicini e rasterizza la zona: e' il
codice che tiene in piedi l'intestazione dello studio, il timbro di deposito e
la firma grafica su un atto. Non aveva test suoi, e la sostituzione della
geometria aveva rotto proprio il raggruppamento senza che nulla lo dicesse.
"""

from __future__ import annotations

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from pct.documento_fedele.geometria import Riquadro
from pct.documento_fedele.immagini import estrai_grafica
from pct.documento_fedele.sorgente import DocumentoSorgente


@pytest.fixture
def con_timbro(tmp_path):
    """Un atto con un timbro fatto di tanti tracciati staccati."""
    percorso = tmp_path / "timbro.pdf"
    foglio = canvas.Canvas(str(percorso), pagesize=A4)

    foglio.setFont("Helvetica", 11)
    foglio.drawString(25 * mm, 250 * mm, "atto con timbro")

    # il timbro: cornice piu' una decina di segni dentro, tutti vicini
    foglio.setStrokeColorRGB(0.7, 0.1, 0.1)
    foglio.setLineWidth(1.4)
    foglio.roundRect(120 * mm, 200 * mm, 50 * mm, 18 * mm, 3 * mm, stroke=1, fill=0)
    for n in range(10):
        x = 124 * mm + n * 4 * mm
        foglio.line(x, 205 * mm, x + 3 * mm, 213 * mm)

    foglio.showPage()
    foglio.save()
    return percorso


def test_i_tracciati_vicini_diventano_una_sola_grafica(con_timbro):
    with DocumentoSorgente(con_timbro) as aperto:
        elementi = estrai_grafica(aperto.pagine[0], [])

    assert elementi, "il timbro e' sparito"
    assert len(elementi) == 1, (
        f"il timbro e' stato spezzato in {len(elementi)} pezzi invece di restare uno"
    )

    uno = elementi[0]
    assert uno.tipo == "grafica"
    assert 'src="data:image/' in uno.html
    riquadro = Riquadro(uno.bbox)
    assert riquadro.width > 40 * mm * 0.8
    assert riquadro.height > 15 * mm * 0.8


def test_una_zona_gia_occupata_non_viene_rasterizzata_due_volte(con_timbro):
    """Quello che e' gia' diventato tabella o immagine resta fuori."""
    with DocumentoSorgente(con_timbro) as aperto:
        pagina = aperto.pagine[0]
        tutto = estrai_grafica(pagina, [])
        occupato = Riquadro(tutto[0].bbox)
        niente = estrai_grafica(pagina, [occupato])

    assert tutto
    assert niente == []


def test_la_cornice_di_un_campo_modulo_non_diventa_grafica(tmp_path):
    """La scritta dentro un campo e' gia' letta come testo: rasterizzarla
    raddoppierebbe ogni etichetta."""
    from reportlab.lib.colors import black

    percorso = tmp_path / "modulo.pdf"
    foglio = canvas.Canvas(str(percorso), pagesize=A4)
    foglio.setFont("Helvetica", 11)
    foglio.drawString(25 * mm, 250 * mm, "Nome dell'istante:")
    foglio.acroForm.textfield(
        name="nome", x=80 * mm, y=246 * mm, width=80 * mm, height=8 * mm,
        borderColor=black, forceBorder=True,
    )
    foglio.showPage()
    foglio.save()

    with DocumentoSorgente(percorso) as aperto:
        pagina = aperto.pagine[0]
        campi = pagina.campi_modulo
        elementi = estrai_grafica(pagina, [])

    assert campi, "il campo modulo non e' stato riconosciuto"
    assert elementi == [], "la cornice del campo e' finita nella grafica"


@pytest.fixture
def carta_intestata(tmp_path):
    """Una carta intestata: un riquadro disegnato, e dentro il nome dello studio."""
    percorso = tmp_path / "intestata.pdf"
    foglio = canvas.Canvas(str(percorso), pagesize=A4)

    foglio.setLineWidth(0.8)
    foglio.rect(25 * mm, 250 * mm, 90 * mm, 28 * mm, stroke=1, fill=0)
    foglio.setFont("Helvetica-Bold", 11)
    foglio.drawString(30 * mm, 270 * mm, "STUDIO LEGALE MONTAGNESE")
    foglio.setFont("Helvetica", 9)
    foglio.drawString(30 * mm, 264 * mm, "Avvocato Roberto Montagnese")
    foglio.drawString(30 * mm, 258 * mm, "Via N. Bixio, 4 - Taurianova")

    foglio.setFont("Helvetica", 11)
    foglio.drawString(25 * mm, 200 * mm, "corpo dell'atto")
    foglio.showPage()
    foglio.save()
    return percorso


def test_il_riquadro_che_contiene_testo_non_si_rasterizza(carta_intestata):
    """Altrimenti l'intestazione esce due volte, una sopra l'altra.

    La cornice della carta intestata e' un disegno, ma dentro ci sta il nome
    dello studio, che viene gia' scritto come testo. Rasterizzando anche quella
    le lettere uscivano sdoppiate. Si perde il filetto e si tiene il testo: il
    testo l'avvocato lo modifica, il filetto no.
    """
    from pct.documento_fedele.lettura import leggi_righe

    with DocumentoSorgente(carta_intestata) as documento:
        pagina = documento[0]
        righe = leggi_righe(pagina)
        con_testo = estrai_grafica(pagina, [], righe=righe)
        senza_testo = estrai_grafica(pagina, [])

    assert senza_testo, "la prova non regge: senza le righe il riquadro c'era"
    assert not con_testo, "il riquadro dell'intestazione e' stato rasterizzato lo stesso"


def test_un_timbro_che_non_contiene_testo_resta(con_timbro):
    """La regola non deve mangiarsi i timbri: quelli stanno nel bianco."""
    from pct.documento_fedele.lettura import leggi_righe

    with DocumentoSorgente(con_timbro) as documento:
        pagina = documento[0]
        righe = leggi_righe(pagina)
        trovati = estrai_grafica(pagina, [], righe=righe)

    assert trovati, "il timbro e' sparito"
