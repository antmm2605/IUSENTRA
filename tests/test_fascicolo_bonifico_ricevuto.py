"""«Registra bonifico ricevuto» dal controllo economico: parcella pagata e liquidazione a «Pagato» in un passaggio."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy

import pytest

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


@pytest.mark.parametrize("azione", ["segna-pagata", "stato", "incasso"])
def test_incasso_da_fatturazione_aggiorna_fascicolo_senza_cambiare_liquidato(tmp_path, azione):
    from tests.test_applicazioni import _crea_operatore, _login

    app = _app(tmp_path)
    _crea_operatore(app)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        gf = app.extensions["core_runtime"]["get_fascicoli"]
        gm = app.extensions["core_runtime"]["get_fatturazione"]
        risultato, stato = update_react_fascicolo_payment(
            get_fascicoli=gf, get_fatturazione=gm, id_fasc=fascicolo.id, kind="liquidazione_giudice",
            payload={"importo": 1100, "status": "da_registrare", "documento_fonte": "Sentenza.pdf"}, actor="Avvocato")
        assert stato == 200, risultato
    with app.test_client() as client:
        _login(client)
        body = {"stato": "PAGATA", "data_pagamento": "2026-09-10", "metodo_pagamento": METODO_BONIFICO}
        url = f"/api/v1/ui/fatturazione/{parcella.id}/{azione}"
        if azione == "incasso":
            url = "/api/v1/ui/incassi-pagamenti/incasso"
            body = {"id_parcella": parcella.id, "data_pagamento": "2026-09-10", "metodo_pagamento": METODO_BONIFICO}
        response = client.post(url, json=body)
        assert response.status_code == 200, response.get_data(as_text=True)
        with app.app_context():
            saved = gf().get(fascicolo.id)
            liquidazione = saved.pagamenti["liquidazione_giudice"]
            assert liquidazione["status"] == "pagato" and liquidazione["importo"] == 1100
            assert liquidazione["documento_fonte"] == "Sentenza.pdf" and liquidazione["proforma_id"] == parcella.id
            assert saved.pagamenti["parcella"]["status"] == "pagato"
            assert saved.pagamenti["parcella"]["proforma_id"] == parcella.id
            assert gm().get(parcella.id).stato == StatoParcella.PAGATA
            # Due rappresentazioni dello stesso incasso non raddoppiano il totale.
            from web.services.react_fascicoli_bridge import payment_summary_for_fascicolo
            summary = payment_summary_for_fascicolo(saved)
            assert summary["totaleRegistrato"] == 4500
            assert "€ 4.500,00" in summary["items"]["liquidazione_giudice"]["note"]
            assert summary["items"]["liquidazione_giudice"]["importo"] == 1100
            result_cu, stato_cu = update_react_fascicolo_payment(
                get_fascicoli=gf, get_fatturazione=gm, id_fasc=fascicolo.id, kind="contributo_unificato",
                payload={"importo": 49, "status": "pagato", "documento_fonte": "Ricevuta CU.pdf"}, actor="Avvocato")
            assert stato_cu == 200, result_cu
            assert result_cu["paymentSummary"]["totaleRegistrato"] == 4549
            assert result_cu["paymentSummary"]["items"]["contributo_unificato"]["importo"] == 49
            saved = gf().get(fascicolo.id)
            prima = deepcopy(saved.pagamenti)
        repeat = client.post(url, json=body)
        assert repeat.status_code == 200, repeat.get_data(as_text=True)
        with app.app_context():
            assert gf().get(fascicolo.id).pagamenti == prima
            assert len(gm().per_fascicolo(fascicolo.id)) == 1


def test_collegamento_incasso_ad_altro_fascicolo_non_scrive(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        gf = app.extensions["core_runtime"]["get_fascicoli"]
        gm = app.extensions["core_runtime"]["get_fatturazione"]
        altro = gf().nuovo("Altro procedimento sintetico", TipoFascicolo.CIVILE, nome_cliente="Anna Bianchi")
        before = deepcopy(gf().get(altro.id).pagamenti)
        result, status = update_react_fascicolo_payment(
            get_fascicoli=gf, get_fatturazione=gm, id_fasc=altro.id, kind="liquidazione_giudice",
            payload={"status": "pagato", "importo": 1100, "proforma_id": parcella.id}, actor="Avvocato")
        assert status == 409 and not result["ok"]
        assert gf().get(altro.id).pagamenti == before
        assert gm().get(parcella.id).stato == StatoParcella.EMESSA


def test_incasso_gia_registrato_richiede_scelta_e_preserva_data_originale(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        gf = app.extensions["core_runtime"]["get_fascicoli"]
        gm = app.extensions["core_runtime"]["get_fatturazione"]
        gm().cambia_stato(parcella.id, StatoParcella.PAGATA, data_pagamento="2026-09-10", metodo_pagamento=METODO_BONIFICO)
        args = dict(get_fascicoli=gf, get_fatturazione=gm, id_fasc=fascicolo.id, actor="Avvocato")
        result, status = registra_bonifico_ricevuto(**args, payload={"importo": 4500})
        assert status == 409 and result["parcelle"][0]["id"] == parcella.id
        assert len(gm().per_fascicolo(fascicolo.id)) == 1
        result, status = registra_bonifico_ricevuto(**args, payload={"parcella_id": parcella.id, "importo": 4500, "data_pagamento": "2026-10-12"})
        assert status == 200, result
        assert result["dataPagamento"] == "2026-09-10"
        assert gf().get(fascicolo.id).pagamenti["parcella"]["data_pagamento"] == "2026-09-10"
        assert len(gm().per_fascicolo(fascicolo.id)) == 1
        before = deepcopy(gf().get(fascicolo.id).pagamenti)
        repeat, status = registra_bonifico_ricevuto(**args, payload={"parcella_id": parcella.id, "importo": 4500})
        assert status == 200 and repeat["alreadyPresent"] is True
        assert "già collegato" in repeat["message"]
        assert gf().get(fascicolo.id).pagamenti == before
def test_versamento_discordante_non_diventa_saldo_ne_modifica_importi(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        gf = app.extensions["core_runtime"]["get_fascicoli"]
        gm = app.extensions["core_runtime"]["get_fatturazione"]
        before = deepcopy(gf().get(fascicolo.id).pagamenti)
        result, status = registra_bonifico_ricevuto(get_fascicoli=gf, get_fatturazione=gm,
            id_fasc=fascicolo.id, payload={"parcella_id": parcella.id, "importo": 1000}, actor="Avvocato")
        assert status == 409 and result["conflict"]
        assert result["discordanza"]["nettoParcella"] == 4500
        assert gf().get(fascicolo.id).pagamenti == before
        assert gm().get(parcella.id).stato == StatoParcella.EMESSA

def test_incasso_originale_non_cambia_con_revisione_successiva_documento(tmp_path):
    from pct.fatturazione import VoceParcella
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        gf = app.extensions["core_runtime"]["get_fascicoli"]
        gm = app.extensions["core_runtime"]["get_fatturazione"]
        args = dict(get_fascicoli=gf, get_fatturazione=gm, id_fasc=fascicolo.id, actor="Avvocato")
        result, status = registra_bonifico_ricevuto(**args, payload={"parcella_id": parcella.id, "importo": 4500})
        assert status == 200
        before = deepcopy(gf().get(fascicolo.id).pagamenti)
        gm().aggiorna(parcella.id, voci=[VoceParcella(descrizione="Revisione controllata", quantita=1, prezzo_unitario=5500)])
        result, status = registra_bonifico_ricevuto(**args, payload={"parcella_id": parcella.id, "importo": 5500})
        assert status == 200 and result["alreadyPresent"]
        assert result["importo"] == 4500
        assert gf().get(fascicolo.id).pagamenti == before
        rejected, status = update_react_fascicolo_payment(get_fascicoli=gf, get_fatturazione=gm,
            id_fasc=fascicolo.id, kind="contributo_unificato",
            payload={"status": "pagato", "importo": 49, "proforma_id": parcella.id}, actor="Avvocato")
        assert status == 400 and not rejected["ok"]
        assert gf().get(fascicolo.id).pagamenti == before



def test_bonifico_usa_giorno_italiano_anche_quando_utc_e_ieri(monkeypatch):
    from datetime import UTC, datetime
    import web.services.react_dashboard_time as clock
    import web.services.fascicolo_bonifico_ricevuto as service
    local_now = datetime(2026, 10, 13, 0, 30, tzinfo=clock.ROME_TZ)
    assert local_now.astimezone(UTC).date().isoformat() == "2026-10-12"
    monkeypatch.setattr(clock, "adesso_rome", lambda: local_now)
    assert service._data_iso("") == ("2026-10-13", "")
    assert service._data_iso("13/10/2026") == ("2026-10-13", "")
    assert service._data_iso("14/10/2026")[1] == "La data del bonifico non può essere futura."


@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '-Infinity', '1e9999', float('nan'), float('inf'), True, 'errato', {}])
def test_importo_esplicito_non_valido_non_usa_liquidazione_e_non_apre_fatturazione(monkeypatch, amount):
    from types import SimpleNamespace
    import web.services.fascicolo_bonifico_ricevuto as service

    case = SimpleNamespace(id='controlled-case', pagamenti={})
    monkeypatch.setattr('web.services.react_fascicoli_bridge._resolve_fascicolo', lambda *_: case)
    monkeypatch.setattr(service, '_liquidazione', lambda _: {'importo': 4500})
    result, status = service.registra_bonifico_ricevuto(
        get_fascicoli=lambda: object(),
        get_fatturazione=lambda: pytest.fail('Importo non valido arrivato alla fatturazione'),
        id_fasc=case.id, payload={'importo': amount},
    )
    assert status == 400 and not result['ok']
    assert 'importo' in result['errors']
    assert case.pagamenti == {}


@pytest.mark.parametrize('field,amount', [('importo', 'NaN'), ('amount', 'errato')])
def test_api_importo_non_valido_preserva_parcella_e_liquidazione(tmp_path, field, amount):
    app = _app(tmp_path)
    with app.app_context():
        case, invoice = _seed(app, con_parcella=True)
        gf = app.extensions['core_runtime']['get_fascicoli']
        gm = app.extensions['core_runtime']['get_fatturazione']
        result, status = update_react_fascicolo_payment(
            get_fascicoli=gf, get_fatturazione=gm, id_fasc=case.id,
            kind='liquidazione_giudice', payload={'status': 'da_registrare', 'importo': 4500}, actor='test',
        )
        assert status == 200, result
        before = deepcopy(gf().get(case.id).pagamenti)
        response = app.test_client().post(
            f'/api/v1/ui/fascicoli/{case.id}/bonifico-ricevuto', headers=HEADERS, json={field: amount},
        )
        assert response.status_code == 400 and not response.json['ok']
        stored = GestioneFatturazione(db_path=app.config['FATTURAZIONE_DB']).get(invoice.id)
        assert stored.stato == StatoParcella.EMESSA and not stored.data_pagamento
        assert gf().get(case.id).pagamenti == before

@pytest.mark.parametrize('received', [999.99, 1000.01])
def test_un_centesimo_discordante_non_dimostra_saldo(tmp_path, received):
    app = _app(tmp_path)
    with app.app_context():
        case, invoice = _seed(app, con_parcella=True)
        gf = app.extensions['core_runtime']['get_fascicoli']
        gm = app.extensions['core_runtime']['get_fatturazione']
        gm().aggiorna(invoice.id, voci=[VoceParcella(descrizione='Compenso controllato', quantita=1, prezzo_unitario=1000)])
        before = deepcopy(gf().get(case.id).pagamenti)
        result, status = registra_bonifico_ricevuto(
            get_fascicoli=gf, get_fatturazione=gm, id_fasc=case.id,
            payload={'parcella_id': invoice.id, 'importo': received}, actor='Collaudo',
        )
        assert status == 409 and result['conflict'], result
        assert gm().get(invoice.id).stato == StatoParcella.EMESSA
        assert gf().get(case.id).pagamenti == before

def test_due_parcelle_distinte_per_un_centesimo_seleziona_importo_esatto(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        case, first = _seed(app, con_parcella=True)
        gf = app.extensions['core_runtime']['get_fascicoli']
        gm = app.extensions['core_runtime']['get_fatturazione']
        manager = gm()
        manager.aggiorna(first.id, voci=[VoceParcella(descrizione='Primo compenso', quantita=1, prezzo_unitario=1000)])
        second = manager.crea(id_cliente=case.id_cliente, id_fascicolo=case.id,
            voci=[VoceParcella(descrizione='Secondo compenso', quantita=1, prezzo_unitario=1000.01)],
            applica_iva=False, applica_cassa=False, applica_ritenuta=False, applica_bollo=False)
        manager.cambia_stato(second.id, StatoParcella.EMESSA)
        result, status = registra_bonifico_ricevuto(
            get_fascicoli=gf, get_fatturazione=gm, id_fasc=case.id,
            payload={'importo': 1000.01}, actor='Collaudo',
        )
        assert status == 200, result
        assert result['parcellaId'] == second.id
        assert gm().get(first.id).stato == StatoParcella.EMESSA
        assert gm().get(second.id).stato == StatoParcella.PAGATA

def test_bonifico_rejects_a_document_changed_after_selection(tmp_path):
    from pct.fatturazione import parcella_revision
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        core = app.extensions['core_runtime']
        manager = core['get_fatturazione']()
        revision = parcella_revision(manager.get(parcella.id))
        manager.aggiorna(parcella.id, note='Revisione successiva alla selezione')
        before = core['get_fascicoli']().get(fascicolo.id).to_dict()
        result, status = registra_bonifico_ricevuto(
            get_fascicoli=core['get_fascicoli'], get_fatturazione=core['get_fatturazione'],
            id_fasc=fascicolo.id, payload={'parcella_id':parcella.id, 'parcella_revision':revision,
                                        'importo':4500, 'data_pagamento':'2026-09-10'}, actor='test')
        assert status == 409 and result['conflict']
        assert core['get_fatturazione']().get(parcella.id).stato == StatoParcella.EMESSA
        assert core['get_fascicoli']().get(fascicolo.id).to_dict() == before


def test_rejected_state_transition_does_not_mutate_loaded_invoice(tmp_path, monkeypatch):
    from pct.fatturazione import ParcellaConcurrentUpdate, parcella_revision
    app = _app(tmp_path)
    with app.app_context():
        _, parcella = _seed(app, con_parcella=True)
        manager = app.extensions['core_runtime']['get_fatturazione']()
        before = manager.get(parcella.id).to_dict()
        def reject(*args, **kwargs):
            raise ParcellaConcurrentUpdate('Aggiornamento concorrente')
        monkeypatch.setattr(manager, '_salva_parcella', reject)
        with pytest.raises(ParcellaConcurrentUpdate):
            manager.cambia_stato(parcella.id, StatoParcella.PAGATA,
                                expected_revision=parcella_revision(manager.get(parcella.id)))
        assert manager.get(parcella.id).to_dict() == before

def test_invoice_choices_api_returns_only_selected_case_and_disables_cache(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        from web.services.storage_runtime import get_request_studio_db
        assert get_request_studio_db(app.config['FATTURAZIONE_DB']) is not None
    client = app.test_client()
    response = client.get(f'/api/v1/ui/fascicoli/{fascicolo.id}/bonifico-ricevuto', headers=HEADERS)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['ok'] and [item['id'] for item in result['items']] == [parcella.id]
    assert response.headers['Cache-Control'] == 'no-store'
    invalid = client.get(f'/api/v1/ui/fascicoli/{fascicolo.id}/bonifico-ricevuto?limit=all', headers=HEADERS)
    assert invalid.status_code == 400 and invalid.get_json()['message'] == 'Dimensione della pagina non valida.'
    denied = client.get(f'/api/v1/ui/fascicoli/{fascicolo.id}/bonifico-ricevuto')
    assert denied.status_code in (401, 403)

def test_bonifico_rejects_invoice_of_another_client(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        fascicolo, parcella = _seed(app, con_parcella=True)
        core = app.extensions['core_runtime']
        manager = core['get_fatturazione']()
        manager.aggiorna(parcella.id, id_cliente='foreign-client')
        result, status = registra_bonifico_ricevuto(
            get_fascicoli=core['get_fascicoli'], get_fatturazione=core['get_fatturazione'],
            id_fasc=fascicolo.id, payload={'parcella_id':parcella.id, 'importo':4500}, actor='test')
        assert status == 409 and 'Cliente' in result['message']
        assert core['get_fatturazione']().get(parcella.id).stato == StatoParcella.EMESSA


def test_invalid_invoice_revision_stops_before_reading_repositories():
    def forbidden():
        raise AssertionError('Repository non necessario per richiesta non valida')
    result, status = registra_bonifico_ricevuto(
        get_fascicoli=forbidden, get_fatturazione=forbidden, id_fasc='case',
        payload={'parcella_id':'invoice', 'parcella_revision':'invalid'}, actor='test')
    assert status == 400 and not result['ok']
