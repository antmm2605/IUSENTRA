"""Attestazione di conformità del difensore (art. 22 e 23-bis CAD; art. 196-octies disp. att. c.p.c.)."""

from __future__ import annotations

import io
from datetime import date

import pytest
from pypdf import PdfReader

from pct.attestazione_conformita import FORMULA, applica_con_esito, da_dati
from tests.test_penale_pdp import pdf_testo

DATI = {"avvocato": "Giuseppe Montagnese", "firma": "Montagnese Giuseppe", "luogo": "Taurianova", "data": "2025-09-04"}


def _testo(pdf: bytes) -> list[str]:
    return [pagina.extract_text() or "" for pagina in PdfReader(io.BytesIO(pdf)).pages]


def test_spazio_libero_sotto_il_testo_come_nella_prassi():
    """Senza riquadro l'attestazione va sotto l'ultimo testo dell'ultima pagina, nella stessa pagina."""
    originale = pdf_testo("Atto originale")
    esito = applica_con_esito(originale, da_dati(DATI))
    pagine = _testo(esito.pdf)
    assert len(pagine) == 1 and not esito.pagina_aggiunta
    testo = " ".join(pagine[0].split())
    assert testo.index("Atto originale") < testo.index("ATTESTAZIONE DI CONFORMITA’")
    assert "Il sottoscritto Avv. Giuseppe Montagnese attesta, ai sensi di legge," in testo
    assert "originale analogico dal quale è estratta" in testo and "Taurianova, 04.09.2025" in testo
    assert "Avv. Montagnese Giuseppe" in testo and "(sottoscrizione tramite firma digitale)" in testo


def test_pagina_aggiunta_su_richiesta_e_copia_di_documento_informatico():
    esito = applica_con_esito(pdf_testo("Atto"), da_dati({**DATI, "posizione": "pagina", "tipo": "informatico"}))
    pagine = _testo(esito.pdf)
    assert len(pagine) == 2 and esito.pagina_aggiunta and "documento informatico" in " ".join(pagine[1].split())


def test_riquadri_disegnati_attestazione_e_firma_testo_sotto_vera_ed_autentica():
    """I due riquadri dell'avvocato: il testo sta dentro il suo riquadro, la firma testo nel suo."""
    import pdfplumber

    dati = {**DATI, "testoFirma": "Giuseppe Montagnese", "carattereFirma": "great_vibes", "dimensioneFirma": "18",
            "riquadroAttestazione": {"pagina": 1, "x": 0.1, "y": 0.6, "larghezza": 0.5, "altezza": 0.2},
            "riquadroFirma": {"pagina": 1, "x": 0.65, "y": 0.7, "larghezza": 0.25, "altezza": 0.05}}
    esito = applica_con_esito(pdf_testo("Procura"), da_dati(dati))
    assert esito.dimensione_firma == 18
    with pdfplumber.open(io.BytesIO(esito.pdf)) as documento:
        pagina = documento.pages[0]
        larghezza, altezza = float(pagina.width), float(pagina.height)
        parole = pagina.extract_words()
    titolo = next(p for p in parole if p["text"] == "ATTESTAZIONE")
    assert 0.1 * larghezza - 0.5 <= titolo["x0"] < 0.12 * larghezza and 0.6 * altezza <= titolo["top"] < 0.8 * altezza
    firma = [p for p in parole if p["x0"] >= 0.65 * larghezza and 0.7 * altezza <= p["top"] <= 0.75 * altezza]
    assert "Montagnese" in " ".join(p["text"] for p in firma)


def test_riquadro_troppo_piccolo_o_fuori_pagina():
    with pytest.raises(ValueError, match="troppo piccolo"):
        applica_con_esito(pdf_testo("Atto"), da_dati({**DATI, "riquadroAttestazione": {
            "pagina": 1, "x": 0.1, "y": 0.1, "larghezza": 0.2, "altezza": 0.02}}))
    with pytest.raises(ValueError):
        da_dati({**DATI, "riquadroFirma": {"pagina": 1, "x": 0.9, "y": 0.1, "larghezza": 0.3, "altezza": 0.1}})
    with pytest.raises(ValueError, match="pagine"):
        applica_con_esito(pdf_testo("Atto"), da_dati({**DATI, "riquadroFirma": {
            "pagina": 3, "x": 0.1, "y": 0.1, "larghezza": 0.3, "altezza": 0.1}}))


