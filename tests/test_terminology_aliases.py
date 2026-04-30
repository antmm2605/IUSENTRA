from pathlib import Path

from web.app import create_app

from tests.test_applicazioni import _cfg_web, _crea_operatore, _login


def test_alias_professionali_reindirizzano_alle_route_storiche_o_react(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    expected_locations = {
        "/redazione-atti/catalogo": "/template-atti/catalogo",
        "/redazione-atti/redigi/CIV_CIT_001": "/template-atti/compila/CIV_CIT_001",
        "/servizi-telematici": "/telematico",
        "/regia-operativa": "/workspace-intelligente",
        "/ricerca-studio": "/global-search",
    }
    expected_react = ("/redazione-atti", "/strumenti-operativi", "/compensi-forensi")

    with app.test_client() as client:
        _login(client)
        for alias, target in expected_locations.items():
            response = client.get(alias, follow_redirects=False)
            assert response.status_code == 302
            assert response.headers["Location"].endswith(target)
        for alias in expected_react:
            response = client.get(alias, follow_redirects=False)
            assert response.status_code == 200
            assert "IUSENTRA - React Shell" in response.get_data(as_text=True)


def test_menu_principale_usa_terminologia_forense(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/applicazioni/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Regia Operativa" in html
    assert "Servizi Telematici" in html
    assert "Redazione Atti" in html
    assert "Parcelle e Fatture" in html
    assert "Compensi Forensi" in html
    assert "Template Atti" not in html
    assert "PCT / Telematico" not in html
