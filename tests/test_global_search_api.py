from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.global_search.models import GlobalSearchDocument
from pct.global_search.repository import GlobalSearchRepository
from pct.global_search.service import default_global_search_db_path
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
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
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
    }


def _crea_utente(app):
    with app.app_context():
        gestore = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
            bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
        )
        gestore.crea(
            username="operatore",
            password="Operatore123!",
            ruolo=RuoloUtente.AMMINISTRATORE,
            must_change_password=False,
        )


def test_api_global_search_restituisce_json_e_pagina_renderizza(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_utente(app)
    repo = GlobalSearchRepository(default_global_search_db_path(app.config["SEARCH_INDEX"]))
    try:
        repo.upsert_document(
            GlobalSearchDocument(
                tenant_id="default",
                entity_type="cliente",
                entity_id="C1",
                title="Mario Rossi",
                body="Codice fiscale RSSMRA80A01H501U",
                source_module="clienti",
                source_url="/clienti/C1",
                metadata={"codice_fiscale": "RSSMRA80A01H501U"},
            )
        )
    finally:
        repo.close()

    with app.test_client() as client:
        client.post("/login", data={"username": "operatore", "password": "Operatore123!"}, follow_redirects=True)
        response = client.get("/api/global-search?q=RSSMRA80A01H501U")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["results"][0]["entity_type"] == "cliente"

        page = client.get("/global-search?q=Rossi")
        assert page.status_code == 200
        assert "Ricerca Studio" in page.get_data(as_text=True)
