"""L'editor PDF a overlay: cosa promette e cosa fa davvero.

Due promesse che prima non erano mantenute. La copertura sembrava nascondere il
testo e invece lo lasciava nel file, recuperabile con un copia-incolla. Il
salvataggio diceva di modificare il PDF originale e invece lo ricostruiva da
capo, quindi l'originale non era piu' verificabile dentro il file modificato.
"""

from __future__ import annotations

import fitz
import pytest

from web.services.pdf_overlay_editor import PdfOverlayError, apply_pdf_overlays

TESTO_RISERVATO = "Codice fiscale del cliente RSSMRA80A01H501U"
TESTO_NORMALE = "Il ricorrente chiede l'accoglimento del ricorso."


def _pdf_di_prova() -> bytes:
    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text(fitz.Point(60, 120), TESTO_RISERVATO, fontsize=12, fontname="helv")
    pagina.insert_text(fitz.Point(60, 300), TESTO_NORMALE, fontsize=12, fontname="helv")
    dati = documento.tobytes()
    documento.close()
    return dati


def _testo_estraibile(pdf_bytes: bytes) -> str:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as documento:
        return "\n".join(pagina.get_text() for pagina in documento)


def _riquadro_sul_testo_riservato() -> dict:
    """Copre la banda orizzontale dove sta il codice fiscale."""
    return {
        "type": "cover",
        "page": 1,
        "x": 0.0,
        "y": 0.12,
        "width": 1.0,
        "height": 0.06,
    }


def test_la_copertura_toglie_davvero_il_testo_dal_file():
    originale = _pdf_di_prova()
    assert TESTO_RISERVATO in _testo_estraibile(originale)

    modificato, quante = apply_pdf_overlays(originale, [_riquadro_sul_testo_riservato()])

    assert quante == 1
    estratto = _testo_estraibile(modificato)
    assert TESTO_RISERVATO not in estratto, "coperto ma ancora leggibile: non e' un oscuramento"
    assert TESTO_NORMALE in estratto, "il resto della pagina deve restare"


def test_senza_oscuramenti_il_salvataggio_e_incrementale():
    """I byte dell'originale restano in testa al file modificato."""
    originale = _pdf_di_prova()

    modificato, _ = apply_pdf_overlays(
        originale,
        [{"type": "text", "page": 1, "x": 0.1, "y": 0.5, "text": "Nota a margine", "fontSizePt": 10}],
    )

    assert len(modificato) > len(originale)
    assert modificato.startswith(originale), "l'originale non e' piu' intatto dentro il file modificato"
    assert "Nota a margine" in _testo_estraibile(modificato)


def test_con_un_oscuramento_il_file_viene_riscritto():
    """Un salvataggio incrementale conserverebbe il testo appena tolto."""
    originale = _pdf_di_prova()

    modificato, _ = apply_pdf_overlays(originale, [_riquadro_sul_testo_riservato()])

    assert not modificato.startswith(originale), "la revisione vecchia conterrebbe ancora il testo oscurato"
    assert TESTO_RISERVATO.encode("latin-1", "ignore") not in modificato or TESTO_RISERVATO not in _testo_estraibile(modificato)


def test_nessuna_modifica_non_produce_un_file():
    with pytest.raises(PdfOverlayError):
        apply_pdf_overlays(_pdf_di_prova(), [])


def test_una_pagina_inesistente_viene_rifiutata():
    with pytest.raises(PdfOverlayError):
        apply_pdf_overlays(
            _pdf_di_prova(),
            [{"type": "highlight", "page": 9, "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.05}],
        )
