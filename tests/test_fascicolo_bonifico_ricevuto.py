"""Il vecchio comando non simula incassi: nessuna scrittura prima del registro SQL nativo.

I cicli positivi, parziali, storni, retry e concorrenza sono provati in
test_parcella_incassi_repository.py e test_invoice_receipts_sql_lifecycle.py.
"""

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



def test_confirmed_receipt_api_audits_replay_without_global_refresh(tmp_path, monkeypatch):
    from web.blueprints import api_v1_react as api
    import web.services.fascicolo_bonifico_ricevuto as service
    app = _app(tmp_path)
    events = []
    def forbidden(*args, **kwargs):
        raise AssertionError('Un riscontro già presente non deve invalidare altre letture')
    monkeypatch.setattr(service, 'registra_bonifico_ricevuto', lambda **kwargs: (
        {'ok':True,'alreadyPresent':True,'message':'Incasso già presente.'},200))
    monkeypatch.setattr(api, '_clear_fascicoli_list_payload_cache', forbidden)
    from types import SimpleNamespace
    monkeypatch.setattr(api, '_LETTURA_CACHE', SimpleNamespace(clear=forbidden))
    monkeypatch.setattr(api, '_audit_event', lambda *args, **kwargs: events.append(args))
    response = app.test_client().post('/api/v1/ui/fascicoli/controlled/bonifico-ricevuto',json={},headers=HEADERS)
    assert response.status_code == 200 and response.get_json()['alreadyPresent']
    assert len(events) == 1 and events[0][0] == 'fascicoli.bonifico_gia_presente'


@pytest.mark.parametrize('con_parcella', [False, True])
def test_vecchio_bonifico_rifiutato_non_crea_documenti_ne_scrive_presidi(tmp_path, con_parcella):
    app = _app(tmp_path)
    with app.app_context():
        case, invoice = _seed(app, con_parcella=con_parcella)
        core = app.extensions['core_runtime']
        gf, gm = core['get_fascicoli'], core['get_fatturazione']
        before_case = deepcopy(gf().get(case.id).to_dict())
        before_invoices = [item.to_dict() for item in gm().per_fascicolo(case.id)]
        body = {'importo':4500, 'data_pagamento':'2026-09-10'}
        for _ in range(2):
            result, status = registra_bonifico_ricevuto(get_fascicoli=gf, get_fatturazione=gm,
                id_fasc=case.id, payload=body, actor='Collaudo')
            assert status == 409 and result['code'] == 'receipt_required'
            assert result['redirectHref'].startswith('/fatturazione')
            assert gf().get(case.id).to_dict() == before_case
            assert [item.to_dict() for item in gm().per_fascicolo(case.id)] == before_invoices


@pytest.mark.parametrize('con_parcella', [False, True])
def test_api_bonifico_non_lascia_bozza_dopo_rifiuto(tmp_path, con_parcella):
    app = _app(tmp_path)
    with app.app_context():
        case, invoice = _seed(app, con_parcella=con_parcella)
        core = app.extensions['core_runtime']
        before = [item.to_dict() for item in core['get_fatturazione']().per_fascicolo(case.id)]
        before_case = deepcopy(core['get_fascicoli']().get(case.id).to_dict())
    response = app.test_client().post(f'/api/v1/ui/fascicoli/{case.id}/bonifico-ricevuto',
        headers=HEADERS, json={'importo':4500,'data_pagamento':'2026-09-10'})
    assert response.status_code == 409 and response.json['code'] == 'receipt_required'
    with app.app_context():
        assert [item.to_dict() for item in core['get_fatturazione']().per_fascicolo(case.id)] == before
        assert core['get_fascicoli']().get(case.id).to_dict() == before_case


@pytest.mark.parametrize('action', ['segna-pagata', 'stato', 'incasso'])
def test_vecchi_stati_http_non_sostituiscono_il_movimento_sql(tmp_path, action):
    from tests.test_applicazioni import _crea_operatore, _login
    app = _app(tmp_path)
    _crea_operatore(app)
    with app.app_context():
        case, invoice = _seed(app, con_parcella=True)
        core = app.extensions['core_runtime']
        before = deepcopy(core['get_fatturazione']().get(invoice.id).to_dict())
        before_case = deepcopy(core['get_fascicoli']().get(case.id).to_dict())
    with app.test_client() as client:
        _login(client)
        url = f'/api/v1/ui/fatturazione/{invoice.id}/{action}'
        body = {'stato':'PAGATA','data_pagamento':'2026-09-10','metodo_pagamento':METODO_BONIFICO}
        if action == 'incasso':
            url = '/api/v1/ui/incassi-pagamenti/incasso'
            body = {'id_parcella': invoice.id, 'data_pagamento':'2026-09-10', 'metodo_pagamento':METODO_BONIFICO}
        response = client.post(url, json=body)
        assert response.status_code == 409 and response.json['code'] == 'receipt_required'
    with app.app_context():
        assert core['get_fatturazione']().get(invoice.id).to_dict() == before
        assert core['get_fascicoli']().get(case.id).to_dict() == before_case


def test_guardia_pagata_preserva_anche_oggetto_caricato(tmp_path):
    from pct.fatturazione_sql_commands import ParcellaPaymentRequiresReceipt
    app = _app(tmp_path)
    with app.app_context():
        _, invoice = _seed(app, con_parcella=True)
        manager = app.extensions['core_runtime']['get_fatturazione']()
        before = deepcopy(manager.get(invoice.id).to_dict())
        with pytest.raises(ParcellaPaymentRequiresReceipt):
            manager.cambia_stato(invoice.id, StatoParcella.PAGATA)
        assert manager.get(invoice.id).to_dict() == before


def test_scelta_importo_esatto_non_diventa_pagamento_implicito(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        case, first = _seed(app, con_parcella=True)
        core = app.extensions['core_runtime']
        gm = core['get_fatturazione']
        second = gm().crea(id_cliente=case.id_cliente, id_fascicolo=case.id,
            voci=[VoceParcella(descrizione='Secondo compenso', quantita=1, prezzo_unitario=4500.01)],
            applica_iva=False, applica_cassa=False, applica_ritenuta=False, applica_bollo=False)
        gm().cambia_stato(second.id, StatoParcella.EMESSA)
        before = [item.to_dict() for item in gm().per_fascicolo(case.id)]
        result, status = registra_bonifico_ricevuto(get_fascicoli=core['get_fascicoli'],
            get_fatturazione=gm,id_fasc=case.id,payload={'importo':4500.01},actor='Collaudo')
        assert status == 409 and result['code'] == 'receipt_required'
        assert result['parcellaId'] == second.id
        assert [item.to_dict() for item in gm().per_fascicolo(case.id)] == before
