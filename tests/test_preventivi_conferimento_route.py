from urllib.parse import parse_qs, urlparse

from pct.clienti import TipoCliente
from pct.config_studio import GestioneConfigStudio
from pct.preventivi import GestionePreventivi, StatoPreventivo, TipoVoce, VocePreventivo
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from web.app import create_app
from web.helpers import get_clienti, get_preventivi


def _completa_cliente_conferimento(gestione_clienti, cliente) -> None:
    gestione_clienti.aggiorna_indirizzo(
        cliente.id,
        "residenza",
        via="Via Roma",
        civico="1",
        comune="Palmi",
        provincia="RC",
    )
    gestione_clienti.aggiorna_recapiti(cliente.id, email="cliente@example.it")


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


def test_login_conferimento_preserva_id_preventivo_nel_next(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    url = (
        "/preventivi/conferimento/nuovo/EE0F9CEA"
        "?id_preventivo=172455b8-df0a-49d5-91ab-2ae9299d706d&from_page=preventivo"
    )
    with app.test_client() as client:
        response = client.get(url, follow_redirects=False)

    assert response.status_code == 302
    qs = parse_qs(urlparse(response.location).query)
    assert qs["next"][0] == url


def test_conferimento_prefilla_dati_forensi_da_impostazioni_studio(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    GestioneConfigStudio(config_path=app.config["STUDIO_CONFIG"]).aggiorna_sezione(
        "studio",
        {
            "nome": "Studio Test",
            "avvocato": "Avv. Titolare Studio",
            "numero_iscrizione_albo": "4567",
            "ordine_avvocati": "Ordine degli Avvocati di Palmi",
        },
    )

    with app.app_context():
        cliente = get_clienti().nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Luigi",
            cognome="Bianchi",
            codice_fiscale="RSSMRA80A01H501U",
        )

    with app.test_client() as client:
        _login(client)
        response = client.get(
            f"/preventivi/conferimento/nuovo/{cliente.id}",
            follow_redirects=False,
        )
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'value="Avv. Titolare Studio"' in body
    assert 'value="4567"' in body
    assert 'value="Ordine degli Avvocati di Palmi"' in body


def test_stato_preventivo_get_non_genera_500(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.app_context():
        cliente = get_clienti().nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Anna",
            cognome="Verdi",
            codice_fiscale="RSSMRA80A01H501U",
        )
        preventivo = get_preventivi().crea_preventivo(
            id_cliente=cliente.id,
            oggetto="Assistenza stragiudiziale",
            voci=[VocePreventivo(descrizione="Studio", importo=300.0, tipo=TipoVoce.ONORARIO)],
        )

    with app.test_client() as client:
        _login(client)
        response = client.get(f"/preventivi/p/{preventivo.id}/stato", follow_redirects=False)

    assert response.status_code == 302
    assert f"/preventivi/p/{preventivo.id}" in response.location


def test_accettazione_studio_fallback_su_form_conferimento_se_auto_creazione_fallisce(tmp_path, monkeypatch):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.app_context():
        gestione_clienti = get_clienti()
        cliente = gestione_clienti.nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Carla",
            cognome="Neri",
            codice_fiscale="RSSMRA80A01H501U",
        )
        _completa_cliente_conferimento(gestione_clienti, cliente)
        preventivo = get_preventivi().crea_preventivo(
            id_cliente=cliente.id,
            oggetto="Opposizione a decreto ingiuntivo",
            voci=[VocePreventivo(descrizione="Studio", importo=900.0, tipo=TipoVoce.ONORARIO)],
        )

    def _raise_auto_creazione(*args, **kwargs):
        raise RuntimeError("errore legacy conferimento")

    monkeypatch.setattr(GestionePreventivi, "crea_conferimento_da_preventivo", _raise_auto_creazione)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/preventivi/p/{preventivo.id}/workflow/accetta-studio",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert f"/preventivi/conferimento/nuovo/{cliente.id}" in response.location
    assert f"id_preventivo={preventivo.id}" in response.location
    with app.app_context():
        assert get_preventivi().get_preventivo(preventivo.id).stato == StatoPreventivo.ACCETTATO


def test_accettazione_studio_crea_conferimento_con_dati_forensi(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    GestioneConfigStudio(config_path=app.config["STUDIO_CONFIG"]).aggiorna_sezione(
        "studio",
        {
            "nome": "Studio Test",
            "avvocato": "Avv. Titolare Studio",
            "numero_iscrizione_albo": "4567",
            "ordine_avvocati": "Ordine degli Avvocati di Palmi",
        },
    )

    with app.app_context():
        gestione_clienti = get_clienti()
        cliente = gestione_clienti.nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Paolo",
            cognome="Gialli",
            codice_fiscale="RSSMRA80A01H501U",
        )
        _completa_cliente_conferimento(gestione_clienti, cliente)
        preventivo = get_preventivi().crea_preventivo(
            id_cliente=cliente.id,
            oggetto="Assistenza civile",
            voci=[VocePreventivo(descrizione="Studio", importo=700.0, tipo=TipoVoce.ONORARIO)],
        )

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/preventivi/p/{preventivo.id}/workflow/accetta-studio",
            follow_redirects=False,
        )

    assert response.status_code == 302
    with app.app_context():
        conferimento = get_preventivi().get_conferimento_principale_preventivo(preventivo.id)
    assert conferimento is not None
    assert conferimento.avvocato_referente == "Avv. Titolare Studio"
    assert conferimento.numero_iscrizione_albo == "4567"
    assert conferimento.ordine_avvocati == "Ordine degli Avvocati di Palmi"
