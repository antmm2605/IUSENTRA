"""Deposito penale PDP dal fascicolo: quadro, catalogo, preparazione, ricevuta, esito, import."""

from __future__ import annotations

import io
from datetime import date, timedelta

from pct.fascicoli import TipoDocumento, TipoFascicolo
from tests.test_penale_pdp import _pdf_ricevuta, _xlsx, p7m, pdf_testo
from tests.test_react_shell import _app

H = {"X-API-Key": "react-test-key"}


def _fascicolo(app):
    with app.app_context():
        gf = app.extensions["core_runtime"]["get_fascicoli"]()
        f = gf.nuovo("Stato c/ Bianchi", TipoFascicolo.PENALE, nome_cliente="Mario Bianchi",
                     tribunale="Procura della Repubblica presso il Tribunale di Palmi", numero_rg="1096", anno_rg=2023)
        gf.aggiorna(f.id, qualifica_giudiziale_titolare="Indagato")
        nomina = gf.aggiungi_documento(f.id, "nomina.pdf.p7m", TipoDocumento.ATTO_GIUDIZIARIO, p7m(pdf_testo()))
        verbale = gf.aggiungi_documento(f.id, "verbale identificazione.pdf", TipoDocumento.VERBALE, pdf_testo("Verbale di identificazione"))
        return f.id, nomina.id, verbale.id


def test_flusso_completo_deposito_penale(tmp_path):
    app = _app(tmp_path)
    fid, nomina, verbale = _fascicolo(app)
    base = f"/api/v1/ui/penale/fascicoli/{fid}"
    with app.test_client() as client:
        quadro = client.get(base, headers=H).get_json()
        assert quadro["ok"] and quadro["procedimento"]["ufficio"] == "PM-U"
        assert quadro["registri"][0]["protocollo"] == "PM: N2023/1096"
        assert quadro["soggetti"][0]["ruolo"] == "IND" and quadro["canale"]["obbligatorio"] is True
        soggetto = quadro["soggetti"][0]["id"]

        atti = client.get(f"{base}/atti?principali=1", headers=H).get_json()["atti"]
        assert "P02" in {a["codice"] for a in atti}
        scheda = client.get("/api/v1/ui/penale/atti/P02?ufficio=PM-U&ruoli=IND", headers=H).get_json()
        assert scheda["atto"]["principale"] and scheda["contestuali"]

        richiesta = {"atto": "P02", "ufficio": "PM-U", "soggetti": [soggetto],
                     "file": [{"documentoId": nomina, "ruolo": "principale"}]}
        bozza = client.post(f"{base}/depositi", json=richiesta, headers=H).get_json()
        assert bozza["deposito"]["stato"] == "BOZZA"
        assert "ABILITANTE" in [e["codice"] for e in bozza["deposito"]["controlli"]["esiti"]]
        did = bozza["deposito"]["id"]

        richiesta["file"].append({"documentoId": verbale, "ruolo": "abilitante", "oggetto": "Verbale di identificazione"})
        pronto = client.post(f"{base}/depositi/{did}", json=richiesta, headers=H).get_json()
        assert pronto["deposito"]["stato"] == "PRONTO", pronto["deposito"]["controlli"]
        titoli = [s["titolo"] for s in pronto["scheda"]["sezioni"]]
        assert titoli[:3] == ["Dove", "Ufficio destinazione", "Identificazione procedimento"]

        righe = [
            ["MINISTERO della GIUSTIZIA"], ["IDENTIFICA", "TIV", "O 2026/0012345 POR", "T", "ALE DEPOSITO atti PENALI"],
            ["L'avvocato ROSSI MARIO RSSMRA80A01H501U ha inviato all'ufficio PROCURA DELLA REPUBBLICA PRESSO IL TRIBUNALE DI P", "ALMI in data"],
            ["24/09/2026 alle ore 18:10:00, in relazione al pr", "ocedimento: REGISTRO NOTI PM nr. 1096/2023, l'atto di Nomina a difensore di"],
            ["fiducia, nell'interesse dei seguenti soggetti rappresentati, in qualità di IND./IMP./RESP.AMM.: BIANCHI MARIO 01/01/1980"],
            ["con nr. 0 allegati"], ["Roma, 24/09/2026 18:10"],
        ]
        ricevuta = client.post(f"{base}/depositi/{did}/ricevuta", headers=H, content_type="multipart/form-data",
                               data={"ricevuta": (io.BytesIO(_pdf_ricevuta(righe)), "ricevuta.pdf")}).get_json()
        assert ricevuta["ok"], ricevuta
        dep = ricevuta["deposito"]
        assert dep["identificativo"] == "2026/0012345" and dep["stato"] == "INVIATO" and dep["dataInvio"] == "2026-09-24T18:10:00"
        verifica = dep["verificaRicevuta"]
        assert verifica["totale"] >= 5 and verifica["corrispondenti"] == verifica["totale"], verifica
        assert dep["ricevutaId"]

        altro = [["Il deposito con IDENTIFICATIVO 2026/0099999, inviato all'ufficio PROCURA DI PALMI in data 24/09/2026 alle ore 18:10,"],
                 ["è stato accettato in data 25/09/2026 alle ore 09:00"]]
        sbagliata = client.post(f"{base}/depositi/{did}/ricevuta", headers=H, content_type="multipart/form-data",
                                data={"ricevuta": (io.BytesIO(_pdf_ricevuta(altro)), "esito.pdf")})
        assert sbagliata.status_code == 400 and "2026/0099999" in sbagliata.get_json()["message"]

        esito = client.post(f"{base}/depositi/{did}/stato", json={"stato": "Accettato"}, headers=H).get_json()
        assert esito["deposito"]["stato"] == "ACCOLTO"
        assert client.get(base, headers=H).get_json()["procedimento"]["autorizzato"] is True

        export = _xlsx([["Ident. Invio", "Data Invio", "Data Arrivo", "Num. Registro", "Ufficio", "Magistrato", "Soggetti Rappr.", "Tipo Atto", "Stato"],
                        ["2026/0012345", "24/09/2026 18:10", "24/09/2026 18:12", "PM: N2023/1096", "PROCURA DI PALMI", "", "M. B.",
                         "Nomina difensore di fiducia (artt. 96, 100, 101 cpp)", "Rifiutato"],
                        ["2025/0000001", "01/02/2025 10:00", "", "PM: N2024/9", "PROCURA DI PALMI", "", "X. Y.", "Memorie difensive (artt. 121, 367 cpp)", "Accolto"]])
        anteprima = client.post(f"{base}/import", headers=H, content_type="multipart/form-data",
                                data={"export": (io.BytesIO(export), "depositi.xlsx"), "anteprima": "1"}).get_json()
        assert anteprima["tipo"] == "depositi" and anteprima["pertinenti"] == 1 and anteprima["ignorate"] == 1
        fatto = client.post(f"{base}/import", headers=H, content_type="multipart/form-data",
                            data={"export": (io.BytesIO(export), "depositi.xlsx"), "anteprima": "0"}).get_json()
        assert fatto["aggiornati"] == 1
        depositi = client.get(base, headers=H).get_json()["depositi"]
        assert depositi[0]["stato"] == "RIGETTATO"

        giorno = (date.today() + timedelta(days=30)).strftime("%d/%m/%Y")
        udienze = f"Data e ora;Tipo ufficio;Aula;Luogo;Causale\n{giorno} 09:30;DIB;2;Palmi;Prima udienza\n01/01/2020 09:00;GIP;1;Palmi;Udienza preliminare\n"
        importate = client.post(f"{base}/import", headers=H, content_type="multipart/form-data",
                                data={"export": (io.BytesIO(udienze.encode()), "udienze.csv"), "anteprima": "0"}).get_json()
        assert importate["tipo"] == "udienze" and importate["importati"] == 2 and importate["inAgenda"] == 1


