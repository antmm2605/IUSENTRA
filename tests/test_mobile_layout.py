from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from web.app import create_app


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
    }


def _login_admin(cfg: dict) -> None:
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    ).crea(
        username="admin-mobile",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )


def test_dashboard_mobile_header_usa_griglia_coerente(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _login_admin(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-mobile", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get("/", follow_redirects=True)
        html = page.get_data(as_text=True)

    css = Path("web/static/css/mobile.css").read_text(encoding="utf-8")

    assert page.status_code == 200
    assert 'class="ds-ph-actions"' in html
    assert "grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));" in css
    assert ".ds-ph-actions .d-none.d-sm-inline" in css
    assert ".topbar-actions .btn," in css


def test_agenda_mobile_toolbar_ha_layout_dedicato(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _login_admin(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-mobile", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get("/agenda", follow_redirects=True)
        html = page.get_data(as_text=True)

    css = Path("web/static/css/mobile.css").read_text(encoding="utf-8")

    assert page.status_code == 200
    assert "agenda-toolbar" in html
    assert "agenda-toolbar-group--vista" in html
    assert "agenda-toolbar-group--nav" in html
    assert ".agenda-toolbar-group--vista" in css
    assert ".agenda-toolbar-label" in css
