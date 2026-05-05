from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.timesheet import GestioneTimesheet, StatoTimesheet
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app


def _seed_cliente_fascicolo(app):
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Laura", cognome="Bianchi")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
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
    timesheet = GestioneTimesheet(db_path=app.config["TIMESHEET_DB"])
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
            data={"stato": StatoTimesheet.VALIDATO.value, "id_cliente": cliente.id, "id_fascicolo": fascicolo.id},
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
