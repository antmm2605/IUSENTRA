import json
from pathlib import Path

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
