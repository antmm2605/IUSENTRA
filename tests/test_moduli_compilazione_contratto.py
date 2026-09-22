"""Cosa deve contenere un modulo dopo la compilazione.

I test che c'erano verificavano il giro — il modulo si legge, la copia
compilata nasce — ma non che il valore finisse davvero dentro il PDF, ne' che
fosse visibile. Un campo il cui valore sta nel modulo senza apparenza disegnata
si stampa vuoto in alcuni lettori: per un modulo che va depositato a un
organismo e' un difetto che nessuno vede finche' non e' tardi.

Questi test fissano il contratto, e valgono qualunque libreria ci sia sotto.
"""

from __future__ import annotations

import pytest

from pct.mediazione_documenti import campi_pdf, compila_pdf


def _modulo_vuoto() -> bytes:
    import pymupdf

    documento = pymupdf.open()
    pagina = documento.new_page()
    for nome, alto in (("nome_istante", 100), ("recapito", 160)):
        campo = pymupdf.Widget()
        campo.field_name = nome
        campo.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        campo.rect = pymupdf.Rect(72, alto, 400, alto + 24)
        campo.field_value = ""
        pagina.add_widget(campo)
    casella = pymupdf.Widget()
    casella.field_name = "accetto"
    casella.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    casella.rect = pymupdf.Rect(72, 220, 92, 240)
    casella.field_value = False
    pagina.add_widget(casella)
    dati = documento.tobytes()
    documento.close()
    return dati


def _valori_nel_pdf(dati: bytes) -> dict[str, object]:
    """Rilegge i valori dal modulo, con un lettore indipendente."""
    import io

    from pypdf import PdfReader

    campi = PdfReader(io.BytesIO(dati)).get_fields() or {}
    return {nome: voce.get("/V") for nome, voce in campi.items()}


def test_il_valore_scritto_si_rilegge_dal_modulo():
    compilato = compila_pdf(_modulo_vuoto(), {"nome_istante": "Antonio Affinito"})

    assert _valori_nel_pdf(compilato).get("nome_istante") == "Antonio Affinito"


def test_il_campo_compilato_ha_un_apparenza_disegnata():
    """Senza apparenza il campo e' pieno nel modulo e vuoto sul foglio."""
    import io

    from pypdf import PdfReader

    compilato = compila_pdf(_modulo_vuoto(), {"nome_istante": "Antonio Affinito"})

    lettore = PdfReader(io.BytesIO(compilato))
    annotazioni = lettore.pages[0].get("/Annots") or []
    trovato = False
    for riferimento in annotazioni:
        annotazione = riferimento.get_object()
        if str(annotazione.get("/T") or "") != "nome_istante":
            continue
        trovato = True
        assert annotazione.get("/AP"), "il campo compilato non ha apparenza disegnata"
    assert trovato, "il campo non e' piu' nel modulo"


def test_la_casella_selezionata_non_resta_su_off():
    compilato = compila_pdf(_modulo_vuoto(), {"accetto": True})

    valore = str(_valori_nel_pdf(compilato).get("accetto") or "")

    assert valore and valore != "/Off", f"casella non selezionata: {valore!r}"


def test_un_campo_che_non_esiste_viene_rifiutato():
    with pytest.raises(ValueError):
        compila_pdf(_modulo_vuoto(), {"campo_inventato": "x"})


def test_un_testo_oltre_il_limite_del_campo_viene_rifiutato():
    limite = next(c for c in campi_pdf(_modulo_vuoto()) if c["nome"] == "nome_istante")["max_caratteri"]

    with pytest.raises(ValueError):
        compila_pdf(_modulo_vuoto(), {"nome_istante": "x" * (limite + 1)})


def test_una_selezione_non_booleana_viene_rifiutata():
    with pytest.raises(ValueError):
        compila_pdf(_modulo_vuoto(), {"accetto": "si"})


def test_il_modulo_compilato_non_porta_javascript():
    """Lo scrub e' una misura di sicurezza: non deve perdersi nella migrazione."""
    compilato = compila_pdf(_modulo_vuoto(), {"nome_istante": "Antonio Affinito"})

    assert b"/JavaScript" not in compilato
    assert b"/JS" not in compilato
