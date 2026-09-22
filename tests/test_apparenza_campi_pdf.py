"""L'apparenza disegnata di un campo compilato, verificata sui pixel.

Il valore di un campo e il disegno di quel valore sono due cose diverse dentro
il PDF. Un campo con il valore e senza disegno si stampa vuoto in molti
lettori: per un modulo che lo studio deposita e' un difetto che si scopre
dall'altra parte. Qui non si controlla il modello, si guarda il foglio.
"""

from __future__ import annotations

import io

from pct.apparenza_campi_pdf import (
    CORPO_MASSIMO,
    CORPO_MINIMO,
    apparenza_testo,
    applica_apparenza_testo,
    corpo_carattere,
)

NOME_CAMPO = "nome_istante"


def _modulo_vuoto() -> bytes:
    import pymupdf

    documento = pymupdf.open()
    pagina = documento.new_page()
    campo = pymupdf.Widget()
    campo.field_name = NOME_CAMPO
    campo.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    campo.rect = pymupdf.Rect(72, 100, 400, 124)
    campo.field_value = ""
    pagina.add_widget(campo)
    dati = documento.tobytes()
    documento.close()
    return dati


def _inchiostro(dati: bytes) -> int:
    """Quanti pixel non bianchi ci sono sulla pagina disegnata.

    Il motore dei moduli va acceso: senza, PDFium disegna la pagina ma non il
    contenuto dei campi, e il conto tornerebbe zero anche con l'apparenza
    agganciata — cioe' il test direbbe che non funziona quando funziona.
    """
    import pypdfium2 as pdfium

    documento = pdfium.PdfDocument(dati)
    try:
        documento.init_forms()
        immagine = documento[0].render(scale=2, draw_annots=True, may_draw_forms=True).to_pil().convert("L")
        # `getdata` e' deprecata in Pillow: l'istogramma da' lo stesso conto
        # senza scorrere i pixel uno per uno.
        istogramma = immagine.histogram()
        return sum(istogramma[:200])
    finally:
        documento.close()


def _scrivi_valore(dati: bytes, testo: str, *, con_apparenza: bool) -> bytes:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, TextStringObject

    lettore = PdfReader(io.BytesIO(dati))
    scrittore = PdfWriter()
    scrittore.append(lettore)
    applicata = None
    for pagina in scrittore.pages:
        for riferimento in pagina.get("/Annots") or []:
            annotazione = riferimento.get_object()
            if str(annotazione.get("/T") or "") != NOME_CAMPO:
                continue
            annotazione[NameObject("/V")] = TextStringObject(testo)
            if con_apparenza:
                applicata = applica_apparenza_testo(scrittore, annotazione, testo)
    if con_apparenza:
        assert applicata is True, "l'apparenza non e' stata agganciata"
    uscita = io.BytesIO()
    scrittore.write(uscita)
    return uscita.getvalue()


def test_il_valore_scritto_senza_apparenza_non_si_vede():
    """E' il difetto da evitare: il modulo e' pieno, il foglio e' vuoto."""
    vuoto = _modulo_vuoto()

    senza = _scrivi_valore(vuoto, "Antonio Affinito", con_apparenza=False)

    assert _inchiostro(senza) == _inchiostro(vuoto)


def test_con_l_apparenza_il_valore_compare_sul_foglio():
    vuoto = _modulo_vuoto()

    con = _scrivi_valore(vuoto, "Antonio Affinito", con_apparenza=True)

    assert _inchiostro(con) > _inchiostro(vuoto) + 100


def test_un_testo_piu_lungo_lascia_piu_inchiostro():
    vuoto = _modulo_vuoto()

    corto = _inchiostro(_scrivi_valore(vuoto, "Rossi", con_apparenza=True))
    lungo = _inchiostro(_scrivi_valore(vuoto, "Rossi Mario Giuseppe", con_apparenza=True))

    assert lungo > corto


def test_le_parentesi_non_rompono_il_flusso():
    """Una parentesi non protetta chiude la stringa e il campo si stampa vuoto."""
    vuoto = _modulo_vuoto()

    con = _scrivi_valore(vuoto, "Rossi (detto Mario)", con_apparenza=True)

    assert _inchiostro(con) > _inchiostro(vuoto) + 100
    assert b"\\(" in apparenza_testo("(", larghezza=100, altezza=20)


def test_un_accento_italiano_arriva_sul_foglio():
    vuoto = _modulo_vuoto()

    con = _scrivi_valore(vuoto, "Citta' di Palmi perche' cosi'", con_apparenza=True)
    accentato = _scrivi_valore(vuoto, "Città di Palmi perché così", con_apparenza=True)

    assert _inchiostro(con) > _inchiostro(vuoto)
    assert _inchiostro(accentato) > _inchiostro(vuoto)


def test_il_corpo_dichiarato_dal_modulo_viene_rispettato():
    assert corpo_carattere(24, dichiarato=10) == 10.0


def test_senza_corpo_dichiarato_se_ne_sceglie_uno_che_ci_sta():
    assert CORPO_MINIMO <= corpo_carattere(24) <= CORPO_MASSIMO
    assert CORPO_MINIMO <= corpo_carattere(6) <= CORPO_MASSIMO
    assert corpo_carattere(1000) <= CORPO_MASSIMO, "un campo alto non fa un carattere gigante"


def test_una_casella_senza_misure_lo_dichiara_invece_di_fingere():
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject

    annotazione = DictionaryObject()
    annotazione[NameObject("/Rect")] = ArrayObject([FloatObject(0)] * 4)

    assert applica_apparenza_testo(PdfWriter(), annotazione, "x") is False
