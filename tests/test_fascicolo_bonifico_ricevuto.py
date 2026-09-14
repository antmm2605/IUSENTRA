"""«Registra bonifico ricevuto» dal controllo economico: parcella pagata e liquidazione a «Pagato» in un passaggio."""

from __future__ import annotations

from pathlib import Path

from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella
from tests.test_react_shell import _app
from web.services.fascicolo_bonifico_ricevuto import METODO_BONIFICO, registra_bonifico_ricevuto
from web.services.react_fascicoli_bridge import update_react_fascicolo_payment

HEADERS = {"X-API-Key": "react-test-key", "Content-Type": "application/json"}


def _seed(app, *, con_parcella: bool):
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi", codice_fiscale="RSSMRA80A01H501U")
    fascicoli = GestioneFascicoli(db_path=app.config["FASCICOLI_DB"], documents_dir=app.config["FASCICOLI_DOCS"], archive_dir=app.config["FASCICOLI_ARCH"])
    fascicolo = fascicoli.nuovo("Rossi / Alfa", TipoFascicolo.CIVILE, id_cliente=cliente.id, nome_cliente="Mario Rossi", numero_rg="12", anno_rg=2026)
    fatturazione = GestioneFatturazione(db_path=app.config["FATTURAZIONE_DB"])
    parcella = None
    if con_parcella:
        parcella = fatturazione.crea(id_cliente=cliente.id, id_fascicolo=fascicolo.id, voci=[VoceParcella(descrizione="Compenso", quantita=1.0, prezzo_unitario=4500.0, tipo="ONORARIO")], applica_iva=False, applica_cassa=False, applica_ritenuta=False, applica_bollo=False)
        fatturazione.cambia_stato(parcella.id, StatoParcella.EMESSA)
    return fascicolo, parcella


def test_bonifico_su_parcella_aperta_segna_pagata_e_chiude_la_liquidazione(tmp_path: Path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        get_fascicoli = app.extensions["core_runtime"]["get_fascicoli"]
        get_fatturazione = app.extensions["core_runtime"]["get_fatturazione"]
        esito, stato = update_react_fascicolo_payment(get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fascicolo.id, kind="liquidazione_giudice", payload={"status": "da_registrare", "importo": 4500, "documento_fonte": "Sentenza.pdf"}, actor="test")
        assert stato == 200, esito

        esito, stato = registra_bonifico_ricevuto(get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fascicolo.id, payload={"data_pagamento": "10/09/2026", "note": "bonifico Banca X"}, actor="avv. Bianchi")

        assert stato == 200, esito
        assert esito["ok"] and esito["parcellaId"] == parcella.id and esito["parcellaCreata"] is False
        assert esito["importo"] == 4500.0 and esito["dataPagamento"] == "2026-09-10" and esito["metodo"] == METODO_BONIFICO
        assert "registrato: parcella" in esito["message"] and "segnata pagata il 10/09/2026" in esito["message"]
        pagata = get_fatturazione().get(parcella.id)
        assert pagata.stato == StatoParcella.PAGATA and pagata.data_pagamento == "2026-09-10" and pagata.metodo_pagamento == METODO_BONIFICO
        liquidazione = esito["paymentSummary"]["items"]["liquidazione_giudice"]
        assert liquidazione["status"] == "pagato" and liquidazione["pagato"] is True and liquidazione["metodo"] == METODO_BONIFICO
        assert "Bonifico ricevuto il 10/09/2026" in liquidazione["note"]

        # La lettura del fascicolo legge la stessa fonte: liquidazione incassata, nessun passo di riscossione.
        from lex.context.fascicolo_lettura_context import load_fascicolo_lettura_context

        lettura = load_fascicolo_lettura_context(fascicolo_id=fascicolo.id)
        assert lettura["economico"]["liquidazione_incasso"] == "incassata"
        assert [voce["pagata_il"] for voce in lettura["economico"]["bonifici"]] == ["10/09/2026"]
        assert not any(passo["azione"].startswith("Riscuotere") for passo in lettura["prossimi_passi"])


def test_bonifico_senza_parcella_la_crea_e_la_segna_pagata(tmp_path: Path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, _ = _seed(app, con_parcella=False)
        get_fascicoli = app.extensions["core_runtime"]["get_fascicoli"]
        get_fatturazione = app.extensions["core_runtime"]["get_fatturazione"]
        esito, stato = registra_bonifico_ricevuto(get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fascicolo.id, payload={"importo": "1.200,50"}, actor="test")
        assert stato == 200, esito
        assert esito["parcellaCreata"] is True and esito["importo"] == 1200.5
        creata = get_fatturazione().get(esito["parcellaId"])
        assert creata.stato == StatoParcella.PAGATA and creata.metodo_pagamento == METODO_BONIFICO and creata.id_fascicolo == fascicolo.id
        assert abs(float(creata.totale) - 1200.5) < 0.01
        parcella = esito["paymentSummary"]["items"]["parcella"]
        assert parcella["status"] == "pagato"


def test_bonifico_rifiuta_importo_mancante_e_data_futura(tmp_path: Path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, _ = _seed(app, con_parcella=False)
        get_fascicoli = app.extensions["core_runtime"]["get_fascicoli"]
        get_fatturazione = app.extensions["core_runtime"]["get_fatturazione"]
        esito, stato = registra_bonifico_ricevuto(get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fascicolo.id, payload={}, actor="test")
        assert stato == 400 and "importo" in esito["errors"]
        esito, stato = registra_bonifico_ricevuto(get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc=fascicolo.id, payload={"importo": 10, "data_pagamento": "31/12/2099"}, actor="test")
        assert stato == 400 and "futura" in esito["message"]
        esito, stato = registra_bonifico_ricevuto(get_fascicoli=get_fascicoli, get_fatturazione=get_fatturazione, id_fasc="NONESISTE", payload={"importo": 10}, actor="test")
        assert stato == 404


def test_endpoint_bonifico_ricevuto(tmp_path: Path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
    with app.test_client() as client:
        risposta = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/bonifico-ricevuto", headers=HEADERS, json={"importo": 4500, "data_pagamento": "2026-09-10"})
    assert risposta.status_code == 200, risposta.get_data(as_text=True)
    payload = risposta.get_json()
    assert payload["ok"] is True and payload["parcellaId"] == parcella.id
    assert payload["redirectHref"].endswith(parcella.id)
