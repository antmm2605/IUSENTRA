"""Deposito tributario dal fascicolo: quadro NIR, controlli dei file, pacchetto, termini, depositi, apertura veloce."""

from __future__ import annotations

import io
import zipfile

from pct.fascicoli import TipoDocumento, TipoFascicolo
from pct.soggetti import RuoloSoggetto, TipoSoggetto
from tests.test_pat_formweb import pdf_pades
from tests.test_penale_pdp import pdf_testo
from tests.test_react_shell import _app

H = {"X-API-Key": "react-test-key"}


def _fascicolo(app):
    from pct.clienti import GestioneClienti, TipoCliente

    with app.app_context():
        rt = app.extensions["core_runtime"]
        cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
            TipoCliente.PERSONA_FISICA, nome="Anna", cognome="Verdi", codice_fiscale="VRDNNA80A41A662P")
        gf = rt["get_fascicoli"]()
        f = gf.nuovo("Verdi c/ Agenzia Entrate Bari", TipoFascicolo.TRIBUTARIO, nome_cliente="Verdi Anna", id_cliente=cliente.id,
                     tribunale="Corte di giustizia tributaria di primo grado di Bari")
        soggetti = rt["get_soggetti"]()
        agenzia = soggetti.crea(TipoSoggetto.PUBBLICA_AMMINISTRAZIONE, ragione_sociale="Agenzia delle Entrate - Direzione provinciale di Bari")
        soggetti.aggiungi_parte(f.id, agenzia.id, RuoloSoggetto.CONTROPARTE)
        ricorso = gf.aggiungi_documento(f.id, "Ricorso tributario.pdf", TipoDocumento.RICORSO, pdf_pades(pdf_testo("Ricorso")), firmato=True)
        avviso = gf.aggiungi_documento(f.id, "Avviso di accertamento TK1.pdf", TipoDocumento.ALLEGATO, pdf_testo("Avviso"))
        foto = gf.aggiungi_documento(f.id, "Fotografie.zip", TipoDocumento.ALLEGATO, b"PK\x03\x04zip")
        return f.id, {"ricorso": ricorso, "avviso": avviso, "zip": foto}


