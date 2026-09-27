"""Migrazione React della ex cabina `/applicazioni`.

- le 14 funzioni che la vista storica serviva solo nella cabina (utility e
  verifiche) hanno la pagina React `/applicazioni/<id>`: i calcoli restano
  quelli di `web/services/applicazioni_runtime._utility_result`, confrontati
  qui sia con la funzione sia con la vista storica (POST `/applicazioni/`);
- le voci che nella vista storica rispondevano «Presidio operativo attivo» a
  qualunque input non inventano risultati: la pagina le dichiara non disponibili;
- le voci di calcolo forense rimandano a Strumenti forensi con lo strumento, il
  preset di `TOOL_PRESET_OVERRIDES` e il precompilato della pratica;
- `/applicazioni` e `/applicazioni/<id>` sono servite dalla shell React, la vista
  storica resta raggiungibile con `?_legacy=1`.
"""

from __future__ import annotations

import html

import pytest

from pct.applicazioni_catalogo import get_applicazione
from tests.test_revisione_2410_sicurezza import _app as _app_sessione
from tests.test_topbar_operational_api import _create_user, _login

HTML = {"Accept": "text/html"}

# Funzione -> valori del modulo storico e righe attese (etichetta -> valore).
CASI_CALCOLO = {
    "calcolo_giorni_lavorativi": (
        {"utility_data_inizio": "2026-04-01", "utility_data_fine": "2026-04-30"},
        {"Giorni": "29", "Giorni lavorativi": "21", "Solo lun-ven": "22"},  # 6 aprile 2026: lunedì dell'Angelo
    ),
    "calcolo_eta_anagrafica": (
        {"utility_data_inizio": "1980-05-20", "utility_data_fine": "2026-09-27"},
        {"Età": "46 anni e 4 mesi"},
    ),
    "conversione_minuti_in_centesimi": ({"utility_minuti": "90"}, {"Ore centesimali": "1,50"}),
    "variazione_media_fatturato": (
        {"utility_valori": "100; 110; 121"},
        {"Periodi": "3", "Variazione media": "+10,00%", "Complessiva": "+21,00%"},
    ),
    "calcolo_ora_inizio_fine_attivita": (
        {"utility_ora_inizio": "09:00", "utility_ora_fine": "17:30", "utility_pausa": "30"},
        {"Durata lorda": "8h 30m", "Durata netta": "8h 00m", "Ore centesimali": "8,00"},
    ),
    "calcolatore_per_frazioni": (
        {"utility_frazione_a": "3/4", "utility_operazione": "+", "utility_frazione_b": "1/6"},
        {"Risultato": "11/12", "Decimale": "0,916667"},
    ),
    "conversione_unita_di_misura": (
        {"utility_valore": "25000", "utility_conversione": "mq_ettari"},
        {"Risultato": "2,5 ha"},
    ),
    "verifica_partita_iva": ({"utility_codice": "12345678903"}, {"Esito": "Formalmente valida"}),
    "verifica_iban": ({"utility_codice": "IT60X0542811101000000123456"}, {"Esito": "Formalmente valido"}),
}
NON_DISPONIBILI = ("decurtazione_punti_patente", "calcolo_tasso_alcolemico", "ricerca_codici_ateco", "cronometro_online")
QUATTORDICI = (*CASI_CALCOLO, "ricerca_comuni", *NON_DISPONIBILI)
SENZA_STRUMENTO = {
    "termini_processuali_civili": "termini_processuali",
    "termini_deposito_atti_appello": "impugnazioni",
    "calcolo_notula_penale": "onorari_forensi",
    "calcolo_spese_di_mediazione": "indennita_mediazione",
    "tariffe_mediazione": "indennita_mediazione",
    "calcolo_compenso_a_ore": "compenso_a_tempo",
    "calcolo_ravvedimento_operoso": "ravvedimento_operoso",
}


def _esegui(client, app_id: str, valori: dict):
    return client.post(f"/api/v1/ui/applicazioni/{app_id}/esegui", json={"values": valori})


