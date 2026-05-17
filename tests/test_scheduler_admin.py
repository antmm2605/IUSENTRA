from __future__ import annotations

from pathlib import Path

from web.app import create_app

from tests.test_legal_updates_pipeline import _cfg_web, _seed_platform_superadmin, _write_studio_config


def test_superadmin_puo_aprire_console_pianificazioni(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.get("/admin/pianificazioni")
        alias = client.get("/admin/cronjob", follow_redirects=False)

    assert login.status_code == 302
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Pianificazioni" in html
    assert "Agenti delegati disponibili" in html
    assert "Agente clienti e soggetti" in html
    assert "Agente email PEC" in html
    assert alias.status_code == 302
    assert alias.headers["Location"].endswith("/admin/pianificazioni")


def test_superadmin_crea_e_modifica_cronjob_agente(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        create = client.post(
            "/admin/pianificazioni/crea",
            data={
                "_csrf_token": "test",
                "template_key": "agent_clienti_soggetti",
                "name": "Controllo clienti serale",
                "trigger_kind": "cron",
                "hour": "22",
                "minute": "45",
                "interval_minutes": "60",
                "enabled": "1",
            },
            follow_redirects=True,
        )
        page = create.get_data(as_text=True)

    assert create.status_code == 200
    assert "Controllo clienti serale" in page
    assert "Ogni giorno alle 22:45" in page
    assert "agente delegato" in page


def test_superadmin_puo_richiedere_esecuzione_cronjob(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.post(
            "/admin/pianificazioni/legal_updates_batch/esegui",
            data={"_csrf_token": "test"},
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Esecuzione richiesta" in html
    assert "Richiesta" in html