def test_non_penale_e_permessi(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        gf = app.extensions["core_runtime"]["get_fascicoli"]()
        civile = gf.nuovo("Rossi c/ Verdi", TipoFascicolo.CIVILE, nome_cliente="Rossi")
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/penale/fascicoli/{civile.id}", headers=H)
        assert risposta.status_code == 400
        assert client.get("/api/v1/ui/penale/fascicoli/inesistente", headers=H).status_code == 404
        assert client.get(f"/api/v1/ui/penale/fascicoli/{civile.id}").status_code == 401


def test_pagina_pdp_e_centro_telematico_con_la_nuova_logica(tmp_path):
    app = _app(tmp_path)
    fid, nomina, verbale = _fascicolo(app)
    with app.test_client() as client:
        vuota = client.get("/api/v1/ui/penale/panoramica", headers=H).get_json()
        assert vuota["ok"] and vuota["totali"]["procedimenti"] == 1
        assert vuota["procedimenti"][0]["azione"]["codice"] in {"REGISTRO", "NOMINA"}
        base = f"/api/v1/ui/penale/fascicoli/{fid}"
        soggetto = client.get(base, headers=H).get_json()["soggetti"][0]["id"]
        client.post(f"{base}/depositi", headers=H, json={"atto": "P02", "ufficio": "PM-U", "soggetti": [soggetto],
                                                        "file": [{"documentoId": nomina, "ruolo": "principale"}]})
        dati = client.get("/api/v1/ui/penale/panoramica", headers=H).get_json()
        riga = dati["procedimenti"][0]
        assert riga["href"] == f"/fascicoli/{fid}#penale-pdp" and riga["protocollo"] == "PM: N2023/1096"
        assert riga["azione"]["codice"] == "COMPLETARE" and dati["totali"]["inPreparazione"] == 1
        assert any(v["inVigore"] for v in dati["calendario"]) and dati["link"]["pdp"].startswith("https://servizipst")

        telematico = client.get("/api/v1/ui/telematico", headers=H).get_json()
        canali = telematico.get("channels") or telematico.get("data", {}).get("channels")
        pdp = next(c for c in canali if c["id"] == "pdp")
        assert [m["label"] for m in pdp["metrics"]] == ["Procedimenti", "In attesa di esito", "Da fare"]
        assert pdp["metrics"][0]["value"] == 1 and pdp["quickActions"][0]["href"] == "/pdp"
        assert "acquisizione" not in pdp["importHref"]
        assert pdp["lastSyncAt"] == "" and "CNS/CIE" in pdp["environmentLabel"]
