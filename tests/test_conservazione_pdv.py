"""Conservazione: pacchetto di versamento con i metadati dell'Allegato 5 e i formati dell'Allegato 2
(Linee guida AgID), impronte verificabili e registro degli esiti del conservatore."""

from __future__ import annotations

import hashlib
import io
import zipfile
from types import SimpleNamespace
from xml.etree import ElementTree as ET

from pct.conservazione.formati import formato_file
from pct.conservazione.metadati import metadati_documento
from pct.conservazione.pacchetto import NAMESPACE, crea_pdv

NS = {"p": NAMESPACE}


def _documento(**campi):
    base = dict(id="D1", nome="comparsa.pdf.p7m", nome_originale="comparsa.pdf.p7m", tipo=SimpleNamespace(value="COMPARSA"),
                data_caricamento="2026-09-01T10:00:00", fonte_documento="", mittente_portale="", id_deposito_pct="DEP1",
                firmato_digitalmente=True, caricato_da="avv.rossi", tags=["pct"], note="", versioni=[], tipo_atto_portale="")
    base.update(campi)
    return SimpleNamespace(**base)


def test_formati_allegato_2():
    assert formato_file("atto.pdf")["idoneo"] is True
    firmato = formato_file("atto.pdf.p7m")
    assert firmato["idoneo"] is True and "PDF firmato" in firmato["formato"]
    assert formato_file("vecchio.doc")["idoneo"] is False and "PDF/A" in formato_file("vecchio.doc")["nota"]
    assert formato_file("busta.doc.p7m")["idoneo"] is False


def test_metadati_documento_informatico():
    fascicolo = SimpleNamespace(id="F1", numero="2026/001", titolo="Rossi c. Bianchi")
    meta = metadati_documento(_documento(), fascicolo, b"contenuto", produttore="Studio Rossi", anni_conservazione=10,
                              versione_software="2.430.0")
    assert meta["IdDoc"]["ImprontaCrittograficaDelDocumento"] == {"Impronta": hashlib.sha256(b"contenuto").hexdigest(), "Algoritmo": "SHA-256"}
    assert meta["ModalitaDiFormazione"] == "b"
    assert meta["DatiDiRegistrazione"]["TipologiaDiFlusso"] == "U"  # depositato dallo studio
    assert meta["Verifica"]["FirmatoDigitalmente"] == "Vero" and meta["Riservato"] == "Vero"
    assert meta["Agg"] == {"TipoAggregazione": "Fascicolo", "IdAggregazione": "2026/001"}
    assert meta["IdentificativoDelFormato"]["Formato"] == "application/pkcs7-mime"
    ricevuto = metadati_documento(_documento(fonte_documento="PORTALE_TELEMATICO", mittente_portale="Tribunale di Milano",
                                             id_deposito_pct=""), fascicolo, b"x", produttore="Studio", anni_conservazione=10)
    assert ricevuto["DatiDiRegistrazione"]["TipologiaDiFlusso"] == "E"
    assert {"Ruolo": "Mittente", "TipoSoggetto": "PAI", "Denominazione": "Tribunale di Milano"} in ricevuto["Soggetti"]
    creato = metadati_documento(_documento(fonte_documento="TEMPLATE_ATTI_COMPILATORE", id_deposito_pct=""), fascicolo, b"x",
                                produttore="Studio", anni_conservazione=10)
    assert creato["ModalitaDiFormazione"] == "a" and creato["DatiDiRegistrazione"]["TipologiaDiFlusso"] == "I"


def test_pacchetto_deterministico_e_verificabile():
    fascicolo = SimpleNamespace(id="F1", numero="2026/001", titolo="Rossi c. Bianchi")
    meta = metadati_documento(_documento(), fascicolo, b"contenuto", produttore="Studio Rossi", anni_conservazione=10)
    argomenti = dict(identificativo="PDV-1", creato_il="2026-09-29T10:00:00+02:00",
                     produttore={"Denominazione": "Studio Rossi"}, fascicolo={"IdAggregazione": "2026/001", "Oggetto": "Rossi c. Bianchi"},
                     voci=[(meta, "comparsa.pdf.p7m", b"contenuto")])
    primo, elenco = crea_pdv(**argomenti)
    secondo, _ = crea_pdv(**argomenti)
    assert primo == secondo and elenco[0]["impronta"] == hashlib.sha256(b"contenuto").hexdigest()
    with zipfile.ZipFile(io.BytesIO(primo)) as archivio:
        nomi = archivio.namelist()
        assert nomi[0] == "IndicePdV.xml" and "documenti/0001_comparsa.pdf.p7m" in nomi and "metadati/0001.xml" in nomi
        for riga in archivio.read("impronte.sha256").decode().splitlines():
            impronta, percorso = riga.split("  ", 1)
            assert hashlib.sha256(archivio.read(percorso)).hexdigest() == impronta
        indice = ET.fromstring(archivio.read("IndicePdV.xml"))
        assert indice.find("p:Documenti/p:Documento/p:Impronta", NS).text == elenco[0]["impronta"]
        metadati = ET.fromstring(archivio.read("metadati/0001.xml"))
        assert metadati.find("p:Verifica/p:FirmatoDigitalmente", NS).text == "Vero"
        assert metadati.find("p:Soggetti/p:Soggetto/p:Ruolo", NS).text == "Produttore"


def test_rotte_pacchetto_download_ed_esito(tmp_path):
    from pct.fascicoli import TipoDocumento, TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_fascicoli

    app = _app(tmp_path)
    with app.test_request_context("/"):
        fascicolo = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE, numero_rg="123/2026")
        get_fascicoli().aggiungi_documento(fascicolo.id, "comparsa.pdf", TipoDocumento.COMPARSA, b"%PDF-1.4 comparsa")
        get_fascicoli().aggiungi_documento(fascicolo.id, "nota.doc", TipoDocumento.ALTRO, b"vecchio word")
    h = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    with app.test_client() as client:
        _login(client)
        dati = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/conservazione", headers=h).get_json()
        assert [d["idoneo"] for d in dati["documenti"]] == [True, False]
        creato = client.post(f"/fascicoli/{fascicolo.id}/conservazione/pacchetto", json={"anni": 10}, headers=h).get_json()
        assert creato["ok"] and len(creato["versamento"]["documenti"]) == 2
        scaricato = client.get(creato["download"])
        assert scaricato.status_code == 200
        assert hashlib.sha256(scaricato.data).hexdigest() == creato["versamento"]["impronta_pacchetto"]
        with zipfile.ZipFile(io.BytesIO(scaricato.data)) as archivio:
            assert archivio.read("documenti/0001_comparsa.pdf") == b"%PDF-1.4 comparsa"
        vid = creato["versamento"]["id"]
        assert client.post(f"/fascicoli/{fascicolo.id}/conservazione/{vid}/esito", json={"stato": "versato", "data": "2026-09-29"},
                           headers=h).status_code == 400
        esito = client.post(f"/fascicoli/{fascicolo.id}/conservazione/{vid}/esito",
                            json={"stato": "versato", "conservatore": "Conservatore Esempio", "data": "2026-09-29", "idRapporto": "RdV-77"},
                            headers=h).get_json()
        assert esito["ok"] and esito["versamento"]["stato"] == "versato"
        dopo = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/conservazione", headers=h).get_json()
        assert all(d["versato"] for d in dopo["documenti"]) and dopo["versamenti"][0]["id_rapporto"] == "RdV-77"
        assert client.get(f"/fascicoli/ALTRO/conservazione/{vid}/pacchetto.zip", headers=h).status_code == 404
