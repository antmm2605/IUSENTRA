"""Regressioni emerse nella prova reale della utility OCR a sei pagine."""

import pytest

from legal_ocr.motore.consenso import LetturaSecondaria, applica_consenso
from legal_ocr.ner_legal import extract_legal_entities
from web.services import document_ocr_documento as documento
from web.services.document_ocr import OcrPageResult


def _pagina():
    righe = ["Tribunale di Miiano", "Sezione civile prima", "Udienza da preparare", "Documento della parte"]
    return [
        {"text": parola, "conf": 0.41 if parola == "Miiano" else 0.96,
         "left": 10 + colonna * 60, "top": 20 + riga * 30,
         "width": 50, "height": 20, "block": 1, "par": 1, "line": riga + 1}
        for riga, testo in enumerate(righe) for colonna, parola in enumerate(testo.split())
    ]


def test_capoverso_riunito_preserva_coordinate_e_incertezza():
    parole = _pagina()
    testo = " ".join(p["text"] for p in parole).replace("Miiano", "Milano")
    nuove, numero = applica_consenso(parole, LetturaSecondaria(testo, 0.99, "pp-ocr", 0.1))
    assert numero == 1
    assert nuove[2] == {**parole[2], "text": "Milano", "consenso": True}
    assert parole[2]["text"] == "Miiano"
    assert nuove[:2] == parole[:2] and nuove[3:] == parole[3:]


@pytest.mark.parametrize("trasforma", [
    lambda t: t.replace("di Miiano", "di nuovo Milano"),
    lambda t: t.replace("Miiano Sezione", "Milano Camera"),
])
def test_non_inserisce_parole_ne_corregge_segmenti_tra_righe(trasforma):
    parole = _pagina()
    testo = trasforma(" ".join(p["text"] for p in parole))
    nuove, numero = applica_consenso(parole, LetturaSecondaria(testo, 0.99, "pp-ocr", 0.1))
    assert numero == 0 and nuove == parole


def test_consenso_per_riga_non_promuove_confidenza_di_pagina():
    parole = _pagina()[:3]
    nuove, numero = applica_consenso(parole, LetturaSecondaria("Tribunale di Milano", 0.99, "pp-ocr", 0.1))
    assert numero == 1 and nuove[2]["conf"] == 0.41


def test_norma_vicina_a_rg_non_diventa_numero_di_ruolo():
    entita = extract_legal_entities("R.G. 1234/2026. Copia per immagine ai sensi del D.Lgs. 82/2005, art. 22.")
    assert [(n["numero"], n["anno"]) for n in entita["numero_ruolo"]] == [("1234", "2026")]
    assert any("82/2005" in riferimento for riferimento in entita["riferimenti"])


@pytest.mark.parametrize("nome,pdf", [("scansione.jpg", False), ("scansione.pdf", True)])
def test_wrapper_trasmette_confronto_del_secondo_lettore(monkeypatch, nome, pdf):
    import io
    import fitz
    from PIL import Image

    motore = "pdf-inspector:pp-ocrv6-small@oar-ocr-v0.7.0"
    monkeypatch.setattr(documento, "recognize_page", lambda *args, **kwargs: OcrPageResult(
        pdf=b"%PDF-1.4 prova", paragraphs=["Tribunale di Milano"], dpi=300,
        blocks=[], figures=[], confidence=0.8, engine="tesseract",
        consenso=2, secondo_lettore=motore,
    ))
    if pdf:
        originale = fitz.open()
        originale.new_page()
        dati = originale.tobytes()
        originale.close()
    else:
        buffer = io.BytesIO()
        Image.new("RGB", (100, 100), "white").save(buffer, "JPEG")
        dati = buffer.getvalue()
    pagina = documento.riconosci_pagina(dati, nome, 1)
    payload = documento.come_payload(pagina)
    assert pagina.consenso == payload["consenso"] == 2
    assert pagina.secondo_lettore == payload["secondo_lettore"] == motore


def test_pagina_nativa_non_dichiara_confronto_ocr():
    import fitz

    pdf = fitz.open()
    pagina = pdf.new_page()
    pagina.insert_text((60, 80), "Tribunale di Milano. Il documento contiene testo nativo leggibile e non richiede riconoscimento ottico.")
    risultato = documento.riconosci_pagina(pdf.tobytes(), "originale.pdf", 1)
    pdf.close()
    assert risultato.origine == documento.ORIGINE_TESTO
    assert documento.come_payload(risultato)["consenso"] == 0
    assert documento.come_payload(risultato)["secondo_lettore"] == ""
