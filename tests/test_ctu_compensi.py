"""Modulo CTU/ausiliari: vacazioni (L. 319/1980, Corte cost. 16/2025), tabella D.M. 30/05/2002,
compenso (D.P.R. 115/2002 artt. 51-53), termini della liquidazione (artt. 71 e 170), operazioni
peritali e bozza dell'istanza di liquidazione dal fascicolo."""

from __future__ import annotations

import pytest

from pct.ctu import GestioneCtu, proposte_scadenze_incarico
from pct.ctu_compensi.onorari import compenso, forbice_voce
from pct.ctu_compensi.tabella_dm_2002 import VOCI, elenco
from pct.ctu_compensi.termini import termine_istanza, termine_opposizione
from pct.ctu_compensi.vacazioni import conteggio_giornaliero, onorario_vacazioni, vacazioni_da_minuti


def test_vacazioni_da_due_ore_divisibili_solo_a_meta():
    assert vacazioni_da_minuti(120) == 1
    assert vacazioni_da_minuti(150) == 1.5
    assert vacazioni_da_minuti(195) == 1.5  # resto di un'ora e un quarto: ancora metà
    assert vacazioni_da_minuti(196) == 2  # trascorsa un'ora e un quarto è dovuta per intero
    assert vacazioni_da_minuti(0) == 0


def test_tetto_di_quattro_al_giorno_salvo_presenza_del_giudice():
    esito = conteggio_giornaliero([
        {"data": "2026-10-05", "minuti": 600},
        {"data": "2026-10-05", "minuti": 120, "presenza_giudice": True},
        {"data": "2026-10-06", "minuti": 90},
    ])
    assert [g["vacazioni"] for g in esito["giorni"]] == [5, 1]
    assert esito["vacazioni"] == 6 and esito["escluse_per_tetto"] == 1


def test_ogni_vacazione_vale_quanto_la_prima_e_urgenza():
    assert onorario_vacazioni(5)["onorario"] == 73.4  # 5 × 14,68 (Corte cost. 16/2025)
    assert onorario_vacazioni(5, termine_giorni=5)["onorario"] == 146.8
    assert onorario_vacazioni(4, termine_giorni=12)["onorario"] == 88.08
    assert onorario_vacazioni(4, termine_giorni=12, aumento_urgenza=1.2)["fattore_urgenza"] == 1.2
    assert onorario_vacazioni(4, termine_giorni=30)["fattore_urgenza"] == 1.0


def test_tabella_a_scaglioni_progressivi_e_minimi():
    edilizia = forbice_voce("11", 20000)
    assert (edilizia["minimo"], edilizia["massimo"]) == (944.87, 1891.38)
    piccolo = forbice_voce("2", 1000)
    assert piccolo["minimo"] == piccolo["massimo"] == 145.12
    assert any("minimo" in n for n in piccolo["note"])
    aziende = forbice_voce("3", 20000)
    assert abs(aziende["massimo"] - forbice_voce("2", 20000)["massimo"] / 2) <= 0.01
    oltre = forbice_voce("17", 60000)
    assert any("si ferma" in n for n in oltre["note"])
    with pytest.raises(ValueError, match="valore"):
        forbice_voce("11", 0)


def test_reperti_successivi_ridotti():
    armi = forbice_voce("18", quantita=3)
    assert armi["minimo"] == round(48.03 + 2 * 48.03 / 3, 2)
    assert armi["massimo"] == round(145.12 + 2 * 145.12 * 2 / 3, 2)
    assert forbice_voce("22", quantita=4)["minimo"] == 57.84


def test_elenco_copre_la_tabella():
    codici = [v["value"] for v in elenco()]
    assert codici == list(VOCI) and "28ter" in codici and "4B" in codici


def test_compenso_con_aumenti_collegio_e_accessori():
    esito = compenso({"modalita": "tabella", "voci": [{"codice": "11", "valore": "20000"}], "posizione": 50,
                      "aumento_eccezionale": "1,5", "motivazione_aumento": "Accertamenti su tre edifici",
                      "componenti_collegio": 2, "contributo_perc": 4, "iva_perc": 22, "spese_documentate": "100"})
    base = round(944.87 + (1891.38 - 944.87) / 2, 2)
    assert esito["onorario_base"] == base
    assert esito["onorario"] == round(round(base * 1.5, 2) * 1.4, 2)
    assert esito["contributo"] == round(esito["onorario"] * 0.04, 2)
    assert esito["totale"] == round(esito["onorario"] + esito["contributo"] + esito["iva"] + 100, 2)
    with pytest.raises(ValueError, match="motivato"):
        compenso({"modalita": "tabella", "voci": [{"codice": "5"}], "aumento_eccezionale": 2})
    ritardo = compenso({"modalita": "vacazioni", "vacazioni": 3, "ritardo": True, "iva_perc": 0})
    assert ritardo["onorario"] == round(3 * 14.68 * 2 / 3, 2)
    patrocinio = compenso({"modalita": "vacazioni", "vacazioni": 3, "patrocinio": "civile", "iva_perc": 0})
    assert patrocinio["onorario"] == 44.04 and any("166/2022" in n for n in patrocinio["note"])