@pytest.mark.parametrize("app_id", sorted(CASI_CALCOLO))
def test_utility_in_pagina_danno_il_risultato_della_vista_storica(tmp_path, app_id):
    from web.services.applicazioni_runtime import _utility_result

    valori, attese = CASI_CALCOLO[app_id]
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        scheda = client.get(f"/api/v1/ui/applicazioni/{app_id}").get_json()
        assert scheda["ok"] is True and scheda["item"]["type"] in {"utility", "lookup"}
        nomi = {campo["name"] for campo in scheda["item"]["form"]["fields"]}
        assert set(valori) <= nomi, nomi

        risposta = _esegui(client, app_id, valori)
        assert risposta.status_code == 200
        esito = risposta.get_json()
        assert esito["ok"] is True, esito
        righe = {riga["label"]: riga["value"] for riga in esito["rows"]}
        for etichetta, valore in attese.items():
            assert righe.get(etichetta) == valore, (etichetta, righe)

        # Stesso calcolo della funzione storica...
        storico = _utility_result(get_applicazione(app_id), valori)
        assert [(m["label"], m["value"]) for m in storico["metrics"]] == [(r["label"], r["value"]) for r in esito["rows"]]
        assert storico["notes"] == esito["notes"]
        # ...e della vista storica.
        pagina = client.post("/applicazioni/", data={"app": app_id, "app_id": app_id, **valori})
        testo = html.unescape(pagina.get_data(as_text=True))
        assert pagina.status_code == 200
        for valore in attese.values():
            assert valore in testo, (app_id, valore)


