"""Il testo di un PDF, letto senza PyMuPDF.

Per leggere il testo non serve un motore di rendering: serve un lettore.
pdfplumber e' gia' fra le dipendenze ed e' MIT; PyMuPDF e' AGPL-3.0 e il
prodotto viaggia sulla rete verso gli studi.
"""

from __future__ import annotations

import pytest

from pct import lettura_pdf

PRIMA = "TRIBUNALE DI PALMI"
SECONDA = "Il ricorrente chiede l'accoglimento"


def _pdf_due_pagine() -> bytes:
    import pymupdf

    documento = pymupdf.open()
    una = documento.new_page()
    una.insert_text(pymupdf.Point(60, 100), PRIMA, fontsize=14, fontname="helv")
    due = documento.new_page()
    due.insert_text(pymupdf.Point(60, 100), SECONDA, fontsize=12, fontname="helv")
    dati = documento.tobytes()
    documento.close()
    return dati


def test_il_testo_arriva_tutto_e_nell_ordine_giusto():
    testo = lettura_pdf.leggi_testo(_pdf_due_pagine())

    assert PRIMA in testo
    assert SECONDA in testo
    assert testo.index(PRIMA) < testo.index(SECONDA)


def test_il_testo_si_puo_avere_pagina_per_pagina():
    pagine = lettura_pdf.leggi_testo_pagine(_pdf_due_pagine())

    assert len(pagine) == 2
    assert PRIMA in pagine[0]
    assert SECONDA in pagine[1]


def test_una_pagina_senza_testo_non_sparisce_dall_elenco():
    """Una scansione non ha testo estraibile: resta una pagina vuota, non un buco."""
    import pymupdf

    documento = pymupdf.open()
    documento.new_page()
    una = documento.new_page()
    una.insert_text(pymupdf.Point(60, 100), PRIMA, fontsize=14, fontname="helv")
    dati = documento.tobytes()
    documento.close()

    pagine = lettura_pdf.leggi_testo_pagine(dati)

    assert len(pagine) == 2
    assert pagine[0] == ""
    assert PRIMA in pagine[1]


def test_un_file_che_non_e_un_pdf_viene_rifiutato():
    with pytest.raises(lettura_pdf.LetturaPdfError):
        lettura_pdf.leggi_testo(b"questo non e' un PDF")


def test_i_nomi_non_cominciano_per_test():
    """pytest raccoglie come test qualunque nome che inizi per `test`.

    Con `testo_documento` importato in un file di prova, pytest provava a
    eseguirlo come se fosse una batteria di test. I nomi pubblici di questo
    modulo devono restare fuori da quel prefisso.
    """
    for nome in lettura_pdf.__all__:
        assert not nome.lower().startswith("test"), f"{nome} verrebbe raccolto da pytest"


def test_il_secondo_motore_legge_davvero_la_pagina_chiesta():
    """Serve a chi chiama quando il lettore principale non e' affidabile."""
    dati = _pdf_due_pagine()

    assert PRIMA in lettura_pdf.leggi_testo_pagina_alternativo(dati, 0)
    assert SECONDA in lettura_pdf.leggi_testo_pagina_alternativo(dati, 1)


def test_il_secondo_motore_non_fa_cadere_l_importazione():
    """Se non riesce, chi chiama passa all'OCR: non deve sollevare."""
    assert lettura_pdf.leggi_testo_pagina_alternativo(_pdf_due_pagine(), 9) == ""
    assert lettura_pdf.leggi_testo_pagina_alternativo(_pdf_due_pagine(), -1) == ""
    assert lettura_pdf.leggi_testo_pagina_alternativo(b"non e' un PDF", 0) == ""


def test_il_secondo_motore_non_e_lo_stesso_del_primo():
    """Interrogare due volte lo stesso lettore non e' una seconda opinione."""
    import ast
    from pathlib import Path as _P

    sorgente = (_P(__file__).resolve().parents[1] / "pct" / "lettura_pdf.py").read_text(encoding="utf-8")
    corpo = next(
        nodo
        for nodo in ast.walk(ast.parse(sorgente))
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "leggi_testo_pagina_alternativo"
    )
    importati = {
        alias.name.split(".")[0]
        for nodo in ast.walk(corpo)
        if isinstance(nodo, ast.Import)
        for alias in nodo.names
    }
    assert "pypdfium2" in importati
    assert "pdfplumber" not in importati, "il secondo parere deve venire da un motore diverso"


def test_i_moduli_gia_migrati_non_importano_piu_pymupdf():
    import ast
    from pathlib import Path

    radice = Path(__file__).resolve().parents[1]
    for relativo in (
        "pct/lettura_pdf.py",
        "pct/soglie_nei_documenti.py",
        "web/services/client_portal_moduli.py",
        "web/services/mediazione_fascicolo.py",
        "web/bootstrap/mediazione_fascicolo_routes.py",
        "pct/editor.py",
    ):
        albero = ast.parse((radice / relativo).read_text(encoding="utf-8-sig"))
        importati: set[str] = set()
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Import):
                importati.update(alias.name.split(".")[0] for alias in nodo.names)
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                importati.add(nodo.module.split(".")[0])
        assert not (importati & {"fitz", "pymupdf"}), f"{relativo} importa di nuovo PyMuPDF"
