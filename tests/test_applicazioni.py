from pathlib import Path

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
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
    }


def test_applicazioni_index_renderizza_catalogo_e_rassegna(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        assert login.status_code == 200

        response = client.get("/applicazioni/")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Workspace applicazioni professionali" in body
    assert "Filtri avanzati" in body
    assert "Primo piano operativo" in body
    assert "Notizie Giuridiche" in body
    assert "Calcolo Interessi Legali" in body
    assert "Link Ricerca PEC" in body
    assert "Azioni immediate" in body
    assert "Percorso guidato" in body


def test_applicazioni_index_filtra_per_query_e_area(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/applicazioni/?q=cedolare&sezione=proprieta_successioni&tipo=patrimonio")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Calcolo Cedolare Secca" in body
    assert "Calcolo Danno Biologico" not in body


def test_applicazioni_index_filtra_primo_piano_e_modalita(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/applicazioni/?solo_primo_piano=1&modalita=diretta&q=interessi")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Calcolo Interessi Legali" in body
    assert "Rivalutazione Mensile" not in body


def test_applicazioni_dettaglio_collega_modulo_operativo(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/applicazioni/calcolo_interessi_legali")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Calcolo Interessi Legali" in body
    assert "Azioni workspace" in body
    assert "Moduli correlati" in body
    assert "Stessa tipologia" in body
    assert '/strumenti-legali/?tool=interessi' in body


def test_sidebar_studio_include_link_applicazioni(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/applicazioni/")
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert ">Applicazioni</span>" in body


def test_template_applicazioni_workspace_usa_griglie_compatte():
    index_html = Path("web/templates/applicazioni/index.html").read_text(encoding="utf-8")
    detail_html = Path("web/templates/applicazioni/dettaglio.html").read_text(encoding="utf-8")

    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in index_html
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in detail_html
    assert "solo_primo_piano" in index_html
