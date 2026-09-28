"""Attestazione di conformità del difensore (art. 22 e 23-bis CAD; art. 196-octies disp. att. c.p.c.)."""

from __future__ import annotations

import io
from datetime import date

import pytest
from pypdf import PdfReader

from pct.attestazione_conformita import FORMULA, applica, da_dati
from tests.test_penale_pdp import pdf_testo

DATI = {"avvocato": "Giuseppe Montagnese", "firma": "Montagnese Giuseppe", "luogo": "Taurianova", "data": "2025-09-04"}


def _testo(pdf: bytes) -> list[str]:
    return [pagina.extract_text() or "" for pagina in PdfReader(io.BytesIO(pdf)).pages]


def test_pagina_finale_con_formula_luogo_data_e_firma():
    originale = pdf_testo("Atto originale")
    copia = applica(originale, da_dati(DATI))
    pagine = _testo(copia)
    assert len(pagine) == 2 and "Atto originale" in pagine[0]
    ultima = " ".join(pagine[1].split())
    assert "ATTESTAZIONE DI CONFORMITÀ" in ultima
    assert "Il sottoscritto Avv. Giuseppe Montagnese attesta" in ultima and "originale analogico" in ultima
    assert "Taurianova, 04.09.2025" in ultima
    assert "Avv. Montagnese Giuseppe" in ultima and "(sottoscrizione tramite firma digitale)" in ultima


def test_in_fondo_all_ultima_pagina_e_copia_di_documento_informatico():
    copia = applica(pdf_testo("Atto"), da_dati({**DATI, "posizione": "fondo", "tipo": "informatico"}))
    pagine = _testo(copia)
    assert len(pagine) == 1 and "documento informatico" in " ".join(pagine[0].split())


def test_scelte_non_ammesse():
    with pytest.raises(ValueError):
        da_dati({**DATI, "dimensioneFirma": "40"})
    with pytest.raises(ValueError):
        da_dati({**DATI, "carattereTesto": "comic"})
    with pytest.raises(ValueError):
        da_dati({**DATI, "luogo": ""})
    assert da_dati({k: v for k, v in DATI.items() if k != "data"}).data == date.today()
    assert "{avvocato}" in FORMULA


def test_rotta_anteprima_e_copia_salvata(tmp_path):
    from pct.fascicoli import TipoDocumento, TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_fascicoli

    app = _app(tmp_path)
    with app.test_request_context("/"):
        fascicolo = get_fascicoli().nuovo("Prova", TipoFascicolo.CIVILE)
        documento = get_fascicoli().aggiungi_documento(fascicolo.id, "Procura.pdf", TipoDocumento.PROCURA, pdf_testo("Procura"))
    indirizzo = f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/attestazione"
    intestazioni = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    with app.test_client() as client:
        _login(client)
        opzioni = client.get(indirizzo, headers=intestazioni).get_json()
        assert opzioni["ok"] and opzioni["predefiniti"]["tipo"] == "analogico" and opzioni["caratteri"]
        anteprima = client.post(indirizzo, headers=intestazioni, json={**DATI, "anteprima": True})
        assert anteprima.status_code == 200 and anteprima.mimetype == "application/pdf"
        salvata = client.post(indirizzo, headers=intestazioni, json=DATI).get_json()
        assert salvata["ok"] and salvata["documento"]["nome"] == "Procura - copia conforme.pdf"
        assert client.post(indirizzo, headers=intestazioni, json={**DATI, "dimensioneTesto": "3"}).status_code == 400
    with app.test_request_context("/"):
        nomi = [d.nome for d in get_fascicoli().get(fascicolo.id).documenti]
    assert "Procura.pdf" in nomi and "Procura - copia conforme.pdf" in nomi


def test_pdfa_registrato_sul_documento_e_pulsante_nascosto():
    """Il documento PDF/A mostra la versione e non propone più la conversione (niente clic «a vuoto»)."""
    from web.services import react_fascicoli_bridge as bridge

    class Doc:
        nome = "Atto.pdf"
        fonte_documento = ""
        tags = ["PDF/A-2B"]

    assert bridge._versione_pdfa(Doc) == "PDF/A-2B" and not bridge._pdfa_convertibile(Doc, False)
    Doc.tags = []
    assert bridge._pdfa_convertibile(Doc, False) and not bridge._pdfa_convertibile(Doc, True)
    Doc.nome = "Atto.docx"
    assert not bridge._pdfa_convertibile(Doc, False) and not bridge._e_pdf(Doc)
