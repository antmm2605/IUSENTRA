"""Controllo Studio (quadro unico) e Preparazione udienza guidata: flussi reali via API.

Base normativa della preparazione: artt. 183, 171-ter, 189, 127-ter e 309 c.p.c. (verifiche per tipo
di udienza); i termini assegnati dal giudice diventano scadenze dello scadenziario.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pct.agenda import TipoAppuntamento
from pct.clienti import TipoCliente
from pct.controllo_studio.voce import fascia, quando_etichetta
from pct.email_client import EmailRicevuta
from pct.fascicoli import TipoFascicolo
from pct.fatturazione import StatoParcella, VoceParcella
from pct.procedura_fasi.fonti import FONTI
from pct.scadenziario import TipoTermine
from pct.udienze import tipi
from tests.test_revisione_2410_sicurezza import _app
from tests.test_topbar_operational_api import _login
from web.helpers import get_agenda, get_clienti, get_email_pec, get_fascicoli, get_fatturazione, get_scadenziario
from web.services.controllo_studio_runtime import oggi_roma


def _semina(app) -> dict[str, str]:
    oggi = oggi_roma()
    with app.test_request_context("/"):
        cliente = get_clienti().nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Bianchi")
        fascicolo = get_fascicoli().nuovo(
            "Bianchi c. Condominio Aurora", TipoFascicolo.CIVILE, id_cliente=cliente.id, nome_cliente="Mario Bianchi",
            numero_rg="1234/2026", tribunale="Tribunale di Bari", giudice="Dott.ssa Neri",
        )
        domani = (oggi + timedelta(days=1)).isoformat()
        udienza = get_agenda().aggiungi(
            "Udienza Bianchi c. Condominio Aurora", TipoAppuntamento.UDIENZA, f"{domani}T10:00:00", 60, "Tribunale di Bari, aula 3",
            cliente="Mario Bianchi", id_cliente=cliente.id, procedimento="RG 1234/2026", tribunale="Tribunale di Bari",
        )
        scaduta = get_scadenziario().nuova(
            "Notifica atto di precetto", TipoTermine.NOTIFICA, (oggi - timedelta(days=1)).isoformat(), id_fascicolo=fascicolo.id, perentorio=True,
        )
        get_scadenziario().nuova("Termine appello", TipoTermine.IMPUGNAZIONE, (oggi + timedelta(days=12)).isoformat(), id_fascicolo=fascicolo.id)
        parcella = get_fatturazione().crea(
            cliente.id, [VoceParcella("Fase di studio", 1, 1000.0)], id_fascicolo=fascicolo.id,
            data_emissione=(oggi - timedelta(days=60)).isoformat(), data_scadenza=(oggi - timedelta(days=30)).isoformat(),
        )
        get_fatturazione().cambia_stato(parcella.id, StatoParcella.EMESSA)
        get_email_pec().aggiungi(EmailRicevuta(
            id="PEC1", mittente="avv.verdi@pec.it", mittente_nome="Avv. Verdi", oggetto="Proposta transattiva RG 1234/2026",
            data=datetime.now().isoformat(timespec="seconds"),
        ))
    return {"cliente": cliente.id, "fascicolo": fascicolo.id, "udienza": udienza.id, "scaduta": scaduta.id}


def _voce(payload: dict, area: str, parola: str) -> dict:
    return next(v for v in payload["voci"] if v["area"] == area and parola in v["titolo"])


def _azione(voce: dict, etichetta: str) -> dict:
    return next(a for a in voce["azioni"] if a["etichetta"] == etichetta)


def test_fasce_e_date_leggibili():
    oggi = oggi_roma()
    assert fascia((oggi - timedelta(days=3)).isoformat(), oggi) == "scaduto"
    assert fascia(oggi.isoformat(), oggi) == "oggi"
    assert fascia((oggi + timedelta(days=1)).isoformat(), oggi) == "domani"
    assert fascia((oggi + timedelta(days=6)).isoformat(), oggi) == "settimana"
    assert fascia((oggi + timedelta(days=20)).isoformat(), oggi) == "prossimi"
    assert fascia("", oggi) == "senza_data"
    assert quando_etichetta((oggi - timedelta(days=3)).isoformat(), oggi) == "Da 3 giorni"
    assert quando_etichetta((oggi + timedelta(days=5)).isoformat(), oggi) == "Tra 5 giorni"


def test_verifiche_di_legge_citano_fonti_verificate():
    for tipo in tipi.catalogo():
        for verifica in tipi.verifiche(tipo["value"], {}):
            norma = verifica["fonte"].get("norma")
            if norma:
                assert verifica["fonte"]["url"].startswith("https://www.normattiva.it/")
                assert verifica["fonte"]["estratto"]
    prima = {v["id"]: v for v in tipi.verifiche("prima_comparizione", {"comparizione_cliente": True})}
    assert prima["comparizione_cliente"]["fatta"] is True
    assert "183" in prima["comparizione_cliente"]["fonte"]["norma"]
    assert "cpc_309" in FONTI


def test_controllo_studio_un_solo_quadro_con_azioni_che_funzionano(tmp_path):
    app = _app(tmp_path)
    ids = _semina(app)
    with app.test_client() as client:
        _login(client)
        dati = client.get("/api/v1/ui/controllo-studio").get_json()
        assert dati["ok"] is True and dati["fonti_non_disponibili"] == []
        aree = {a["area"]: a for a in dati["aree"]}
        assert set(aree) == {"scadenze", "agenda", "notifiche", "comunicazioni", "incassi"}
        assert aree["scadenze"]["urgenti"] >= 1 and aree["incassi"]["totale"] == 1 and aree["comunicazioni"]["totale"] == 1
        assert "termine scaduto" in dati["riepilogo"] and "parcella scaduta" in dati["riepilogo"]
        assert dati["incassi"]["scaduto"] > 0

        scaduta = _voce(dati, "scadenze", "Notifica atto di precetto")
        assert scaduta["fascia"] == "scaduto" and scaduta["gravita"] == "critica"
        assert scaduta["fascicolo"]["etichetta"].startswith("R.G. 1234/2026")
        udienza = _voce(dati, "agenda", "Udienza Bianchi")
        assert udienza["fascia"] == "domani" and _azione(udienza, "Prepara l'udienza")["href"].startswith("/wizard-pro/")
        assert _azione(_voce(dati, "incassi", ""), "Registra incasso")["href"].startswith("/incassi-pagamenti?id_parcella=")

        fatto = client.post(_azione(scaduta, "Segna fatto")["endpoint"])
        assert fatto.status_code == 200 and fatto.get_json()["ok"] is True
        pec = _voce(dati, "comunicazioni", "Proposta transattiva")
        assert client.post(_azione(pec, "Segna letta")["endpoint"]).get_json()["ok"] is True

        dopo = client.get("/api/v1/ui/controllo-studio").get_json()
        assert not any("Notifica atto di precetto" in v["titolo"] for v in dopo["voci"] if v["fascia"] == "scaduto")
        assert not any(v["area"] == "comunicazioni" for v in dopo["voci"])
        assert client.post("/api/v1/ui/controllo-studio/scadenze/inesistente/completa").status_code == 404
    assert ids["scaduta"]


def test_preparazione_udienza_dal_quadro_all_esito_con_seguiti(tmp_path):
    app = _app(tmp_path)
    ids = _semina(app)
    oggi = oggi_roma()
    with app.test_client() as client:
        _login(client)
        elenco = client.get("/api/v1/ui/preparazione-udienza").get_json()
        riga = next(u for u in elenco["udienze"] if u["idAppuntamento"] == ids["udienza"])
        assert riga["stato"] == "Da preparare" and riga["idFascicolo"] == ids["fascicolo"]

        avviata = client.post("/api/v1/ui/preparazione-udienza/avvia", json={"idAppuntamento": ids["udienza"]}).get_json()
        assert avviata["ok"] is True and avviata["redirect"].endswith("/step/1")
        sid = avviata["redirect"].split("/")[2]
        # Riaprire la stessa udienza non crea una seconda preparazione.
        assert client.post("/api/v1/ui/preparazione-udienza/avvia", json={"idAppuntamento": ids["udienza"]}).get_json()["redirect"].split("/")[2] == sid

        scheda = client.get(f"/api/v1/ui/preparazione-udienza/{sid}").get_json()
        assert scheda["udienza"]["rg"] == "1234/2026" and len(scheda["passi"]) == 5
        assert any(t["titolo"] == "Termine appello" for t in scheda["termini"])

        def azione(nome, corpo):
            risposta = client.post(f"/api/v1/ui/preparazione-udienza/{sid}/{nome}", json=corpo)
            return risposta.status_code, risposta.get_json()

        stato, r = azione("passo", {"passo": 1, "campi": {"tipo_udienza": "prima_comparizione"}, "conferma": False})
        assert stato == 200, r
        assert {v["id"] for v in r["dati"]["verifiche"]} >= {"comparizione_cliente"}
        stato, r = azione("verifica", {"id": "comparizione_cliente", "fatta": True})
        assert stato == 200 and next(v for v in r["dati"]["verifiche"] if v["id"] == "comparizione_cliente")["fatta"] is True
        assert azione("verifica", {"id": "non_prevista", "fatta": True})[0] == 400
        stato, r = azione("documento-extra", {"etichetta": "Perizia di parte"})
        assert stato == 200 and r["dati"]["documenti"][-1]["etichetta"] == "Perizia di parte"
        stato, r = azione("documento", {"indice": len(r["dati"]["documenti"]) - 1, "stato": "pronto"})
        assert stato == 200 and r["dati"]["documenti"][-1]["stato"] == "pronto"
        assert azione("documento", {"indice": 99, "stato": "pronto"})[0] == 400
        assert azione("passo", {"passo": 1, "campi": {}, "conferma": True})[1]["dati"]["passi"][0]["fatto"] is True

        assert azione("esito", {"esito": "rinvio", "rinvioData": oggi.isoformat()})[0] == 400
        rinvio = (oggi + timedelta(days=40)).isoformat()
        termine = (oggi + timedelta(days=20)).isoformat()
        corpo = {"esito": "rinvio", "rinvioData": rinvio, "rinvioOra": "09:30", "noteVerbale": "Concessi i termini per le note.",
                 "termini": [{"descrizione": "Deposito note scritte", "data": termine, "perentorio": True}]}
        stato, r = azione("esito", corpo)
        assert stato == 200 and r["ok"] is True
        assert any("rinvio" in c for c in r["creati"]) and any("Deposito note scritte" in c for c in r["creati"])
        assert r["dati"]["completata"] is True and r["dati"]["esito"]["rinvioAgendaHref"]

        # Registrare di nuovo l'esito non duplica rinvio, scadenza e nota del fascicolo.
        corpo["termini"] = r["dati"]["esito"]["termini"]
        stato, di_nuovo = azione("esito", corpo)
        assert stato == 200 and di_nuovo["creati"] == []

    with app.test_request_context("/"):
        rinvii = [a for a in get_agenda().tutti() if str(a.data_ora).startswith(rinvio)]
        assert len(rinvii) == 1 and rinvii[0].data_ora.startswith(f"{rinvio}T09:30")
        nuove = [s for s in get_scadenziario().tutte(solo_aperte=False) if s.titolo == "Deposito note scritte"]
        assert len(nuove) == 1 and nuove[0].id_fascicolo == ids["fascicolo"] and nuove[0].data_scadenza.startswith(termine)
        fascicolo = get_fascicoli().get(ids["fascicolo"])
        assert str(fascicolo.data_prossima_udienza).startswith(rinvio)
        assert len([a for a in fascicolo.attivita if "[Preparazione udienza" in str(getattr(a, "note", ""))]) == 1
        originale = get_agenda().get(ids["udienza"])
        assert str(getattr(originale.stato, "value", originale.stato)) == "COMPLETATO"
