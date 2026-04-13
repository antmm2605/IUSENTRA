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
        "web/templates/base.html": ["Panoramica", "Operazione completata"],
        "web/templates/admin/base.html": ["Esci", "Piattaforma"],
        "web/templates/dashboard.html": ["Panoramica dello studio"],
        "web/templates/agenda.html": ["Sincronizzazione automatica", "Configura sincronizzazione calendario"],
        "web/templates/impostazioni/index.html": ["Companion locale sul dispositivo cliente", "Prepara runtime automatico"],
        "web/templates/notifiche/pannello.html": ["Invia messaggio", "Registro notifiche"],
        "web/templates/workspace_intelligente.html": ["Assistente operativo locale", "Ultima sincronizzazione"],
        "web/templates/portale/base.html": ["Operazione completata", "Inizio"],
        "web/templates/telematico_dashboard.html": ["Cabina Telematica", "Ultimo allineamento"],
    }

    for relative_path, expected_snippets in template_checks.items():
        content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in expected_snippets:
            assert snippet in content

    locale_sensitive_templates = [
        "web/templates/base.html",
        "web/templates/dashboard.html",
        "web/templates/agenda.html",
        "web/templates/dettaglio_appuntamento.html",
        "web/templates/notifiche/pannello.html",
        "web/templates/portale/home.html",
        "web/templates/telematico_dashboard.html",
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
        assert "strftime('%H:%M')" not in content
        assert "strftime('%d/%m/%Y')" not in content

    base_content = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")
    assert "{{ oggi|fmt_data }}" in base_content
    telematico_content = (REPO_ROOT / "web/templates/telematico_dashboard.html").read_text(encoding="utf-8")
    assert "|fmt_dataora" in telematico_content


def test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ollama:" in compose
    assert 'profiles: ["ollama-sidecar"]' in compose
    assert "image: ollama/ollama:latest" in compose
    assert "PCT_LOCAL_AI_BASE_URL: ${PCT_LOCAL_AI_BASE_URL:-http://host.docker.internal:11434/api}" in compose
    assert 'host.docker.internal:host-gateway' in compose


def test_scss_governance_usa_bundle_modulari_e_niente_style_inline():
    app_scss = (REPO_ROOT / "web/static/scss/app.scss").read_text(encoding="utf-8")
    assert "@use 'components/feedback';" in app_scss
    assert "@use 'components/compact-panels';" in app_scss
    assert "@use 'components/local-ai-assistant';" in app_scss
    assert "@use 'components/pct-lex-assistant';" in app_scss
    assert "@use 'pages/dashboard';" in app_scss
    assert "@use 'pages/notifiche-whatsapp';" in app_scss
    assert "@use 'pages/settings';" in app_scss
    assert "@use 'pages/telematico-dashboard';" in app_scss
    assert "@use 'pages/workspace-intelligente';" in app_scss
    portal_scss = (REPO_ROOT / "web/static/scss/portal.scss").read_text(encoding="utf-8")
    assert "@use 'components/portale-shell';" in portal_scss
    assert "@use 'pages/portale-home';" in portal_scss

    for relative_path in (
        "web/templates/base.html",
        "web/templates/dashboard.html",
        "web/templates/impostazioni/index.html",
        "web/templates/notifiche/pannello.html",
        "web/templates/workspace_intelligente.html",
        "web/templates/portale/base.html",
        "web/templates/portale/home.html",
        "web/templates/telematico_dashboard.html",
    ):
        content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "<style>" not in content

    portale_base = (REPO_ROOT / "web/templates/portale/base.html").read_text(encoding="utf-8")
    assert "/static/css/portal.css?v={{ app_version }}" in portale_base


def test_impostazioni_js_e_esterno_e_senza_duplicazioni():
    template = (REPO_ROOT / "web/templates/impostazioni/index.html").read_text(encoding="utf-8")
    firma_js = (REPO_ROOT / "web/static/js/impostazioni-firma.js").read_text(encoding="utf-8")
    common_js = (REPO_ROOT / "web/static/js/impostazioni-common.js").read_text(encoding="utf-8")
    ai_js = (REPO_ROOT / "web/static/js/impostazioni-ai.js").read_text(encoding="utf-8")

    assert "/static/js/impostazioni-firma.js?v={{ app_version }}" in template
    assert "/static/js/impostazioni-common.js?v={{ app_version }}" in template
    assert "/static/js/impostazioni-ai.js?v={{ app_version }}" in template
    assert "function renderLocalAiStatus" not in template
    assert "async function refreshLocalAiStatus" not in template
    assert "async function runLocalAiBootstrap" not in template
    assert "<script>" not in template

    assert firma_js.count("function scegliModalita") == 1
    assert common_js.count("function togglePwd") == 1
    assert ai_js.count("function renderLocalAiStatus") == 1
    assert ai_js.count("async function refreshLocalAiStatus") == 1
    assert ai_js.count("async function runLocalAiBootstrap") == 1
    assert "127.0.0.1:27272" in ai_js
    assert "/ai/status" in ai_js
    assert "/ai/bootstrap" in ai_js
    assert "companion locale" in ai_js
    assert "fetch(config.localSignerUrl + '/ai/status?' + params.toString(), {\n      method: 'GET',\n    });" in ai_js
    assert "fetch(config.localSignerUrl + '/ai/bootstrap', {\n          method: 'POST'," in ai_js
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in template
    assert "data-local-signer-setup-windows" in template
    assert "Quando HACS e' online" in template


def test_local_signer_distribution_include_bridge_ai(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        bridge = client.get("/polisWeb/local-signer/download/local-ai-bridge")

    assert bridge.status_code == 200
    bridge_source = bridge.get_data(as_text=True)
    assert "class LocalAiHostBridge" in bridge_source
    assert "class OllamaLocalClient" in bridge_source

    build_dist = (REPO_ROOT / "tools/build_dist.py").read_text(encoding="utf-8")
    build_windows = (REPO_ROOT / "tools/build_local_signer_windows_exe.ps1").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "tools/installa_local_signer_locale.ps1").read_text(encoding="utf-8")
    web_app = (REPO_ROOT / "web/app.py").read_text(encoding="utf-8")

    assert "local_ai_host_bridge.py" in build_dist
    assert "local_ai_host_bridge.py" in build_windows
    assert "local_ai_host_bridge.py" in installer
    assert "/polisWeb/local-signer/download/local-ai-bridge" in web_app


def test_notifiche_whatsapp_usa_js_esterno_e_date_localizzate():
    template = (REPO_ROOT / "web/templates/notifiche/pannello.html").read_text(encoding="utf-8")
    script = (REPO_ROOT / "web/static/js/notifiche-whatsapp.js").read_text(encoding="utf-8")

    assert "/static/js/notifiche-whatsapp.js?v={{ app_version }}" in template
    assert "{% block extra_scripts %}" in template
    assert "<script>" not in template
    assert "strftime('%H:%M')" not in template
    assert "|fmt_ora" in template
    assert "|fmt_dataora" in template
    assert "Link WA" not in template
    assert "Apri il link WhatsApp" in template
    assert "showFeedback(" in script
    assert "dataset.promemoriaCount" in script


def test_ai_operativa_usa_bridge_browser_e_template_senza_logica_inline():
    fascicolo_template = (REPO_ROOT / "web/templates/fascicoli/dettaglio.html").read_text(encoding="utf-8")
    workspace_template = (REPO_ROOT / "web/templates/workspace_intelligente.html").read_text(encoding="utf-8")
    bridge_js = (REPO_ROOT / "web/static/js/local-ai-browser-bridge.js").read_text(encoding="utf-8")
    fascicolo_js = (REPO_ROOT / "web/static/js/fascicolo-ai.js").read_text(encoding="utf-8")
    workspace_js = (REPO_ROOT / "web/static/js/workspace-ai.js").read_text(encoding="utf-8")

    assert 'id="fascicolo-ai-root"' in fascicolo_template
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in fascicolo_template
    assert "/static/js/local-ai-browser-bridge.js?v={{ app_version }}" in fascicolo_template
    assert "/static/js/fascicolo-ai.js?v={{ app_version }}" in fascicolo_template
    assert "async function askFascicoloAi" not in fascicolo_template
    assert "async function _refreshFascicoloAiRuntime" not in fascicolo_template

    assert 'id="workspace-ai-root"' in workspace_template
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in workspace_template
    assert "/static/js/local-ai-browser-bridge.js?v={{ app_version }}" in workspace_template
    assert "/static/js/workspace-ai.js?v={{ app_version }}" in workspace_template
    assert "async function askWorkspaceAi" not in workspace_template
    assert "async function refreshWorkspaceAiRuntime" not in workspace_template

    assert "window.HacsLocalAiBrowserBridge" in bridge_js
    assert "/ai/rag/query" in bridge_js
    assert "127.0.0.1:27272" in bridge_js
    assert "fetch(config.localSignerUrl + '/ai/status', {\n        method: 'GET',\n      });" in bridge_js
    assert "renderCompanionHelp" in fascicolo_js
    assert "fetchServerContext" in fascicolo_js
    assert "runCompanionRagQuery" in fascicolo_js
    assert "renderCompanionHelp" in workspace_js
    assert "fetchServerContext" in workspace_js
    assert "runCompanionRagQuery" in workspace_js


def test_lex_assistant_usa_componente_esterno_e_posizione_persistente():
    base_template = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")
    widget_template = (REPO_ROOT / "web/templates/components/pct_ai_widget.html").read_text(encoding="utf-8")
    widget_js = (REPO_ROOT / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")
    widget_scss = (REPO_ROOT / "web/static/scss/components/_pct-lex-assistant.scss").read_text(encoding="utf-8")

    assert '{% include "components/pct_ai_widget.html" %}' in base_template
    assert "/static/js/local-ai-browser-bridge.js?v={{ app_version }}" in base_template
    assert "/static/js/pct-lex-assistant.js?v={{ app_version }}" in base_template

    assert 'data-chat-url="{{ url_for(\'assistente.assistente_chat\') }}"' in widget_template
    assert 'data-status-url="{{ url_for(\'assistente.assistente_stato\') }}"' in widget_template
    assert 'data-server-context-url="{{ url_for(\'assistente.assistente_context\') }}"' in widget_template
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in widget_template
    assert "data-local-signer-setup-windows" in widget_template
    assert 'data-ai-mode="{{ \'local\' if request.host.split(\':\')[0] in [\'localhost\', \'127.0.0.1\'] else \'remote\' }}"' in widget_template
    assert 'data-pct-ai-drag-handle="true"' in widget_template
    assert "posizione resta salvata su questo browser" in widget_template
    assert "<script>" not in widget_template

    assert "window.localStorage" in widget_js
    assert "resetPosition" in widget_js
    assert "pct-ai-widget--custom" in widget_js
    assert "data-pct-ai-drag-handle" in widget_template
    assert "dataset.chatUrl" in widget_js
    assert "dataset.statusUrl" in widget_js
    assert "fetchServerContext" in widget_js
    assert "runCompanionRagQuery" in widget_js
    assert "companionHelp" in widget_js
    assert "remoteHosted" in widget_js
    assert "Risposta generata sul dispositivo locale." in widget_js

    assert ".pct-ai-widget" in widget_scss
    assert ".pct-ai-widget--custom" in widget_scss
    assert ".pct-ai-drag-hint" in widget_scss
    assert "cursor: move;" in widget_scss
