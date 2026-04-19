from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.checklist_atti import (
    DECRETO_INGIUNTIVO,
    TUTTI_I_TEMPLATE,
    costruisci_catalogo_checklist,
    nome_cartella_compilato,
    statistiche_copertura_template_atti,
)
from pct.storage import StudioDB
from pct.template_atti_catalogo import build_builtin_templates
from pct.tenant import GestioneTenant
from web.app import create_app

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def _build_app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    return create_app({**_cfg_web(tmp_path), "MULTI_TENANT": True})


def _login_tenant_admin(app, client):
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Checklist", "studio-checklist", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    tenant_users = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
    )
    tenant_users.crea(
        username="checklist-admin",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=False,
    )
    response = client.post(
        "/login",
        data={
            "username": "checklist-admin",
            "password": "PasswordSicura!123",
            "studio_slug": studio.slug,
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_catalogo_checklist_copre_tutto_il_catalogo_professionale_template_atti():
    catalogo = costruisci_catalogo_checklist()
    stats = statistiche_copertura_template_atti()
    tassonomie_template = {
        (template["area"], template["branca"], template["sottobranca"])
        for template in build_builtin_templates()
    }
    tassonomie_checklist = {(template.area, template.branca, template.sottobranca) for template in TUTTI_I_TEMPLATE}

    assert len(TUTTI_I_TEMPLATE) >= len(build_builtin_templates())
    assert stats["template_coperti"] == stats["template_totali"] == len(build_builtin_templates())
    assert stats["tassonomie_scoperte"] == 0
    assert tassonomie_template <= tassonomie_checklist
    assert all(template.area and template.branca and template.sottobranca for template in TUTTI_I_TEMPLATE)
    assert any(area["nome"] == "Societario" for area in catalogo)
    assert any(
        branca["nome"] == "Procure e deleghe"
        for area in catalogo
        for branca in area["branche"]
    )
    assert any(
        sottobranca["nome"] == "Ricorsi, permessi e protezione"
        for area in catalogo
        for branca in area["branche"]
        for sottobranca in branca["sottobranche"]
    )


def test_nome_cartella_compilato_usa_data_italiana_filesystem_safe():
    cartella = nome_cartella_compilato(
        DECRETO_INGIUNTIVO,
        parte="Rossi Mario",
        data="2026-04-19",
    )

    assert cartella == "Decreto_ingiuntivo_Rossi_Mario_19-04-2026"
    assert "/" not in cartella


def test_checklist_route_renderizza_catalogo_professionale_completo(tmp_path: Path):
    app = _build_app(tmp_path)

    with app.test_client() as client:
        _login_tenant_admin(app, client)
        response = client.get("/checklist")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Checklist Atti professionale per aree, branche e sottobranche" in html
    assert "Copertura Template Atti" in html
    assert "Immigrazione" in html
    assert "Societario" in html
    assert "Procure e deleghe" in html
    assert "gg-mm-aaaa" in html


def test_checklist_dettaglio_mostra_cartella_con_data_italiana(tmp_path: Path):
    app = _build_app(tmp_path)

    with app.test_client() as client:
        _login_tenant_admin(app, client)
        response = client.get("/checklist/decreto_ingiuntivo?parte=Rossi%20Mario&data=2026-04-19")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Decreto_ingiuntivo_Rossi_Mario_19-04-2026" in html
    assert "Civile" in html
    assert "Monitorio e sommario" in html
    assert "Ricorsi monitori" in html


def test_checklist_dettaglio_builtin_renderizza_template_professionale_derivato(tmp_path: Path):
    app = _build_app(tmp_path)

    with app.test_client() as client:
        _login_tenant_admin(app, client)
        response = client.get("/checklist/builtin-tmp-proc-001?parte=Rossi%20Mario&data=2026-04-19")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Procura alle liti" in html
    assert "Procure e deleghe" in html
    assert "Mandati e domiciliazioni" in html
    assert "Workflow misto / redazione professionale" in html
    assert "19-04-2026" in html
