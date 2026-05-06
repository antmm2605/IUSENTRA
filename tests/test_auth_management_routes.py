from pathlib import Path

from pct.auth import RuoloUtente
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    return create_app(_cfg_web(tmp_path))


def test_permessi_utente_legacy_renderizza_e_salva_override(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.app_context():
        utenti = app.extensions["core_runtime"]["get_utenti"]()
        target = utenti.crea(
            username="collaboratore-permessi",
            password="Password123!",
            ruolo=RuoloUtente.SEGRETERIA,
            nome_completo="Collaboratore Permessi",
        )
        target_id = target.id

    with app.test_client() as client:
        _login(client)

        response = client.get(f"/utenti/{target_id}/permessi?_legacy=1")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Permessi utente: collaboratore-permessi" in html
        assert "Impostazioni accesso per sezione" in html

        post_response = client.post(
            f"/utenti/{target_id}/permessi?_legacy=1",
            data={"permessi_extra": ["backup.leggi"], "permessi_negati": []},
        )

        assert post_response.status_code in {302, 303}

    with app.app_context():
        utenti = app.extensions["core_runtime"]["get_utenti"]()
        aggiornato = utenti.get(target_id)

    assert aggiornato is not None
    assert "backup.leggi" in aggiornato.permessi_extra
