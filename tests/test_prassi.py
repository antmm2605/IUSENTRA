"""Prassi dalle fonti ufficiali: elenchi dell'Agenzia delle Entrate e dell'INPS, testi, ricerca, ripresa."""
import json
from types import SimpleNamespace

from pct.prassi import fonti
from pct.prassi.archivio import ArchivioPrassi
from pct.prassi.recupero import esegui_tratto

PAGINA_ADE = """<div><p><strong>Circolare n. 16 del 28/06/2024 </strong></p><p><a href="https://www.agenziaentrate.gov.it/portale/documents/20143/6193294/Circolare.pdf/cbc?t=1">
 Modifiche alle procedure di compensazione di crediti </a></p></div>
<div><p><strong>Risoluzione n. 45 del 13/11/2026</strong></p><p><a href="/portale/documents/20143/1/Risoluzione+45.pdf">Interpello IVA</a></p></div>
<a href="https://www.agenziaentrate.gov.it/portale/giugno-2024-circolari">Giugno</a>
<a href="https://www.agenziaentrate.gov.it/portale/web/guest/archivio/normativa-prassi-archivio-documentazione/circolari-territorio">Territorio</a>"""

ELENCO_INPS = {"data": {"results": [{"selectors": "circolari-e-messaggi.2026.11.circolare-numero-114-del-20-11-2026_16423",
                                     "path": "/content/dam/inps-site/it/scorporati/circolari-e-messaggi/2026/11/circolare-numero-114-del-20-11-2026_16423",
                                     "oggetto": "<p>Convenzione CONFENALP</p>", "numero": "114", "tipo": "Circolare"}]}}


def test_lettura_degli_elenchi_ufficiali():
    documenti = fonti.ade_documenti(PAGINA_ADE, "https://www.agenziaentrate.gov.it/portale/giugno-2024-circolari")
    assert [(d["tipo"], d["numero"], d["data"]) for d in documenti] == [("Circolare", "16", "2024-06-28"), ("Risoluzione", "45", "2026-11-13")]
    assert documenti[1]["url_testo"] == "https://www.agenziaentrate.gov.it/portale/documents/20143/1/Risoluzione+45.pdf"
    assert fonti.ade_collegamenti(PAGINA_ADE) == ["https://www.agenziaentrate.gov.it/portale/giugno-2024-circolari"]
    (inps,) = fonti.inps_documenti(ELENCO_INPS)
    assert (inps["tipo"], inps["numero"], inps["data"], inps["oggetto"]) == ("Circolare", "114", "2026-11-20", "Convenzione CONFENALP")
    assert inps["url_testo"].endswith("_16423/jcr:content/data/master.json")
    assert fonti.inps_url_elenco(0, 10).endswith(".30.3130.67696f726e6f.44455343.636972636f6c6172692d652d6d65737361676769.json")


def test_recupero_testi_e_ricerca(tmp_path, monkeypatch):
    archivio = ArchivioPrassi(tmp_path / "prassi.sqlite")
    monkeypatch.setattr(fonti, "ADE_PARTENZE", ("https://www.agenziaentrate.gov.it/portale/normativa-e-prassi/circolari",))
    monkeypatch.setattr(fonti, "testo_pdf", lambda contenuto: "CIRCOLARE N. 16/E. Compensazione dei crediti d'imposta: " + "chiarimenti " * 20)

    def scarica(url):
        if "search" in url:
            pagina = 0 if ".30." in url else 1
            return SimpleNamespace(status_code=200, content=json.dumps(ELENCO_INPS if pagina == 0 else {"data": {"results": []}}).encode())
        if url.endswith("master.json"):
            return SimpleNamespace(status_code=200, content=json.dumps({"testoCompleto": "<p>Premessa. La convenzione per la "
                                                                         "riscossione dei contributi sindacali " + "istruzioni " * 30 + "</p>"}).encode())
        if url.endswith(".pdf") or ".pdf/" in url:
            return SimpleNamespace(status_code=200, content=b"%PDF")
        return SimpleNamespace(status_code=200, content=PAGINA_ADE.encode())

    esito = esegui_tratto(archivio, scarica, tempo_massimo=600, pausa=0)
    assert esito["elenchi"] == {"agenzia_entrate": 2, "inps": 1} and esito["testi_nuovi"] == 3
    risultati = archivio.cerca("contributi sindacali")
    assert [r["ente"] for r in risultati] == ["INPS"] and "«" in risultati[0]["brano"]
    assert archivio.cerca("compensazione crediti", ente="Agenzia delle Entrate")[0]["numero"] == "16"
    # Secondo tratto: nulla di nuovo da leggere.
    assert esegui_tratto(archivio, scarica, tempo_massimo=600, pausa=0)["testi_nuovi"] == 0


def test_api_di_ricerca(tmp_path, monkeypatch):
    from flask import Flask, g

    from web.blueprints.api_v1_prassi import api_v1_prassi

    archivio = ArchivioPrassi(tmp_path / "prassi.sqlite")
    archivio.aggiungi([{"ente": "INPS", "tipo": "Messaggio", "numero": "3801", "data": "2026-11-19",
                        "oggetto": "Notifiche digitali SEND", "url": "https://www.inps.it/x.html", "url_testo": "https://www.inps.it/x.json"}])
    archivio.salva_testo("inps|messaggio|2026|3801", "Estensione delle notifiche digitali tramite piattaforma SEND agli indebiti.")
    app = Flask(__name__)
    app.config["PCT_PRASSI_DB"] = str(tmp_path / "prassi.sqlite")
    app.config["PCT_GA_TESTI_DB"] = str(tmp_path / "assente.sqlite")
    app.register_blueprint(api_v1_prassi)
    app.before_request(lambda: setattr(g, "utente_corrente", object()))
    client = app.test_client()
    risposta = client.get("/api/v1/ui/prassi?q=notifiche%20digitali").get_json()
    assert risposta["ok"] and risposta["items"][0]["numero"] == "3801"
    testo = client.get("/api/v1/ui/prassi/testo?id=inps|messaggio|2026|3801").get_json()
    assert "piattaforma SEND" in testo["text"]
    assert client.get("/api/v1/ui/giustizia-amministrativa/testi?q=appalti").get_json()["items"] == []
