"""Lo strato di testo selezionabile del lettore, senza PyMuPDF.

E' un di piu' del lettore, non il lettore: se il PDF non si apre le pagine
devono comunque comparire, senza selezione. Questi test fissano quel
comportamento, che e' la ragione per cui il modulo esiste.
"""

from __future__ import annotations

import re

from web.services.pdf_reader_text import text_layers

TESTO = "TRIBUNALE DI PALMI sezione lavoro"


def _pdf(rotazione: int = 0, pagine: int = 1) -> bytes:
    import pymupdf

    documento = pymupdf.open()
    for _ in range(pagine):
        pagina = documento.new_page()
        pagina.insert_text(pymupdf.Point(60, 100), TESTO, fontsize=13, fontname="helv")
        if rotazione:
            pagina.set_rotation(rotazione)
    dati = documento.tobytes()
    documento.close()
    return dati


def test_ogni_parola_diventa_un_riquadro_selezionabile():
    strati = text_layers(_pdf())

    assert len(strati) == 1
    assert "reader-text-layer" in strati[0]
    for parola in ("TRIBUNALE", "PALMI", "lavoro"):
        assert parola in strati[0]


def test_le_percentuali_restano_dentro_la_pagina():
    """Le coordinate sono percentuali sulla pagina: fuori scala sballano l'overlay."""
    strato = text_layers(_pdf())[0]

    valori = [float(v) for v in re.findall(r"(?:left|top|width|height):([\d.]+)%", strato)]

    assert valori
    assert all(0.0 <= v <= 100.0 for v in valori)


def test_una_pagina_ruotata_resta_allineata():
    """La rotazione dichiarata dalla pagina e' gia' applicata alle coordinate."""
    strato = text_layers(_pdf(rotazione=90))[0]

    valori = [float(v) for v in re.findall(r"(?:left|top):([\d.]+)%", strato)]

    assert valori
    assert all(0.0 <= v <= 100.0 for v in valori)


def test_un_pdf_illeggibile_non_toglie_le_pagine_al_lettore():
    """Un guasto qui non si propaga: il lettore mostra comunque le immagini."""
    assert text_layers(b"questo non e' un PDF") == []


def test_una_pagina_senza_testo_lo_dichiara():
    import pymupdf

    documento = pymupdf.open()
    documento.new_page()
    dati = documento.tobytes()
    documento.close()

    strati = text_layers(dati)

    assert len(strati) == 1
    assert "reader-no-text" in strati[0]


def test_ogni_pagina_ha_il_suo_strato():
    strati = text_layers(_pdf(pagine=3))

    assert len(strati) == 3


def test_il_lettore_non_dipende_piu_da_pymupdf():
    import ast
    from pathlib import Path

    sorgente = (Path(__file__).resolve().parents[1] / "web" / "services" / "pdf_reader_text.py").read_text(
        encoding="utf-8-sig"
    )
    importati: set[str] = set()
    for nodo in ast.walk(ast.parse(sorgente)):
        if isinstance(nodo, ast.Import):
            importati.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importati.add(nodo.module.split(".")[0])
    assert not (importati & {"fitz", "pymupdf"})
