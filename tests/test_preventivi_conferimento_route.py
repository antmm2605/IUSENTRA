from pct.clienti import TipoCliente
from pct.preventivi import TipoVoce, VocePreventivo
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from web.app import create_app
from web.helpers import get_clienti, get_preventivi


def test_conferimento_da_preventivo_riallinea_cliente_stale_senza_500(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.app_context():
        cliente = get_clienti().nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Mario",
            cognome="Rossi",
            codice_fiscale="RSSMRA80A01H501U",
        )
        preventivo = get_preventivi().crea_preventivo(
            id_cliente=cliente.id,
            oggetto="Assistenza e conferimento incarico",
            voci=[
                VocePreventivo(
                    descrizione="Studio pratica",
                    importo=1000.0,
                    tipo=TipoVoce.ONORARIO,
                )
            ],
            creato_da="Avv. Test",
        )

    with app.test_client() as client:
        _login(client)
        response = client.get(
            f"/preventivi/conferimento/nuovo/CLIENTE_ERRATO"
            f"?id_preventivo={preventivo.id}&from_page=preventivo",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert f"/preventivi/conferimento/nuovo/{cliente.id}" in response.location
        assert f"id_preventivo={preventivo.id}" in response.location

        final = client.get(response.location, follow_redirects=False)
        body = final.get_data(as_text=True)

    assert final.status_code == 200
    assert "Preventivo collegato" in body
    assert "Mario Rossi" in body
    assert "Assistenza e conferimento incarico" in body