def test_termini_della_liquidazione():
    assert termine_istanza("2026-10-01")["data"] == "2027-01-09"
    assert termine_opposizione("2026-10-01")["data"] == "2026-10-31"
    assert termine_istanza("") is None


def test_incarico_operazioni_e_proposte_di_legge(tmp_path):
    gestione = GestioneCtu(db_path=str(tmp_path / "ctu.json"))
    incarico = gestione.nuovo(fascicolo_id="F1", ruolo_studio="AUSILIARIO", nome_ctu="Ing. Bruni", data_nomina="2026-06-01")
    gestione.aggiungi_operazione(incarico.id, {"data": "2099-01-10", "ora": "10:00", "tipo": "sopralluogo", "minuti": 150,
                                               "luogo": "Via Roma 1"})
    with pytest.raises(ValueError, match="data"):
        gestione.aggiungi_operazione(incarico.id, {"data": "10/01/2099"})
    gestione.aggiorna(incarico.id, data_deposito_relazione="2026-10-01", data_comunicazione_decreto="2026-10-20")
    with pytest.raises(ValueError, match="data_comunicazione_decreto"):
        gestione.aggiorna(incarico.id, data_comunicazione_decreto="20/10/2026")
    riletto = GestioneCtu(db_path=str(tmp_path / "ctu.json")).get(incarico.id)
    chiavi = [p["chiave"].rsplit(":", 1)[-1] for p in proposte_scadenze_incarico(riletto)]
    assert chiavi[:2] == ["istanza_liquidazione", "opposizione_decreto"] and chiavi[2].startswith("operazione-")
    assert [t["chiave"] for t in riletto.timeline()][-2:] == ["relazione_depositata", "decreto"]
    parte = gestione.nuovo(fascicolo_id="F1", ruolo_studio="PARTE", nome_ctu="Ing. Bruni", data_deposito_relazione="2026-10-01")
    assert proposte_scadenze_incarico(parte) == []  # l'istanza la presenta il CTU
    assert gestione.rimuovi_operazione(incarico.id, riletto.operazioni[0]["id"]) is True


def test_rotte_dal_fascicolo(tmp_path):
    from pct.fascicoli import TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_fascicoli

    app = _app(tmp_path)
    with app.test_request_context("/"):
        fascicolo = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE)
    h = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    with app.test_client() as client:
        _login(client)
        creato = client.post(f"/fascicoli/{fascicolo.id}/ctu/nuovo", json={"ruoloStudio": "AUSILIARIO", "nomeCtu": "Ing. Bruni",
                                                                          "dataNomina": "2026-06-01"}, headers=h).get_json()
        iid = creato["incarico"]["id"]
        base = f"/fascicoli/{fascicolo.id}/ctu/{iid}"
        assert client.get("/api/v1/ui/ctu/tabella", headers=h).get_json()["voci"]
        assert client.post(f"{base}/operazioni", json={"data": "2026-07-01", "minuti": 300}, headers=h).get_json()["ok"]
        assert client.post(f"{base}/operazioni", json={"data": "2026-07-02", "minuti": 90}, headers=h).get_json()["ok"]
        payload = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/ctu", headers=h).get_json()["incarichi"][0]
        assert payload["vacazioniRegistro"]["vacazioni"] == 3.5 and len(payload["operazioni"]) == 2
        conto = client.post(f"{base}/compenso", json={"modalita": "vacazioni", "iva_perc": 0}, headers=h).get_json()
        assert conto["ok"] and conto["onorario"] == round(3.5 * 14.68, 2)
        assert client.post(f"{base}/compenso", json={"modalita": "tabella", "voci": []}, headers=h).status_code == 400
        aggiornato = client.post(f"{base}/aggiorna", json={"stato": "DEPOSITATA", "dataDepositoRelazione": "2026-09-15"}, headers=h).get_json()
        assert aggiornato["incarico"]["dataDepositoRelazione"] == "2026-09-15"
        istanza = client.post(f"{base}/istanza", json={"modalita": "tabella", "voci": [{"codice": "11", "valore": "20000"}]},
                              headers=h).get_json()
        assert istanza["ok"] and istanza["url"].endswith("/editor")
        proposte = client.post(f"{base}/proponi-scadenze", json={}, headers=h).get_json()
        assert proposte["creati"] == 1  # istanza di liquidazione entro 100 giorni
        estraneo = client.post(f"/fascicoli/ALTRO/ctu/{iid}/operazioni", json={"data": "2026-07-01"}, headers=h)
        assert estraneo.status_code == 404
    with app.test_request_context("/"):
        documenti = get_fascicoli().get(fascicolo.id).documenti
        assert any("istanza_liquidazione_ctu" in d.nome for d in documenti)
