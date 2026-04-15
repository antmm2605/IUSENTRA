import json
from pathlib import Path

from flask import g

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
                    "indirizzo": "Via Roma 20",
                    "city": "Taurianova",
                    "province": "RC",
                    "telefono": "0966 654321",
                    "email": "studio.refactor@example.it",
                },
                "pec": {
                    "indirizzo": "studio.refactor@pec.example.it",
                    "password": "segreta",
                    "smtp_host": "smtp.pec.aruba.it",
                    "smtp_port": 465,
                    "imap_host": "imaps.pec.aruba.it",
                    "imap_port": 993,
                    "use_ssl": True,
                },
                "smtp": {
                    "host": "smtp.office365.com",
                    "port": 587,
                    "username": "studio.refactor@example.it",
                    "from_address": "studio.refactor@example.it",
                    "from_name": "Studio Refactor",
                    "use_tls": True,
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
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "editor_layout.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione" / "parcelle.json"),
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


def test_route_domini_estratti_restano_operativi(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code == 302

        for path in (
            "/profilo",
            "/agenda",
            "/scadenziario",
            "/workspace-intelligente",
            "/telematico",
            "/polisWeb",
            "/pdp",
            "/pat",
            "/sigit",
            "/tribunali",
            "/tariffario",
            "/clienti",
            "/cartelle-condivise",
            "/messaggi",
            "/backup",
            "/cerca",
            "/portali/pst/acquisizione",
            "/deposito/checklist",
            "/guida/firma-digitale",
            "/impostazioni/calendario",
            "/privacy/registro",
            "/soggetti",
            "/admin/database",
        ):
            response = client.get(path)
            assert response.status_code == 200, path


def test_web_app_dimagrisce_e_registra_i_moduli_estratti_finali():
    web_app = (REPO_ROOT / "web/app.py").read_text(encoding="utf-8")

    for symbol in (
        "register_clienti_routes",
        "register_clienti_workspace_routes",
        "register_condivisioni_routes",
        "register_messages_routes",
        "register_backup_routes",
        "register_health_routes",
        "register_export_routes",
        "register_search_routes",
        "register_sync_runtime_routes",
        "register_fascicoli_management_routes",
        "register_tariffario_routes",
        "register_fascicoli_document_routes",
        "register_fascicoli_editor_routes",
        "register_fascicoli_core_routes",
        "register_fascicoli_pdp_routes",
        "register_fascicoli_signature_routes",
        "register_reference_lookup_routes",
        "register_telematico_local_signer_routes",
        "register_telematico_portali_routes",
    ):
        assert f"from web.bootstrap.{symbol.replace('register_', '').replace('_routes', '_routes')} import {symbol}" in web_app
        assert f"{symbol}(" in web_app

    assert web_app.count("@app.route") == 0
    assert len(web_app.splitlines()) < 7000


def test_i_moduli_bootstrap_restano_governabili():
    bootstrap_dir = REPO_ROOT / "web/bootstrap"
    default_limit = 650
    per_file_limits = {
        "deposito_routes.py": 1000,
        "scadenziario_routes.py": 700,
        "fascicoli_pdp_routes.py": 900,
        "telematico_portali_routes.py": 800,
    }

    oversized: list[str] = []
    for path in sorted(bootstrap_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        lines = len(path.read_text(encoding="utf-8").splitlines())
        limit = per_file_limits.get(path.name, default_limit)
        if lines > limit:
            oversized.append(f"{path.name}: {lines} righe (limite {limit})")

    assert not oversized, "Moduli bootstrap troppo grandi:\n" + "\n".join(oversized)


def test_template_principali_usano_copy_italiana_e_date_localizzate():
    template_checks = {
        "web/templates/base.html": ["Panoramica", "Operazione completata", "Preparazione Udienza Guidata"],
        "web/templates/admin/base.html": ["Esci", "Piattaforma"],
        "web/templates/dashboard.html": ["Panoramica dello studio"],
        "web/templates/agenda.html": ["Sincronizzazione automatica", "Configura sincronizzazione calendario"],
        "web/templates/impostazioni/index.html": ["Companion locale sul dispositivo cliente", "Prepara runtime automatico"],
        "web/templates/notifiche/pannello.html": ["Invia messaggio", "Registro notifiche"],
        "web/templates/wizard_pro/index.html": [
            "Preparazione Udienza Guidata",
            "Seleziona il fascicolo da cui avviare la preparazione dell'udienza",
        ],
        "web/templates/workspace_intelligente.html": ["Assistente operativo locale", "Ultima sincronizzazione"],
        "web/templates/portale/base.html": ["Operazione completata", "Inizio"],
        "web/templates/telematico_dashboard.html": ["Centro Servizi Telematici", "Ultimo allineamento"],
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


def test_lex_frontend_allinea_smalltalk_e_guardie_legali():
    js_content = (REPO_ROOT / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")

    assert "function looksLikeSmallTalk(text)" in js_content
    assert "legalReferenceGuardActive" in js_content
    assert "Non ho ancora una pronuncia verificata da citare con numero e PDF." in js_content
    assert "countIntentWords(clean) <= 4 && !matchFocusRule(clean)" not in js_content


def test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ollama:" in compose
    assert 'profiles: ["ollama-sidecar"]' in compose
    assert "image: ollama/ollama:latest" in compose
    assert "PCT_LOCAL_AI_BASE_URL: ${PCT_LOCAL_AI_BASE_URL:-http://host.docker.internal:11434/api}" in compose
    assert 'host.docker.internal:host-gateway' in compose


def test_runtime_cloud_hosted_sposta_ai_locale_su_storage_effimero(monkeypatch, tmp_path: Path):
    from web.app import create_app

    monkeypatch.setenv("RAILWAY_PROJECT_ID", "proj-test")
    monkeypatch.delenv("PCT_LOCAL_AI_DB", raising=False)
    monkeypatch.delenv("PCT_LOCAL_AI_MODELS_DIR", raising=False)
    monkeypatch.delenv("PCT_LOCAL_AI_AUTO_BOOTSTRAP", raising=False)

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    assert Path(app.config["LOCAL_AI_DB"]).as_posix() == "/tmp/hacs-runtime/local_ai/local_ai.db"
    assert Path(app.config["LOCAL_AI_MODELS_DIR"]).as_posix() == "/tmp/hacs-runtime/local_ai/models"
    assert app.config["LOCAL_AI_AUTO_BOOTSTRAP"] is False


def test_runtime_cloud_hosted_ignora_percorsi_ai_del_tenant(monkeypatch, tmp_path: Path):
    from web.services.local_ai_runtime import get_local_ai_service

    monkeypatch.setenv("RAILWAY_PROJECT_ID", "proj-test")
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_request_context("/"):
        g.data_paths = {
            "LOCAL_AI_DB": "/data/tenants/demo/intelligence/local_ai.db",
            "LOCAL_AI_MODELS_DIR": "/data/tenants/demo/intelligence/models",
        }
        service = get_local_ai_service()

    assert service.db_path.as_posix() == "/tmp/hacs-runtime/local_ai/local_ai.db"
    assert service.models_path.as_posix() == "/tmp/hacs-runtime/local_ai/models"


def test_scss_governance_usa_bundle_modulari_e_niente_style_inline():
    app_scss = (REPO_ROOT / "web/static/scss/app.scss").read_text(encoding="utf-8")
    assert "@use 'components/feedback';" in app_scss
    assert "@use 'components/compact-panels';" in app_scss
    assert "@use 'components/local-ai-assistant';" in app_scss
    assert "@use 'components/pct-lex-assistant';" in app_scss
    assert "@use 'pages/dashboard';" in app_scss
    assert "@use 'pages/hearing-preparation';" in app_scss
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
        lex_context = client.get("/polisWeb/local-signer/download/lex-document-context")
        visible_signature = client.get("/polisWeb/local-signer/download/visible-signature")

    assert bridge.status_code == 200
    bridge_source = bridge.get_data(as_text=True)
    assert "class LocalAiHostBridge" in bridge_source
    assert "class OllamaLocalClient" in bridge_source

    assert lex_context.status_code == 200
    assert "build_attachment_prompt_block" in lex_context.get_data(as_text=True)
    assert visible_signature.status_code == 200
    assert "apply_visible_signature_stamp" in visible_signature.get_data(as_text=True)

    build_dist = (REPO_ROOT / "tools/build_dist.py").read_text(encoding="utf-8")
    build_windows = (REPO_ROOT / "tools/build_local_signer_windows_exe.ps1").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "tools/installa_local_signer_locale.ps1").read_text(encoding="utf-8")
    web_app = (REPO_ROOT / "web/app.py").read_text(encoding="utf-8")

    assert "local_ai_host_bridge.py" in build_dist
    assert "lex_document_context.py" in build_dist
    assert "local_ai_host_bridge.py" in build_windows
    assert "lex_document_context.py" in build_windows
    assert "visible_signature.py" in build_windows
    assert "local_ai_host_bridge.py" in installer
    assert "lex_document_context.py" in installer
    assert "visible_signature.py" in installer
    assert "/polisWeb/local-signer/download/local-ai-bridge" in web_app
    assert "/polisWeb/local-signer/download/lex-document-context" in web_app
    assert "/polisWeb/local-signer/download/visible-signature" in web_app


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
    fascicolo_component = (REPO_ROOT / "web/templates/components/fascicolo_smart_board.html").read_text(encoding="utf-8")
    workspace_template = (REPO_ROOT / "web/templates/workspace_intelligente.html").read_text(encoding="utf-8")
    bridge_js = (REPO_ROOT / "web/static/js/local-ai-browser-bridge.js").read_text(encoding="utf-8")
    fascicolo_js = (REPO_ROOT / "web/static/js/fascicolo-ai.js").read_text(encoding="utf-8")
    workspace_js = (REPO_ROOT / "web/static/js/workspace-ai.js").read_text(encoding="utf-8")

    assert '{% include "components/fascicolo_smart_board.html" %}' in fascicolo_template
    assert "/static/js/local-ai-browser-bridge.js?v={{ app_version }}" in fascicolo_template
    assert "/static/js/fascicolo-ai.js?v={{ app_version }}" in fascicolo_template
    assert "async function askFascicoloAi" not in fascicolo_template
    assert "async function _refreshFascicoloAiRuntime" not in fascicolo_template
    assert 'id="fascicolo-ai-root"' in fascicolo_component
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in fascicolo_component
    assert 'data-server-context-url="{{ url_for(\'api_fascicolo_ai_context\', id_fasc=fascicolo.id) }}"' in fascicolo_component

    assert 'id="workspace-ai-root"' in workspace_template
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in workspace_template
    assert "/static/js/local-ai-browser-bridge.js?v={{ app_version }}" in workspace_template
    assert "/static/js/workspace-ai.js?v={{ app_version }}" in workspace_template
    assert "async function askWorkspaceAi" not in workspace_template
    assert "async function refreshWorkspaceAiRuntime" not in workspace_template

    assert "window.HacsLocalAiBrowserBridge" in bridge_js
    assert "/ai/rag/query" in bridge_js
    assert "/ai/rag/query/stream" in bridge_js
    assert "/ai/attachments/parse" in bridge_js
    assert "/ping" in bridge_js
    assert "127.0.0.1:27272" in bridge_js
    assert "fetch(config.localSignerUrl + '/ai/status', {\n        method: 'GET',\n      });" in bridge_js
    assert "parseServerAttachments" in bridge_js
    assert "parseCompanionAttachments" in bridge_js
    assert "fetchCompanionPing" in bridge_js
    assert "isCompanionTransportError" in bridge_js
    assert "companionRuntimeHelp" in bridge_js
    assert "streamCompanionRagQuery" in bridge_js
    assert "renderCompanionHelp" in fascicolo_js
    assert "renderCompanionRuntimeHelp" in fascicolo_js
    assert "fetchServerContext" in fascicolo_js
    assert "runCompanionRagQuery" in fascicolo_js
    assert "renderCompanionHelp" in workspace_js
    assert "renderCompanionRuntimeHelp" in workspace_js
    assert "fetchServerContext" in workspace_js
    assert "runCompanionRagQuery" in workspace_js


def test_lex_assistant_usa_componente_esterno_e_posizione_persistente():
    base_template = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")
    widget_template = (REPO_ROOT / "web/templates/components/pct_ai_widget.html").read_text(encoding="utf-8")
    widget_docs_js = (REPO_ROOT / "web/static/js/pct-lex-assistant-documents.js").read_text(encoding="utf-8")
    widget_voice_js = (REPO_ROOT / "web/static/js/pct-lex-assistant-voice.js").read_text(encoding="utf-8")
    widget_js = (REPO_ROOT / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")
    widget_scss = (REPO_ROOT / "web/static/scss/components/_pct-lex-assistant.scss").read_text(encoding="utf-8")
    widget_icon = REPO_ROOT / "web/static/img/lex-mark.png"

    assert '{% include "components/pct_ai_widget.html" %}' in base_template
    assert "/static/js/local-ai-browser-bridge.js?v={{ app_version }}" in base_template
    assert "/static/js/pct-lex-assistant-documents.js?v={{ app_version }}" in base_template
    assert "/static/js/pct-lex-assistant-voice.js?v={{ app_version }}" in base_template
    assert "/static/js/pct-lex-assistant.js?v={{ app_version }}" in base_template

    assert 'data-chat-url="{{ url_for(\'assistente.assistente_chat\') }}"' in widget_template
    assert 'data-status-url="{{ url_for(\'assistente.assistente_stato\') }}"' in widget_template
    assert 'data-server-context-url="{{ url_for(\'assistente.assistente_context\') }}"' in widget_template
    assert 'data-warmup-url="{{ url_for(\'assistente.assistente_warmup\') }}"' in widget_template
    assert 'data-server-attachments-url="{{ url_for(\'assistente.assistente_attachments\') }}"' in widget_template
    assert 'data-export-document-url="{{ url_for(\'assistente.assistente_documento\') }}"' in widget_template
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in widget_template
    assert 'data-lex-icon-url="{{ url_for(\'static\', filename=\'img/lex-mark.png\') }}?v={{ app_version }}"' in widget_template
    assert "data-local-signer-setup-windows" in widget_template
    assert 'data-ai-mode="{{ \'local\' if request.host.split(\':\')[0] in [\'localhost\', \'127.0.0.1\'] else \'remote\' }}"' in widget_template
    assert 'data-pct-ai-drag-handle="true"' in widget_template
    assert '<p class="mb-0">Ciao, sono Lex.</p>' in widget_template
    assert "Ti supporto su fascicoli" not in widget_template
    assert "Carica documenti" in widget_template
    assert "Scarica il riepilogo della conversazione" in widget_template
    assert "Apri Lex a tutto schermo" in widget_template
    assert "Detta la richiesta a Lex" in widget_template
    assert "Ridimensiona la finestra di Lex" in widget_template
    assert "pct-ai-brand-mark" in widget_template
    assert "pct-ai-fab__label" not in widget_template
    assert "pct-ai-header__subtitle" not in widget_template
    assert "<script>" not in widget_template
    assert widget_icon.exists()

    assert "parseAttachments" in widget_docs_js
    assert "buildPromptBlock" in widget_docs_js
    assert "triggerDownload" in widget_docs_js
    assert "buildGeneratedDocumentActions" in widget_docs_js
    assert "downloadGeneratedDocx" in widget_docs_js
    assert "downloadGeneratedMarkdown" in widget_docs_js
    assert "suggestGeneratedTitle" in widget_docs_js
    assert "data-generated-download" in widget_docs_js
    assert "SpeechRecognition" in widget_voice_js or "webkitSpeechRecognition" in widget_voice_js
    assert "speechSynthesis" in widget_voice_js
    assert "DEFAULT_SILENCE_MS = 3000" in widget_voice_js
    assert "recognition.continuous = true" in widget_voice_js
    assert "preferFemale" in widget_voice_js
    assert "splitSpeechChunks" in widget_voice_js
    assert "NATURAL_HINTS" in widget_voice_js
    assert "window.setTimeout(speakNext, 80)" in widget_voice_js
    assert "window.localStorage" in widget_js
    assert "window.sessionStorage" in widget_js
    assert "saveConversationMemory" in widget_js
    assert "restoreConversationMemory" in widget_js
    assert "HISTORY_LIMIT = 12" in widget_js
    assert "primeAssistantContext" in widget_js
    assert "widget.dataset.warmupUrl" in widget_js
    assert "state.contextWarmStarted = true" in widget_js
    assert "buildThinkingNote" in widget_js
    assert "Sto pensando" in widget_js
    assert "Riflessione" in widget_js
    assert "buildThinkingBubbleHtml" in widget_js
    assert "renderReflectionStatus" in widget_js
    assert "pct-ai-status-pill" in widget_js
    assert "pct-ai-widget--fullscreen" in widget_js
    assert "setFullscreen" in widget_js
    assert "toggleFullscreen" in widget_js
    assert "closeAssistant" in widget_js
    assert "state.fullscreen = false" in widget_js
    assert "if (!state.open && state.fullscreen && options.exitFullscreen !== false)" in widget_js
    assert "setFullscreen(false, { silent: true });" in widget_js
    assert "if (!state.open && saved.fullscreen)" in widget_js
    assert "state.fullscreen = Boolean(saved.fullscreen && state.open);" in widget_js
    assert "resolveConversationFocus" in widget_js
    assert "renderReferenceLabel" in widget_js
    assert "appendMetaMessage" not in widget_js
    assert "assistantAvatarMarkup" in widget_js
    assert "dataset.lexIconUrl" in widget_js
    assert "resetPosition" in widget_js
    assert "startResize" in widget_js
    assert "handleUpload" in widget_js
    assert "speakAnswer" in widget_js
    assert "pct-ai-widget--custom" in widget_js
    assert "data-pct-ai-drag-handle" in widget_template
    assert "dataset.chatUrl" in widget_js
    assert "dataset.statusUrl" in widget_js
    assert "generatedDocumentPayload" in widget_js
    assert "renderGeneratedDocumentActions" in widget_js
    assert "documentsHelper" in widget_js
    assert "voiceHelper" in widget_js
    assert "fetchServerContext" in widget_js
    assert "streamCompanionRagQuery" in widget_js
    assert "prependSocialPrefix" in widget_js
    assert "sanitizeLexAnswer" in widget_js
    assert "stripArtificialPlaceholders" in widget_js
    assert "normalizeAssistantPayload" in widget_js
    assert "social_prefix" not in widget_js
    assert "social_only" in widget_js
    assert "overview_today" in widget_js
    assert "GENERIC_OPERATIONAL_FOLLOW_UP_PATTERNS" in widget_js
    assert "Ciao, sono Lex." in widget_js
    assert "Riferimento:" in widget_js
    assert "<div class=\"fw-semibold small mb-1\">Fonti</div>" not in widget_js
    assert "buildAnswerHtml" in widget_js
    assert "companionHelp" in widget_js
    assert "renderCompanionRuntimeHelp" in widget_js
    assert "isCompanionTransportError" in widget_js
    assert "renderServerPreparationHelp" in widget_js
    assert "__companionStage" in widget_js
    assert "Preparazione richiesta non riuscita" in widget_js
    assert "Sessione scaduta o non autorizzata" in widget_js
    assert "Companion locale raggiunto, ma la richiesta non e\\' andata a buon fine" in widget_js
    assert "Local Signer raggiungibile, ma il modulo AI locale non e\\' operativo su questo dispositivo." in widget_js
    assert "remoteHosted" in widget_js
    assert "Lex sta scrivendo dal dispositivo locale" not in widget_js
    assert "Risposta generata sul dispositivo locale." in widget_js
    assert "Companion locale non raggiungibile, attivo fallback sul runtime locale di HACS..." in widget_js
    assert "sendLocal(text);" in widget_js
    assert "payload.answer = prependSocialPrefix(preparedSocialPrefix, payload.answer || '')" not in widget_js
    assert "partial = prependSocialPrefix(preparedSocialPrefix, partial);" not in widget_js
    assert "pct-ai-thinking-copy" in widget_scss
    assert "pct-ai-status-pill--inline" in widget_scss
    assert "pct-ai-widget--fullscreen" in widget_scss
    assert ".pct-ai-widget--fullscreen.pct-ai-widget--open .pct-ai-fab" in widget_scss

    assert ".pct-ai-widget" in widget_scss
    assert ".pct-ai-brand-mark" in widget_scss
    assert ".pct-ai-widget--custom" in widget_scss
    assert ".pct-ai-drag-hint" in widget_scss
    assert "cursor: move;" in widget_scss
    assert ".pct-ai-msg--meta" in widget_scss
    assert ".pct-ai-bubble--meta" in widget_scss
    assert ".pct-ai-status-pill" in widget_scss
    assert ".pct-ai-reference" in widget_scss
    assert "@keyframes pct-lex-thinking-pulse" in widget_scss
    assert "@keyframes pct-lex-soft-blink" in widget_scss
    assert ".pct-ai-toolbar" in widget_scss
    assert ".pct-ai-attachments" in widget_scss
    assert ".pct-ai-resize-handle" in widget_scss
    assert ".pct-ai-generated-actions" in widget_scss
    assert ".pct-ai-generated-btn" in widget_scss


def test_contesto_lex_compatta_le_sezioni_e_limita_le_fonti():
    context_service = (REPO_ROOT / "web/services/assistente_studio_context.py").read_text(encoding="utf-8")
    cache_service = (REPO_ROOT / "web/services/assistente_context_cache.py").read_text(encoding="utf-8")
    focus_service = (REPO_ROOT / "web/services/assistente_conversation_focus.py").read_text(encoding="utf-8")
    live_web_service = (REPO_ROOT / "web/services/assistente_live_web.py").read_text(encoding="utf-8")
    followup_service = (REPO_ROOT / "web/services/assistente_followup.py").read_text(encoding="utf-8")
    social_service = (REPO_ROOT / "web/services/assistente_social.py").read_text(encoding="utf-8")
    social_intent_service = (REPO_ROOT / "web/services/assistente_social_intent.py").read_text(encoding="utf-8")
    today_summary_service = (REPO_ROOT / "web/services/assistente_today_summary.py").read_text(encoding="utf-8")
    language_guidance_service = (REPO_ROOT / "web/services/assistente_language_guidance.py").read_text(encoding="utf-8")
    competence_service = (REPO_ROOT / "web/services/assistente_competencies.py").read_text(encoding="utf-8")
    web_execution_service = (REPO_ROOT / "web/services/assistente_web_execution.py").read_text(encoding="utf-8")
    assistente_blueprint = (REPO_ROOT / "web/blueprints/assistente.py").read_text(encoding="utf-8")
    lex_blueprint = (REPO_ROOT / "lex/blueprint.py").read_text(encoding="utf-8")
    lex_routes = (REPO_ROOT / "lex/routes.py").read_text(encoding="utf-8")
    lex_service = (REPO_ROOT / "lex/service.py").read_text(encoding="utf-8")
    lex_orchestrator = (REPO_ROOT / "lex/orchestrator.py").read_text(encoding="utf-8")
    assistente_prompt = (REPO_ROOT / "web/services/assistente_prompt.py").read_text(encoding="utf-8")

    assert "def _select_detail_sections" in context_service
    assert "def _select_detail_sections_for_chat" in context_service
    assert "def _should_include_live_web" in context_service
    assert "def _should_force_web_fallback" in context_service
    assert "def _has_specific_local_context" in context_service
    assert "resolve_conversation_focus" in context_service
    assert "_DEFAULT_DETAIL_SECTION_TITLES" in context_service
    assert "_CHAT_DETAIL_SECTION_TITLES" in context_service
    assert "_SECTION_KEYWORDS" in context_service
    assert "_cached_section_payload" in context_service
    assert "_SECTION_CACHE_TTLS" in context_service
    assert "_SECTION_DEPENDENCY_KEYS" in context_service
    assert 'chat_mode = str(mode or "").strip().lower() == "chat"' in context_service
    assert "selected_detail_titles = (" in context_service
    assert "force_web_fallback = web_execution_requested or _should_force_web_fallback(" in context_service
    assert '"sources": deduped_sources[:10 if chat_mode else 12]' in context_service
    assert 'research_strategy = _clean_spaces(focus.get("research_strategy"))' in context_service
    assert 'Ricerca ampia su sentenze civili: Lex deve partire dalle pronunce civili piu\' recenti' in context_service
    assert '"web_fallback_used": bool(force_web_fallback)' in context_service
    assert "warm_lex_studio_context" in context_service
    assert "resolve_competence_labels" in context_service
    assert "resolve_competence_section_titles" in context_service
    assert '"competence_labels": competence_labels' in context_service
    assert "cached_compute" in cache_service
    assert "build_file_fingerprint" in cache_service
    assert "question_signature" in cache_service
    assert "resolve_conversation_focus" in focus_service
    assert "def _is_civil_case_law_query" in focus_service
    assert "_TOPIC_RULES" in focus_service
    assert "_FOLLOW_UP_MARKERS" in focus_service
    assert "primary_competence_profile" in focus_service
    assert '"topic": "sentenze_civili"' in focus_service
    assert '"research_strategy": "auto_narrow_recent_civil_case_law"' in focus_service
    assert "resolve_web_execution_intent" in focus_service
    assert '"research_strategy": str(resolved_rule.get("research_strategy") or "").strip()' in focus_service
    assert '"web_execution_requested": bool(web_intent.requested)' in focus_service
    assert '"inherited_previous_theme": bool(web_intent.inherited_previous_theme)' in focus_service
    assert "_FALLBACK_DEFAULT_SOURCE_IDS" in live_web_service
    assert "force: bool = False" in live_web_service
    assert "explicit_source_ids" in live_web_service
    assert "resolve_effective_query as resolve_web_effective_query" in followup_service
    assert "is_web_execution_request as is_web_execution_command" in followup_service
    assert "classify_social_message" in social_service
    assert "build_social_reply" in social_service
    assert "prepend_social_prefix" in social_service
    assert "is_social_only_intent" in social_service
    assert "class SocialRoutingResult" in social_intent_service
    assert "resolve_social_and_operational_intent" in social_intent_service
    assert "build_daily_overview_lead" in social_intent_service
    assert "build_social_only_reply" in social_intent_service
    assert "build_today_operational_summary" in today_summary_service
    assert "_TODAY_SECTION_FACTORIES" in today_summary_service
    assert "class LanguageGuidance" in language_guidance_service
    assert "def build_language_guidance" in language_guidance_service
    assert "Controllo io sul web. Parto dalle sentenze civili piu' recenti e rilevanti" in language_guidance_service
    assert "class LexCompetenceProfile" in competence_service
    assert "def build_competence_catalog_prompt" in competence_service
    assert "Centro Servizi Telematici" in competence_service
    assert "Tariffario, preventivi, fatturazione e pagamenti" in competence_service
    assert "class WebExecutionIntent" in web_execution_service
    assert "is_web_execution_request" in web_execution_service
    assert "resolve_effective_query" in web_execution_service
    assert "resolve_web_execution_intent" in web_execution_service
    assert "create_lex_blueprint" in assistente_blueprint
    assert "LexDependencies" in assistente_blueprint
    assert "warm_ollama_chat_runtime" in assistente_blueprint
    assert "resolved_ollama_runtime" in assistente_blueprint
    assert "_build_lex_dependencies" in assistente_blueprint
    assert "resolve_social_and_operational_intent" in assistente_blueprint
    assert "build_today_operational_summary" in assistente_blueprint
    assert "build_language_guidance" in assistente_blueprint
    assert 'assistente = create_lex_blueprint(' in assistente_blueprint
    assert "register_routes(bp, service=service, login_required=login_required)" in lex_blueprint
    assert 'Blueprint("assistente", __name__)' in lex_blueprint
    assert 'bp.add_url_rule("/api/assistente/warmup"' in lex_routes
    assert "def assistente_chat()" in lex_routes
    assert "LexOrchestrator" in lex_service
    assert "build_context_response" in lex_orchestrator
    assert "chat_response" in lex_orchestrator
    assert "messages_with_effective_question" in lex_orchestrator
    assert "social_context_payload" in lex_orchestrator
    assert "direct_answer_payload" in lex_orchestrator
    assert '"query_type": "assistente_chat"' in lex_orchestrator
    assert '"daily_overview_lead": opening_line' in lex_orchestrator
    assert '"language_mode": str(language_guidance.mode or "").strip()' in lex_orchestrator
    assert '"competence_labels": list(studio_context.get("competence_labels") or [])' in lex_orchestrator
    assert '"social_prefix": str(social_prefix or "").strip()' in lex_orchestrator
    assert '"focus_label": str(studio_context.get("focus_label") or "").strip()' in lex_orchestrator
    assert "web_fallback_used = bool(studio_context.get(\"web_fallback_used\")) or bool(" in lex_orchestrator
    assert "web_execution_requested = bool(studio_context.get(\"web_execution_requested\")) or bool(followup.is_web_request)" in lex_orchestrator
    assert '"web_fallback_used": web_fallback_used' in lex_orchestrator
    assert '"web_execution_requested": web_execution_requested' in lex_orchestrator
    assert "build_assistente_prompt" in assistente_prompt
    assert "_LEX_VOICE_PROMPT" in assistente_prompt
    assert "_LEX_WRITING_PROMPT" in assistente_prompt
    assert "_LEX_OPERATION_GUARDRAILS" in assistente_prompt
    assert "_LEX_COMPETENCE_COVERAGE_PROMPT" in assistente_prompt
    assert "_LEX_CONTEXT_ROUTING_PROMPT" in assistente_prompt
    assert "_LEX_WEB_EXECUTION_PROMPT" in assistente_prompt
    assert "_LEX_SOCIAL_PROMPT" in assistente_prompt
    assert "build_competence_catalog_prompt" in assistente_prompt
    assert "build_competence_prompt_blocks" in assistente_prompt
    assert "Se c'e' gia' una richiesta operativa o di ricerca, non aprire con saluti" in assistente_prompt
    assert "ricerca web sentenze civili" in assistente_prompt
    assert "Non usare mai testo-segnaposto o placeholder artificiali" in assistente_prompt
    assert "_LEX_COMPETENCE_COVERAGE_PROMPT = build_competence_catalog_prompt()" in assistente_prompt
    assert "Apertura iniziale da mantenere:" in assistente_prompt


def test_preparazione_udienza_guidata_usa_componenti_modulari_e_js_esterno():
    base_template = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")
    index_template = (REPO_ROOT / "web/templates/wizard_pro/index.html").read_text(encoding="utf-8")
    nuovo_template = (REPO_ROOT / "web/templates/wizard_pro/nuovo.html").read_text(encoding="utf-8")
    step_template = (REPO_ROOT / "web/templates/wizard_pro/step.html").read_text(encoding="utf-8")
    completo_template = (REPO_ROOT / "web/templates/wizard_pro/completo.html").read_text(encoding="utf-8")
    nav_component = (REPO_ROOT / "web/templates/components/hearing_preparation_module_nav.html").read_text(encoding="utf-8")
    stepper_component = (REPO_ROOT / "web/templates/components/hearing_preparation_stepper.html").read_text(encoding="utf-8")
    list_component = (REPO_ROOT / "web/templates/components/hearing_preparation_case_list.html").read_text(encoding="utf-8")
    summary_component = (REPO_ROOT / "web/templates/components/hearing_preparation_summary_panel.html").read_text(encoding="utf-8")
    service = (REPO_ROOT / "web/services/hearing_preparation_dashboard.py").read_text(encoding="utf-8")
    script = (REPO_ROOT / "web/static/js/hearing-preparation-dashboard.js").read_text(encoding="utf-8")
    scss = (REPO_ROOT / "web/static/scss/pages/_hearing-preparation.scss").read_text(encoding="utf-8")

    assert "Preparazione Udienza Guidata" in base_template
    assert "Wizard Pro</span>" not in base_template

    assert '{% include "components/hearing_preparation_module_nav.html" %}' in index_template
    assert '{% include "components/hearing_preparation_stepper.html" %}' in index_template
    assert '{% include "components/hearing_preparation_case_list.html" %}' in index_template
    assert '{% include "components/hearing_preparation_summary_panel.html" %}' in index_template
    assert "/static/js/hearing-preparation-dashboard.js?v={{ app_version }}" in index_template
    assert "Nuova preparazione" in index_template
    assert "Riprendi bozza" in index_template
    assert "data-hearing-filter=\"search\"" in index_template
    assert "<script>" not in index_template
    assert "Wizard Pro" not in nuovo_template
    assert "Wizard Pro" not in step_template
    assert "Wizard Pro" not in completo_template
    assert "Preparazione udienza completata" in completo_template
    assert "Avvia preparazione udienza" in nuovo_template
    assert "Completa preparazione" in step_template

    assert "Navigazione modulo" in nav_component
    assert "Preparazione Udienza" in nav_component
    assert "Passo 1 di 6" in stepper_component
    assert "Selezione Fascicolo" in stepper_component
    assert "Dati Udienza" in stepper_component
    assert "Parti e Difensori" in stepper_component
    assert "Documenti e Allegati" in stepper_component
    assert "Note Strategiche" in stepper_component
    assert "Controllo Finale" in service
    assert "Avanzamento pratica" in list_component
    assert "Apri fascicolo" in list_component
    assert "Riepilogo fascicolo" in summary_component
    assert "Azioni rapide" in summary_component

    assert 'querySelector("[data-hearing-preparation]")' in script
    assert "applyFilters" in script
    assert "resetFilters" in script
    assert "data-hearing-visible-count" in list_component

    assert ".hearing-prep-layout" in scss
    assert ".hearing-case-card" in scss
    assert ".hearing-prep-summary" in scss
    assert ".hearing-prep-mobile-cta" in scss


def test_preparazione_udienza_guidata_reindirizza_la_vecchia_route_nuovo(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/wizard-pro/nuovo?id_fascicolo=FASC001")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/wizard-pro/?id_fascicolo=FASC001")


def test_modal_firma_deposito_prevede_riavvio_local_signer():
    dettaglio = (REPO_ROOT / "web/templates/fascicoli/dettaglio.html").read_text(encoding="utf-8")
    deposito = (REPO_ROOT / "web/templates/fascicoli/deposito_prepara.html").read_text(encoding="utf-8")
    selector = (REPO_ROOT / "web/templates/components/firma_visibile_selector.html").read_text(encoding="utf-8")
    helper_js = (REPO_ROOT / "web/static/js/firma-visibile-mode.js").read_text(encoding="utf-8")

    assert "Riavvia Local Signer" in dettaglio
    assert "hacs-local-signer://restart" in dettaglio
    assert "riavvio_signer_consigliato" in dettaglio
    assert "sincronizzazione in tempo reale" in dettaglio
    assert "spazio limitato HACS ha sostituito la copia precedente" in dettaglio
    assert "sincronizzazione in tempo reale" in deposito
    assert "spazio limitato HACS ha sostituito la copia precedente" in deposito
    assert '{% from "components/firma_visibile_selector.html" import render_firma_visibile_selector %}' in dettaglio
    assert '{% from "components/firma_visibile_selector.html" import render_firma_visibile_selector %}' in deposito
    assert "{{ render_firma_visibile_selector('dettaglioFirma', firma_visibile_place) }}" in dettaglio
    assert "{{ render_firma_visibile_selector('depositoFirma', firma_visibile_place) }}" in deposito
    assert "/static/js/firma-visibile-mode.js?v={{ app_version }}" in dettaglio
    assert "/static/js/firma-visibile-mode.js?v={{ app_version }}" in deposito
    assert "Laterale verticale" in selector
    assert "In basso a destra" in selector
    assert 'data-signature-place="{{ place }}"' in selector
    assert "window.HacsFirmaVisibileMode" in helper_js
    assert "getSelectedMode" in helper_js
    assert "getSignaturePlace" in helper_js


def test_quadro_intelligente_fascicolo_e_collassabile_con_collegamenti_rapidi():
    dettaglio = (REPO_ROOT / "web/templates/fascicoli/dettaglio.html").read_text(encoding="utf-8")
    smart_board = (REPO_ROOT / "web/templates/components/fascicolo_smart_board.html").read_text(encoding="utf-8")
    app_scss = (REPO_ROOT / "web/static/scss/app.scss").read_text(encoding="utf-8")
    smart_board_scss = (REPO_ROOT / "web/static/scss/pages/_fascicolo-smart-board.scss").read_text(encoding="utf-8")

    assert '{% include "components/fascicolo_smart_board.html" %}' in dettaglio
    assert 'data-bs-target="#collapse-sezione-intelligenza-fascicolo"' in smart_board
    assert 'id="collapse-sezione-intelligenza-fascicolo"' in smart_board
    assert "Cambia stato" in smart_board
    assert "Azioni" in smart_board
    assert "Avanzamento pratica" in smart_board
    assert "Cliente" in smart_board
    assert "Parti del procedimento" in smart_board
    assert "Collegamenti rapidi" in smart_board
    assert "@use 'pages/fascicolo-smart-board';" in app_scss
    assert ".fascicolo-smart-board__quick-link" in smart_board_scss
    assert ".fascicolo-smart-board__hero" in smart_board_scss


def test_assistente_stato_usa_runtime_ollama_risolto(monkeypatch, tmp_path: Path):
    from web.app import create_app

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    class FakeResponse:
        def json(self):
            return {"models": [{"name": "gemma3:1b"}]}

    called = {}

    def fake_get(url, timeout):
        called["url"] = url
        called["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "web.blueprints.assistente.resolved_ollama_runtime",
        lambda: {
            "api_base_url": "http://host.docker.internal:11434/api",
            "base_url": "http://host.docker.internal:11434",
            "chat_model": "gemma3:1b",
            "keep_alive": "10m",
        },
    )
    monkeypatch.setattr("web.blueprints.assistente.requests.get", fake_get)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/api/assistente/stato")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["url"] == "http://host.docker.internal:11434"
    assert payload["modello_attivo"] == "gemma3:1b"
    assert called["url"] == "http://host.docker.internal:11434/api/tags"
    assert called["timeout"] == 3


def test_assistente_chat_usa_runtime_ollama_risolto(monkeypatch, tmp_path: Path):
    from web.app import create_app

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    class FakeStreamResponse:
        def iter_lines(self):
            yield json.dumps({"message": {"content": "Ciao"}, "done": False}).encode("utf-8")
            yield json.dumps({"done": True}).encode("utf-8")

    called = {}

    def fake_post(url, json=None, stream=None, timeout=None):
        called["url"] = url
        called["json"] = json or {}
        called["stream"] = stream
        called["timeout"] = timeout
        return FakeStreamResponse()

    monkeypatch.setattr(
        "web.blueprints.assistente.resolved_ollama_runtime",
        lambda: {
            "api_base_url": "http://host.docker.internal:11434/api",
            "base_url": "http://host.docker.internal:11434",
            "chat_model": "gemma3:1b",
            "keep_alive": "12m",
        },
    )
    monkeypatch.setattr("web.blueprints.assistente.requests.post", fake_post)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.post(
            "/api/assistente/chat",
            json={"messages": [{"role": "user", "content": "Qual e' lo stato del fascicolo?"}]},
        )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert called["url"] == "http://host.docker.internal:11434/api/chat"
    assert called["json"]["model"] == "gemma3:1b"
    assert called["json"]["keep_alive"] == "12m"
    assert called["stream"] is True
    assert called["timeout"] == 180
    assert '"token": "Ciao"' in body
    assert "[DONE]" in body