def test_verifiche_formali_segnalano_i_codici_non_validi(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        piva = _esegui(client, "verifica_partita_iva", {"utility_codice": "12345678901"}).get_json()
        iban = _esegui(client, "verifica_iban", {"utility_codice": "IT60X0542811101000000123457"}).get_json()
    assert {r["label"]: r["value"] for r in piva["rows"]}["Esito"] == "Non valida"
    assert {r["label"]: r["value"] for r in iban["rows"]}["Esito"] == "Non valido"


def test_dati_mancanti_restituiscono_la_nota_della_vista_storica(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        esito = _esegui(client, "calcolo_ora_inizio_fine_attivita", {"utility_ora_inizio": "nove"}).get_json()
        # I campi non dichiarati dal modulo non arrivano al calcolo.
        filtrato = _esegui(client, "conversione_minuti_in_centesimi", {"utility_minuti": "30", "altro": "x"}).get_json()
    assert esito["ok"] is False and esito["rows"] == []
    assert esito["message"] == "Inserisci le ore nel formato HH:MM (es. 09:30)."
    assert filtrato["ok"] is True


def test_ricerca_comuni_usa_la_banca_dati_istat(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        scheda = client.get("/api/v1/ui/applicazioni/ricerca_comuni").get_json()["item"]
        esito = _esegui(client, "ricerca_comuni", {"q": "Bari"}).get_json()
        breve = _esegui(client, "ricerca_comuni", {"q": "B"}).get_json()
    assert scheda["type"] == "lookup" and "ISTAT" in scheda["basis"]
    assert esito["ok"] is True
    bari = next(riga for riga in esito["rows"] if riga["label"] == "Bari (BA)")
    assert bari["value"].startswith("ISTAT ") and "Puglia" in bari["note"]
    assert breve["ok"] is False


@pytest.mark.parametrize("app_id", NON_DISPONIBILI)
def test_voci_senza_calcolo_non_inventano_risultati(tmp_path, app_id):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        item = client.get(f"/api/v1/ui/applicazioni/{app_id}").get_json()["item"]
        esito = _esegui(client, app_id, {"utility_query": "prova"}).get_json()
    assert item["type"] == "non_disponibile" and item["form"] is None
    assert item["unavailable"]["reason"] and item["unavailable"]["href"].startswith("/")
    assert esito["ok"] is False and esito["rows"] == []
    assert "Presidio operativo attivo" not in str(esito)


def test_voce_strumento_porta_preset_e_precompilato_della_pratica(tmp_path):
    from pct.fascicoli import TipoFascicolo
    from web.helpers import get_fascicoli

    app = _app_sessione(tmp_path)
    with app.app_context():
        pratica = get_fascicoli().nuovo(
            "Recupero credito Beta", TipoFascicolo.CIVILE, tribunale="Tribunale di Bari",
            numero_rg="77", anno_rg=2026, valore_causa=12500.0,
        )
    with app.test_client() as client:
        _login(client)
        mora = client.get("/api/v1/ui/applicazioni/calcolo_interessi_di_mora").get_json()["item"]
        assert mora["type"] == "tool" and mora["toolId"] == "interessi"
        assert mora["preset"] == {"int_tipo": "mora_commerciale"}
        assert mora["href"].startswith("/strumenti-legali/?tool=interessi&app=calcolo_interessi_di_mora")
        # Il preset vale solo per i campi dello strumento collegato.
        tabella = client.get("/api/v1/ui/applicazioni/tabella_interessi_di_mora").get_json()["item"]
        assert tabella["toolId"] == "tabella_tassi" and tabella["preset"] == {}

        con_pratica = client.get(f"/api/v1/ui/applicazioni/calcolo_interessi_di_mora?id_fascicolo={pratica.id}").get_json()
        assert con_pratica["item"]["fascicolo"]["id"] == pratica.id
        assert con_pratica["item"]["prefill"]["int_capitale"] in {"12500.0", "12500", "12500.00"}
        assert con_pratica["item"]["prefill"]["note_rg"] == "77/2026"
        assert f"id_fascicolo={pratica.id}" in con_pratica["item"]["href"]

        contesto = client.get(f"/api/v1/ui/applicazioni/contesto-fascicolo?id_fascicolo={pratica.id}").get_json()
        assert contesto["ok"] is True and contesto["prefill"] == con_pratica["item"]["prefill"]
        assert client.get("/api/v1/ui/applicazioni/contesto-fascicolo?id_fascicolo=NONC").get_json()["ok"] is False


def test_precompilato_richiede_il_permesso_sulle_pratiche(tmp_path):
    app = _app_sessione(tmp_path)
    _create_user(app, "ospite", "Ospite12345!", permessi_negati=["fascicoli.leggi"])
    with app.test_client() as client:
        _login(client, "ospite", "Ospite12345!")
        risposta = client.get("/api/v1/ui/applicazioni/calcolo_interessi_di_mora?id_fascicolo=ABC").get_json()
    assert risposta["ok"] is True and risposta["item"]["prefill"] == {}
    assert "Non hai accesso alle pratiche" in risposta["warnings"][0]


@pytest.mark.parametrize("app_id, tool_id", sorted(SENZA_STRUMENTO.items()))
def test_voci_senza_strumento_aprono_lo_strumento_corretto(tmp_path, app_id, tool_id):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        item = client.get(f"/api/v1/ui/applicazioni/{app_id}").get_json()["item"]
    assert item["type"] == "tool" and item["toolId"] == tool_id
    if app_id == "calcolo_notula_penale":
        assert item["preset"] == {"onorari_materia": "PENALE"}


def test_catalogo_strumenti_operativi_non_ha_piu_vicoli_ciechi():
    from web.services.react_studio_module_bridge import _build_strumenti_operativi

    records = {r["id"]: r["href"] for r in _build_strumenti_operativi()["operations"][0]["records"]}
    for app_id in QUATTORDICI:
        assert records[app_id] == f"/applicazioni/{app_id}", app_id
    for app_id, tool_id in SENZA_STRUMENTO.items():
        assert records[app_id].startswith(f"/strumenti-legali/?tool={tool_id}&app={app_id}"), records[app_id]
    assert [i for i, href in records.items() if href == "/strumenti-operativi"] == ["ricerca_applicazioni"]
    assert all("tool=" in href for href in records.values() if href.startswith("/strumenti-legali"))


def test_api_protetta_e_voci_sconosciute(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        assert client.get("/api/v1/ui/applicazioni/verifica_iban").status_code == 401
        _login(client)
        assert client.get("/api/v1/ui/applicazioni/inesistente").status_code == 404
        assert client.get("/api/v1/ui/applicazioni/Non-Valido").status_code == 404
        assert client.post("/api/v1/ui/applicazioni/verifica_iban/esegui", data="x").status_code == 400
        collegamento = client.get("/api/v1/ui/applicazioni/procura_alle_liti").get_json()["item"]
    assert collegamento["type"] == "collegamento" and collegamento["href"] == "/template-atti"


def test_shell_react_per_applicazioni_e_vista_storica_su_richiesta(tmp_path):
    from web.blueprints import react_shell
    from web.bootstrap.react_route_gate import _excluded, _is_react_route

    for percorso in ("/applicazioni", "/applicazioni/verifica_iban"):
        assert _is_react_route(percorso) and not _excluded(percorso), percorso
        assert react_shell._route_component_key(percorso) == "src/components/ApplicazionePage.tsx"
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        for percorso in ("/applicazioni", "/applicazioni/", "/applicazioni/verifica_iban", "/applicazioni/?app=verifica_iban"):
            risposta = client.get(percorso, headers=HTML)
            assert risposta.status_code == 200, percorso
            assert "iusentra-react-bootstrap" in risposta.get_data(as_text=True), percorso
        storica = client.get("/applicazioni/?_legacy=1&app=verifica_iban", headers=HTML)
        assert storica.status_code == 200 and "Cabina applicativa unificata" in storica.get_data(as_text=True)
        dettaglio = client.get("/applicazioni/verifica_iban?_legacy=1", headers=HTML)
        assert dettaglio.status_code == 302 and "app=verifica_iban" in dettaglio.headers["Location"]
