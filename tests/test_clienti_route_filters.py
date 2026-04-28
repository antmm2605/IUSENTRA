from pct.clienti import StatoCliente, TipoCliente
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from web.app import create_app
from web.helpers import get_clienti


def test_lista_clienti_default_mostra_tutti_gli_stati(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.app_context():
        gc = get_clienti()
        attivo = gc.nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Mario",
            cognome="Rossi",
            codice_fiscale="RSSMRA80A01H501U",
        )
        potenziale, _ = gc.crea_o_recupera_potenziale(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Roberto",
            cognome="Alessi",
            codice_fiscale="LSSRRT80A01H501U",
            provenienza="Preventivo guidato",
        )
        archiviato = gc.nuovo(
            TipoCliente.PERSONA_GIURIDICA,
            ragione_sociale="Archivio S.r.l.",
            partita_iva="12345678901",
        )
        gc.aggiorna(archiviato.id, stato=StatoCliente.ARCHIVIATO)

    with app.test_client() as client:
        _login(client)
        response = client.get("/clienti")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert attivo.nome_completo in body
    assert potenziale.nome_completo in body
    assert archiviato.nome_completo in body
    assert ">3<" in body
    assert "potenziali" in body
    assert "archiviati" in body