def test_quadro_nir_e_procedimento(tmp_path):
    app = _app(tmp_path)
    fid, docs = _fascicolo(app)
    base = f"/api/v1/ui/tributario/fascicoli/{fid}"
    with app.test_client() as client:
        quadro = client.get(base, headers=H).get_json()
        assert quadro["ok"] and quadro["procedimento"]["corte"] == "PBA" and quadro["tipoSuggerito"] == "ricorso"
        assert quadro["parti"]["ricorrenti"][0]["natura"] == "F01"
        assert quadro["parti"]["resistenti"][0]["tipoEnte"] == "Agenzie fiscali"
        documenti = {d["id"]: d for d in quadro["documenti"]}
        assert documenti[docs["ricorso"].id]["ruolo"] == "atto" and documenti[docs["ricorso"].id]["firma"] == "pades"
        assert documenti[docs["avviso"].id]["tipologia"] == "ATTO IMPUGNATO"
        assert documenti[docs["zip"].id]["bloccante"]

        salvato = client.post(f"{base}/procedimento", headers=H, json={
            "notificaRicorso": "2026-07-20", "cutModalita": "F23",
            "atti": [{"tipo": "AVVISO DI ACCERTAMENTO", "numero": "TK1", "dataNotifica": "2026-06-01", "tributo": "12.000,00",
                      "materia": "Accertamento imposte", "tributo_tipo": "IRPEF"}]}).get_json()
        assert salvato["cut"]["totale"] == 120 and salvato["termini"][0]["scadenza"] == "2026-09-21"
        righe = {r["etichetta"]: r for s in salvato["scheda"]["sezioni"] for r in s["righe"]}
        assert righe["Codice ufficio F23"]["valore"] and righe["CUT dovuto"]["valore"] == "€ 120,00"
        assert client.post(f"{base}/procedimento", headers=H, json={"atti": [{"tipo": "INVENTATO"}]}).status_code == 400
        assert client.post(f"{base}/procedimento", headers=H, json={"corte": "XYZ"}).status_code == 400

        client.post(f"{base}/documenti/{docs['zip'].id}", headers=H, json={"ruolo": "escludi"})
        controllo = client.post(f"{base}/controllo", headers=H).get_json()
        file = {f["id"]: f for f in controllo["file"]}
        assert docs["zip"].id not in file
        assert {e["codice"] for e in file[docs["avviso"].id]["esiti"]} == {"PDFA"}
        assert controllo["conforme"]

        pacchetto = client.get(f"{base}/pacchetto", headers=H)
        nomi = zipfile.ZipFile(io.BytesIO(pacchetto.data)).namelist()
        assert nomi[0].startswith("01 Ricorso tributario") and "Indice deposito PTT.csv" in nomi and len(nomi) == 3

        primo = client.post(f"{base}/termini/costituzione", headers=H).get_json()
        secondo = client.post(f"{base}/termini/costituzione", headers=H).get_json()
        assert primo["gia"] is False and secondo["gia"] is True and primo["scadenza"] == "2026-09-21"

        depositato = client.post(f"{base}/depositi", headers=H, json={"tipo": "ricorso", "stato": "depositata", "rg": "123/2026"})
        assert depositato.status_code == 200
        dopo = client.post(f"{base}/procedimento", headers=H, json={"rg": "123/2026"}).get_json()
        assert dopo["tipoSuggerito"] == "altri-atti" and dopo["depositi"][0]["stato"] == "depositata"
        assert client.post(f"{base}/depositi", headers=H, json={"tipo": "ricorso", "stato": "inventato"}).status_code == 400

        pagina = client.get(f"/api/v1/ui/fascicoli/{fid}", headers=H).get_json()
        assert pagina["telematic"][0]["href"].endswith("#ptt-sigit")
        panoramica = client.get("/api/v1/ui/tributario/panoramica", headers=H).get_json()
        assert panoramica["fascicoli"][0]["id"] == fid and panoramica["fascicoli"][0]["corte"].endswith("di Bari")


def test_non_tributario_e_connessione(tmp_path, monkeypatch):
    from web.services import ptt_sigit_azioni

    app = _app(tmp_path)
    with app.app_context():
        f = app.extensions["core_runtime"]["get_fascicoli"]().nuovo("Civile", TipoFascicolo.CIVILE)
    monkeypatch.setattr(ptt_sigit_azioni, "_leggi", lambda url, limite: (200, b"<html>Processo Tributario Telematico</html>"))
    ptt_sigit_azioni._CONNESSIONE.clear()
    with app.test_client() as client:
        assert client.get(f"/api/v1/ui/tributario/fascicoli/{f.id}", headers=H).status_code == 400
        assert client.get("/api/v1/ui/tributario/fascicoli/ZZZ", headers=H).status_code == 404
        esito = client.get("/api/v1/ui/tributario/connessione", headers=H).get_json()
        assert esito["raggiungibile"] is True and esito["url"].startswith("https://sigit.finanze.it")
        catalogo = client.get("/api/v1/ui/tributario/catalogo-apertura?ufficio=CTP%20Bari", headers=H).get_json()
        assert catalogo["corte"]["codice"] == "PBA"


def test_fascicolo_veloce_tributario_apre_il_ptt(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"})
        risposta = client.post("/fascicoli/nuovo", headers={**H, "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}, data={
            "titolo": "Bianchi c/ Comune di Lecce", "tipo": "TRIBUTARIO", "oggetto": "Avviso IMU 2021", "fascicolo_veloce": "1",
            "controparte": "Comune di Lecce", "ptt_corte": "PLE", "ptt_atto_tipo": "AVVISO DI ACCERTAMENTO", "ptt_atto_numero": "IMU21",
            "ptt_valore": "4.000,00", "ptt_notifica_ricorso": "2026-09-01"})
        assert risposta.status_code in {200, 201, 302}, risposta.get_data(as_text=True)[:400]
        corpo = risposta.get_json(silent=True) or {}
        destinazione = corpo.get("redirect") or corpo.get("target") or risposta.headers.get("Location", "")
        assert destinazione.endswith("#ptt-sigit"), corpo
