import json
from pathlib import Path

from pct import __version__ as APP_VERSION
from web.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Refactor",
                    "avvocato": "Avv. Refactor",
                },
                "scheduler": {
                    "backup_ora": "03:30",
                    "wa_reminder_ora": "17:15",
                },
                "ai": {
                    "enabled": True,
                    "base_url": "http://127.0.0.1:11434/api",
                    "auto_bootstrap": True,
                    "chat_model": "gemma3:1b",
                    "embed_model": "embeddinggemma:300m",
                    "keep_alive": "12m",
                    "auto_index_documents": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(tmp_path / "clienti" / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "soggetti" / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "import_pst"),
        "VALIDATION_RUNS_DB": str(tmp_path / "intelligence" / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "workspace_intelligence.json"),
        "LOCAL_AI_DB": str(tmp_path / "intelligence" / "local_ai.db"),
        "LOCAL_AI_POLICY": str(REPO_ROOT / "config" / "ai-policy.json"),
        "LOCAL_AI_MODELS_DIR": str(tmp_path / "intelligence" / "models"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
    }


def test_create_app_applies_runtime_overrides_and_registers_blueprints(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    assert app.config["LOCAL_AI_CHAT_MODEL"] == "gemma3:1b"
    assert app.config["LOCAL_AI_EMBED_MODEL"] == "embeddinggemma:300m"
    assert app.config["OLLAMA_MODEL"] == "gemma3:1b"
    assert app.config["BACKUP_ORA"] == "03:30"
    assert app.config["WA_REMINDER_ORA"] == "17:15"

    expected_blueprints = {
        "api_v1",
        "portale",
        "fatturazione",
        "notifiche",
        "template_atti",
        "statistiche",
        "legal_intelligence",
        "giurisprudenza",
        "export_csv",
        "pagamenti",
        "admin",
        "impostazioni",
        "email_client",
        "assistente",
        "preventivi",
        "strumenti_legali",
        "applicazioni",
        "wizard_pro",
    }
    assert expected_blueprints.issubset(set(app.blueprints))


def test_auth_guard_keeps_login_public_and_redirects_protected_routes(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        login_page = client.get("/login")
        protected = client.get("/profilo")

    assert login_page.status_code == 200
    assert protected.status_code == 302
    assert protected.headers["Location"].endswith("/login?next=/profilo")


def test_template_runtime_registers_filters_and_globals(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_request_context("/"):
        globals_map = {}
        for processor in app.template_context_processors[None]:
            globals_map.update(processor())

    assert app.jinja_env.filters["fmt_data"]("2026-04-13") == "13/04/2026"
    assert app.jinja_env.filters["fmt_dataora"]("2026-04-13T09:45:00") == "13/04/2026 09:45"
    assert app.jinja_env.filters["fmt_data_estesa"]("2026-04-13") == "13 aprile 2026"
    assert (
        app.jinja_env.filters["fmt_data_estesa_con_giorno"]("2026-04-13")
        == "lunedì 13 aprile 2026"
    )
    assert (
        app.jinja_env.filters["fmt_data_breve_con_giorno"]("2026-04-13")
        == "lun 13 apr 2026"
    )
    assert app.jinja_env.filters["fmt_giorno_mese"]("2026-04-13") == "13 apr"
    assert app.jinja_env.filters["fmt_giorno_mese_anno"]("2026-04-13") == "13 apr 2026"
    assert app.jinja_env.filters["fmt_mese_breve"]("2026-04-13") == "apr"
    assert app.jinja_env.filters["fmt_ora"]("2026-04-13T09:45:00") == "09:45"
    assert globals_map["app_version"] == APP_VERSION
    assert globals_map["TipoAppuntamento"] is not None
    assert globals_map["recenti"] == []
    assert hasattr(globals_map["oggi"], "strftime")
    assert globals_map["mesi_italiani"][3] == "aprile"
    assert globals_map["giorni_settimana_brevi_italiani"][0] == "lun"


def test_pwa_routes_and_error_handlers_restano_registrati(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        service_worker = client.get("/sw.js")
        offline = client.get("/offline")
        missing = client.get("/percorso-inesistente")

    assert service_worker.status_code == 200
    assert "javascript" in service_worker.content_type
    assert offline.status_code == 200
    assert missing.status_code == 404


def test_template_principali_usano_copy_italiana_e_date_localizzate():
    template_checks = {
        "web/templates/base.html": ["Panoramica"],
        "web/templates/admin/base.html": ["Esci", "Piattaforma"],
        "web/templates/dashboard.html": ["Panoramica dello studio"],
        "web/templates/agenda.html": ["Sincronizzazione automatica", "Configura sincronizzazione calendario"],
        "web/templates/workspace_intelligente.html": ["Runtime locale", "Ultima sincronizzazione"],
    }

    for relative_path, expected_snippets in template_checks.items():
        content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in expected_snippets:
            assert snippet in content

    locale_sensitive_templates = [
        "web/templates/dashboard.html",
        "web/templates/agenda.html",
        "web/templates/dettaglio_appuntamento.html",
        "web/templates/portale/home.html",
        "web/templates/form_preventivo.html",
        "web/templates/clienti/cartella.html",
        "web/templates/cartelle_condivise.html",
    ]
    for relative_path in locale_sensitive_templates:
        content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "strftime('%A" not in content
        assert "strftime('%a" not in content
        assert "strftime('%B" not in content
        assert "strftime('%b" not in content
