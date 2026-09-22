"""Il rendering delle pagine, sopra PDFium invece che sopra MuPDF.

Il motivo della sostituzione non e' tecnico ma di licenza: PyMuPDF e' sotto
AGPL-3.0 e IUSENTRA viene servito agli studi attraverso la rete. Questi test
fissano il comportamento che i quattro punti di rendering davano prima, cosi'
la sostituzione si vede se cambia qualcosa.
"""

from __future__ import annotations

import base64

import pytest

from pct.rendering_pdf import (
    SCALA_MASSIMA,
    SCALA_MINIMA,
    RenderingPdfError,
    dimensioni_pagine,
    pagina_png,
    pagine_png,
)

MAGIA_PNG = b"\x89PNG\r\n\x1a\n"


def _pdf_due_pagine() -> bytes:
    import pymupdf

    documento = pymupdf.open()
    prima = documento.new_page()
    prima.insert_text(pymupdf.Point(60, 100), "TRIBUNALE DI PALMI", fontsize=14, fontname="helv")
    seconda = documento.new_page()
    seconda.insert_text(pymupdf.Point(60, 100), "Allegato secondo", fontsize=12, fontname="helv")
    dati = documento.tobytes()
    documento.close()
    return dati


def test_le_dimensioni_sono_in_punti_e_le_pagine_si_contano_da_uno():
    misure = dimensioni_pagine(_pdf_due_pagine())

    assert [m.numero for m in misure] == [1, 2]
    assert all(m.larghezza > 100 and m.altezza > 100 for m in misure)


def test_una_pagina_esce_come_png():
    png = pagina_png(_pdf_due_pagine(), numero_pagina=2)

    assert png.startswith(MAGIA_PNG)
    assert len(png) > 500


def test_una_pagina_inesistente_viene_rifiutata():
    with pytest.raises(RenderingPdfError):
        pagina_png(_pdf_due_pagine(), numero_pagina=9)

    with pytest.raises(RenderingPdfError):
        pagina_png(_pdf_due_pagine(), numero_pagina=0)


def test_un_file_che_non_e_un_pdf_viene_rifiutato():
    with pytest.raises(RenderingPdfError):
        dimensioni_pagine(b"questo non e' un PDF")


@pytest.mark.parametrize("chiesta,attesa", [(0.01, SCALA_MINIMA), (99.0, SCALA_MASSIMA)])
def test_l_ingrandimento_resta_nei_limiti(chiesta, attesa):
    """Uno zoom fuori scala non deve produrre un'immagine ingestibile."""
    dati = _pdf_due_pagine()

    png = pagina_png(dati, numero_pagina=1, scala=chiesta)
    riferimento = pagina_png(dati, numero_pagina=1, scala=attesa)

    assert len(png) == len(riferimento)


def test_tutte_le_pagine_con_le_misure():
    pagine = pagine_png(_pdf_due_pagine(), dpi=130)

    assert [voce["pagina"] for voce in pagine] == [0, 1]
    assert all(voce["png"].startswith(MAGIA_PNG) for voce in pagine)
    assert all(voce["larghezza"] > 100 for voce in pagine)


def test_l_anteprima_del_modulo_resta_in_base64(tmp_path):
    """Il portale clienti riceve data-uri: il formato non deve cambiare."""
    from pct.firma_modulo.anteprima import anteprima_pagine

    percorso = tmp_path / "modulo.pdf"
    percorso.write_bytes(_pdf_due_pagine())

    pagine = anteprima_pagine(str(percorso))

    assert len(pagine) == 2
    for voce in pagine:
        assert voce["png"].startswith("data:image/png;base64,")
        grezzo = base64.b64decode(voce["png"].split(",", 1)[1])
        assert grezzo.startswith(MAGIA_PNG)


def test_il_conteggio_pagine_passa_dallo_stesso_motore():
    from web.bootstrap.fascicoli_document_helpers import pdf_page_count

    assert pdf_page_count(_pdf_due_pagine()) == 2


def test_i_moduli_di_rendering_non_dipendono_piu_da_pymupdf():
    """Sono i punti gia' migrati: se qualcuno ci rimette fitz, si vede qui."""
    from pathlib import Path as _P

    import ast
    import re

    radice = _P(__file__).resolve().parents[1]
    moduli_vietati = {"fitz", "pymupdf"}
    for relativo in (
        "pct/rendering_pdf.py",
        "pct/firma_modulo/anteprima.py",
        "web/bootstrap/fascicoli_document_helpers.py",
    ):
        testo = (radice / relativo).read_text(encoding="utf-8")
        albero = ast.parse(testo)
        importati: set[str] = set()
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Import):
                importati.update(alias.name.split(".")[0] for alias in nodo.names)
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                importati.add(nodo.module.split(".")[0])
        assert not (importati & moduli_vietati), f"{relativo} importa di nuovo PyMuPDF"
        assert not re.search(r"\bfitz\.", testo), f"{relativo} usa di nuovo l'API di PyMuPDF"
