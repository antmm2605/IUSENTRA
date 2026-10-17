from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pct.clienti import TipoCliente
from pct.fascicoli import TipoFascicolo
from pct.timesheet import StatoTimesheet
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app
from web.helpers import get_clienti, get_fascicoli, get_timesheet


def _seed_cliente_fascicolo(app):
    with app.app_context():
        clienti = get_clienti()
        cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Laura", cognome="Bianchi")
        fascicolo = get_fascicoli().nuovo(
            "Recupero credito",
            TipoFascicolo.CIVILE,
            id_cliente=cliente.id,
            nome_cliente=cliente.nome_completo,
            tribunale="Tribunale di Milano",
        )
        return cliente, fascicolo


def test_timesheet_react_shell_api_e_post_operativi(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    with app.app_context():
        timesheet = get_timesheet()
        voce = timesheet.crea(
        descrizione="Studio documenti udienza",
        minuti=90,
        id_fascicolo=fascicolo.id,
        id_cliente=cliente.id,
        username="operatore",
        data_attivita=date.today().isoformat(),
        valore_unitario=120.0,
            fatturabile=True,
        )

    with app.test_client() as client:
        _login(client)
        response = client.get("/timesheet")
        classic = client.get("/timesheet?_legacy=1")
        api = client.get("/api/v1/ui/timesheet")
        create = client.post(
            "/timesheet/nuovo",
            data={
                "descrizione": "Telefonata cliente",
                "minuti": "25",
                "id_fascicolo": fascicolo.id,
                "id_cliente": cliente.id,
                "data_attivita": date.today().isoformat(),
                "valore_unitario": "80",
                "fatturabile": "1",
                "note": "Aggiornamento operativo",
                "contesto": "telefono",
            },
        )
        status = client.post(
            f"/timesheet/{voce.id}/stato",
            data={"stato": StatoTimesheet.VALIDATO.value, "revision": voce.revisione, "id_cliente": cliente.id, "id_fascicolo": fascicolo.id},
        )
        invoice = client.post(
            "/timesheet/genera-parcella",
            data={
                "entry_ids": [voce.id],
                "id_cliente": cliente.id,
                "id_fascicolo": fascicolo.id,
                "data_scadenza": (date.today() + timedelta(days=30)).isoformat(),
            },
        )

    assert response.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in response.get_data(as_text=True)
    assert classic.status_code == 200
    assert 'id="root"' not in classic.get_data(as_text=True)
    assert api.status_code == 200
    payload = api.get_json()
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["contracts"]["route_owner"] == "react_shell"
    assert payload["summary"]["totalEntries"] >= 1
    assert any(item["id"] == voce.id for item in payload["entries"])
    assert create.status_code in {302, 303}
    assert status.status_code in {302, 303}
    assert invoice.status_code in {302, 303}


def test_proposte_sql_da_generazione_a_api_conferma_e_riapertura(tmp_path):
    from types import SimpleNamespace
    from pct.time_tracking_passivo import GestioneTrackingPassivo
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    with app.test_client() as client:
        _login(client)
        with client.session_transaction() as session:
            actor_id = session['user_id']
        with app.app_context():
            from web.helpers import get_utenti
            worker_id = next(user.id for user in get_utenti().tutti() if user.id != actor_id)
            manager = get_timesheet()
            tracking_path = Path(manager.db_path).parent / 'tracking_passivo.json'
            tracking = GestioneTrackingPassivo(str(tracking_path), studio_db=manager._studio_db)
            events = [SimpleNamespace(timestamp=f'2026-10-17T10:{minute}:00', azione='fascicoli.apri',
                risorsa_tipo='fascicolo', risorsa_id=fascicolo.id, id_utente=worker_id, username='operatore fonte', esito='OK')
                for minute in ('00', '10')]
            proposal = tracking.genera_da_eventi(events)[0]
            assert not tracking_path.exists()
        response = client.get('/api/v1/ui/timesheet')
        assert response.status_code == 200
        assert any(row['id'] == proposal['id'] for row in response.get_json()['trackingProposals'])
        first = client.post(f"/timesheet/proposte/{proposal['id']}/conferma", json={})
        repeated = client.post(f"/timesheet/proposte/{proposal['id']}/conferma", json={})
        assert first.status_code == repeated.status_code == 200
        entry_id = first.get_json()['proposta']['voce_timesheet_id']
        assert repeated.get_json()['proposta']['voce_timesheet_id'] == entry_id
        assert first.get_json()['proposta']['definito_da'] == actor_id
        after = client.get('/api/v1/ui/timesheet').get_json()
        assert not any(row['id'] == proposal['id'] for row in after['trackingProposals'])
    with app.app_context():
        saved = get_timesheet()
        entry = saved.get(entry_id)
        assert entry.id_cliente == cliente.id
        assert entry.id_fascicolo == fascicolo.id
        assert entry.id_utente == worker_id
        assert len([row for row in saved.tutte() if row.origine == 'tracking_passivo']) == 1
        assert not tracking_path.exists()
