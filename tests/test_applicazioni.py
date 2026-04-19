from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pct.auth import GestioneUtenti, RuoloUtente
from web.app import create_app


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(tmp_path / "bootstrap_admin.json"),
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "TIMESHEET_DB": str(tmp_path / "timesheet.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione.json"),
        "PAGAMENTI_DIR": str(tmp_path / "pagamenti"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "giurisprudenza.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "CALENDAR_SYNC_DB": str(tmp_path / "calendar_sync.json"),
        "WIZARD_PRO_DB": str(tmp_path / "wizard_pro.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
        "UFFICI_GIUDIZIARI_DB": str(tmp_path / "uffici.json"),
        "REGINDE_DB": str(tmp_path / "reginde.json"),
        "STUDIO_NOME": "Studio Test Applicazioni",
    }


def _login(client) -> None:
    response = client.post(
        "/login",
        data={"username": "operatore", "password": "Operatore123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def _crea_operatore(app) -> None:
    with app.app_context():
        gestore = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
            bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
        )
        if not any(user.username == "operatore" for user in gestore.tutti()):
            gestore.crea(
                username="operatore",
                password="Operatore123!",
                ruolo=RuoloUtente.AMMINISTRATORE,
                email="operatore@example.it",
                nome_completo="Operatore Test",
                must_change_password=False,
            )


def test_applicazioni_index_renderizza_workspace_operativo_reale(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/applicazioni/")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Cabina applicativa unificata" in body
    assert "Applicazioni vere nello stesso workspace operativo" in body
    assert "Tutte le voci filtrate" in body
    assert "Primo piano operativo" in body
    assert "Apri nel workspace" in body
    assert "Workspace applicazioni professionali" not in body


def test_applicazioni_index_filtra_per_query_e_area(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/applicazioni/?q=cedolare&sezione=proprieta_successioni&tipo=patrimonio")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Calcolo Cedolare Secca" in body
    assert "Calcolo Danno Biologico" not in body


def test_applicazioni_dettaglio_reindirizza_al_workspace_attivo(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/applicazioni/calcolo_interessi_legali", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["Location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.path.endswith("/applicazioni/")
    assert query["app"] == ["calcolo_interessi_legali"]


def test_applicazioni_workspace_tool_calcola_davvero(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/applicazioni/",
            data={
                "app": "calcolo_interessi_legali",
                "app_id": "calcolo_interessi_legali",
                "int_tipo": "legali",
                "int_capitale": "1000",
                "int_data_inizio": "2025-01-01",
                "int_data_fine": "2025-12-31",
            },
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Calcolo Interessi Legali" in body
    assert "Interessi maturati" in body
    assert "Segmenti di calcolo" in body


def test_applicazioni_workspace_template_mostra_template_e_checklist(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/applicazioni/?app=procura_alle_liti")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Template compatibili" in body
    assert "Checklist correlate" in body
    assert "Apri checklist atti" in body


def test_applicazioni_workspace_telematico_ed_economico_espongono_pannelli_reali(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        telematico = client.get("/applicazioni/?app=deposito_telematico_documenti")
        economico = client.get("/applicazioni/?app=fatturazione_avvocati")

    telematico_body = telematico.get_data(as_text=True)
    economico_body = economico.get_data(as_text=True)

    assert telematico.status_code == 200
    assert "Portali attivi" in telematico_body
    assert "Fascicoli disponibili" in telematico_body
    assert economico.status_code == 200
    assert "Parcelle recenti" in economico_body
    assert "Preventivi recenti" in economico_body
    assert "Conferimenti recenti" in economico_body


def test_sidebar_studio_include_link_applicazioni(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/applicazioni/")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert ">Applicazioni</span>" in body


def test_template_applicazioni_workspace_usa_componenti_coerenti():
    index_html = Path("web/templates/applicazioni/index.html").read_text(encoding="utf-8")

    assert "Cabina applicativa unificata" in index_html
    assert "apps-workspace" in index_html
    assert "apps-module-grid" in index_html
    assert "Apri nel workspace" in index_html