def test_scelte_non_ammesse():
    with pytest.raises(ValueError):
        da_dati({**DATI, "dimensioneTesto": "40"})
    with pytest.raises(ValueError):
        da_dati({**DATI, "carattereTesto": "great_vibes"})
    with pytest.raises(ValueError):
        da_dati({**DATI, "luogo": ""})
    assert da_dati({k: v for k, v in DATI.items() if k != "data"}).data == date.today()
    assert da_dati({k: v for k, v in DATI.items() if k != "firma"}).firma == "Montagnese Giuseppe"
    assert "{avvocato}" in FORMULA


def test_rotta_anteprima_applica_sul_documento_e_porta_alla_firma(tmp_path):
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
        assert opzioni["ok"] and opzioni["predefiniti"]["tipo"] == "analogico" and not opzioni["firmato"]
        assert opzioni["pagine"]["meta"].endswith(f"/{documento.id}/pdf-meta")
        assert any(v["id"] == "great_vibes" for v in opzioni["caratteriFirma"])
        anteprima = client.post(indirizzo, headers=intestazioni, json={**DATI, "anteprima": True}).get_json()
        assert anteprima["ok"] and anteprima["esito"].startswith("Attestazione scritta a pagina 1")
        assert [p["numero"] for p in anteprima["pagine"]] == [1]
        assert anteprima["pagine"][0]["immagine"].startswith("data:image/png;base64,")
        applicata = client.post(indirizzo, headers=intestazioni, json=DATI).get_json()
        assert applicata["ok"] and applicata["documento"]["nome"] == "Procura.pdf"
        assert applicata["firmaUrl"] == (f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/firma"
                                         "?firma_visibile=basso_destra&luogo=Taurianova&da=attestazione")
        assert client.post(indirizzo, headers=intestazioni, json={**DATI, "dimensioneTesto": "3"}).status_code == 400
    with app.test_request_context("/"):
        documenti = get_fascicoli().get(fascicolo.id).documenti
        aggiornato = next(d for d in documenti if d.id == documento.id)
        contenuto = get_fascicoli().percorso_documento_lettura(fascicolo.id, documento.id).read_bytes()
    assert [d.nome for d in documenti] == ["Procura.pdf"] and len(aggiornato.versioni) == 1
    assert "ATTESTAZIONE DI CONFORMITA" in " ".join(_testo(contenuto))


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


def test_spazio_libero_su_una_scansione():
    """La copia di un originale analogico è un'immagine: lo spazio si trova guardando l'inchiostro."""
    from PIL import Image, ImageDraw

    from pct.attestazione_spazio import cerca

    foglio = Image.new("L", (1240, 1754), 255)  # A4 a 150 dpi
    disegno = ImageDraw.Draw(foglio)
    for riga in range(20):  # testo fino a metà pagina
        disegno.rectangle([200, 180 + riga * 40, 1050, 200 + riga * 40], fill=0)
    disegno.rectangle([900, 1000, 1100, 1100], fill=0)  # firma della parte, a destra
    buffer = io.BytesIO()
    foglio.save(buffer, format="PDF", resolution=150)
    spazio = cerca(buffer.getvalue(), 280, 100, riserva_basso=72)
    assert spazio is not None
    fine_testo = 842 - (200 + 19 * 40) * 72 / 150
    assert 90 <= spazio.x <= 100 and fine_testo - 30 < spazio.y_alto < fine_testo
    assert cerca(buffer.getvalue(), 280, 700) is None


def test_documento_gia_firmato_non_si_attesta(tmp_path):
    from pct.fascicoli import TipoDocumento, TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_fascicoli

    app = _app(tmp_path)
    with app.test_request_context("/"):
        fascicolo = get_fascicoli().nuovo("Prova", TipoFascicolo.CIVILE)
        documento = get_fascicoli().aggiungi_documento(fascicolo.id, "Procura.pdf", TipoDocumento.PROCURA, pdf_testo("Procura"))
        get_fascicoli().segna_firmato(fascicolo.id, documento.id, signature_metadata={"format": "pades"})
    indirizzo = f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/attestazione"
    with app.test_client() as client:
        _login(client)
        assert client.get(indirizzo, headers={"Accept": "application/json"}).get_json()["firmato"] is True
        risposta = client.post(indirizzo, headers={"Accept": "application/json"}, json=DATI)
        assert risposta.status_code == 409 and "prima della firma" in risposta.get_json()["messaggio"]
