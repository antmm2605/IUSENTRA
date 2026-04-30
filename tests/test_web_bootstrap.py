import json
import re
from pathlib import Path

from flask import g

from pct import __version__ as APP_VERSION
from pct.auth import GestioneUtenti, RuoloUtente
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.storage import StudioDB
from pct.tenant import GestioneTenant
from web.bootstrap.blueprint_registry import BLUEPRINT_REGISTRY
from web.bootstrap.flask_app_factory import create_flask_app
from web.bootstrap.runtime_bundle import build_application_runtime_bundle
from web.app import create_app
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data


REPO_ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_PATTERN = re.compile(
    r"\u00c3.|\u00c2.|\u00e2[\u20ac\u201a\u0192\u201e\u2026\u2020\u2021\u02c6\u2030\u0160\u2039\u0152\u017d\u2018\u2019\u201c\u201d\u2022\u2013\u2014\u02dc\u2122\u0161\u203a\u0153\u017e\u0178]|\u00e2\u0153.|\u00e2\u0161."
)


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
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(tmp_path / "auth" / "bootstrap_admin.json"),
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
        "TIMESHEET_DB": str(tmp_path / "timesheet" / "entries.json"),
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


def _seed_tenant_admin(
    app,
    *,
    studio_nome: str = "Studio Refactor",
    studio_slug: str = "studio-refactor",
    username: str = "studio-admin",
    password: str = "PasswordSicura!123",
):
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.get(studio_slug) or tm.crea(
        studio_nome,
        studio_slug,
        db_config={"mode": "SQLITE"},
    )
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio.slug)
    paths = tm.percorsi_dati(studio.slug)
    utenti = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
    )
    utenti_json = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    esistente = utenti.get_by_username(username)
    if esistente is None:
        esistente = utenti.crea(
            username=username,
            password=password,
            ruolo=RuoloUtente.AMMINISTRATORE,
            tenant_slug=studio.slug,
            must_change_password=False,
        )
    if utenti_json.get_by_username(username) is None:
        utenti_json.importa_utente_esistente(
            esistente,
            tenant_slug=studio.slug,
            preserve_id=True,
        )
    return studio, esistente


def test_create_app_applies_runtime_overrides_and_registers_blueprints(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    assert app.config["LOCAL_AI_CHAT_MODEL"] == "gemma3:1b"
    assert app.config["LOCAL_AI_EMBED_MODEL"] == "embeddinggemma:300m"
    assert app.config["OLLAMA_MODEL"] == "gemma3:1b"
    assert app.config["BACKUP_ORA"] == "03:30"
    assert app.config["WA_REMINDER_ORA"] == "17:15"

    expected_blueprints = {
        entry.name for entry in BLUEPRINT_REGISTRY if entry.is_enabled(app.config)
    }
    assert expected_blueprints.issubset(set(app.blueprints))
    assert app.config["PCT_SCHEDULER_WORKER"] is False
    assert "PCT_SCHEDULER" not in app.config


def test_create_app_portale_runtime_paths_seguono_data_root(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg.pop("PORTALE_DB")
    cfg.pop("PORTALE_UPLOADS")

    app = create_app(cfg)

    assert Path(app.config["PORTALE_DB"]) == tmp_path / "portale" / "portali.json"
    assert Path(app.config["PORTALE_UPLOADS"]) == tmp_path / "portale" / "uploads"
    assert Path(app.config["PORTALE_IMPORT_LOG_DB"]) == tmp_path / "portale" / "import_log.json"


def test_create_app_scheduler_only_costruisce_worker_senza_blueprint(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "SCHEDULER_ONLY": True})

    assert app.config["PCT_SCHEDULER_WORKER"] is True
    assert app.config["BACKUP_ORA"] == "03:30"
    assert app.config["WA_REMINDER_ORA"] == "17:15"
    assert app.blueprints == {}
    assert "PCT_SCHEDULER" not in app.config


def test_flask_app_factory_isola_bootstrap_base(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app, cfg = create_flask_app({**_cfg_web(tmp_path), "SCHEDULER_ONLY": True})

    assert cfg["SCHEDULER_ONLY"] is True
    assert app.config["PCT_SCHEDULER_WORKER"] is True
    assert app.config["TESTING"] is True
    assert app.static_folder is not None


def test_runtime_bundle_scheduler_only_costruisce_solo_core(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app, cfg = create_flask_app({**_cfg_web(tmp_path), "SCHEDULER_ONLY": True})
    runtime_bundle = build_application_runtime_bundle(app, cfg)

    assert runtime_bundle.scheduler_only is True
    assert runtime_bundle.ocr_runtime is None
    assert runtime_bundle.fascicoli == {}
    assert runtime_bundle.telematico == {}
    assert runtime_bundle.pdp_penale == {}
    assert runtime_bundle.core["get_agenda"] is not None


def test_runtime_bundle_cloud_gestito_rinvia_governance_pesante(monkeypatch, tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app, cfg = create_flask_app(_cfg_web(tmp_path))
    called = {"sync": 0, "pack": 0, "legacy": 0}

    class _FakeTenantManager:
        def __init__(self, registry_path):
            self.registry_path = registry_path

        def sync_user_directory(self, secret_key):
            called["sync"] += 1

    monkeypatch.setattr("web.bootstrap.runtime_bundle.is_managed_cloud_runtime", lambda: True)
    monkeypatch.setattr("web.bootstrap.runtime_bundle.GestioneTenant", _FakeTenantManager)
    monkeypatch.setattr(
        "web.bootstrap.runtime_bundle.bootstrap_pack_governance",
        lambda **kwargs: called.__setitem__("pack", called["pack"] + 1),
    )
    monkeypatch.setattr(
        "web.bootstrap.runtime_bundle.bootstrap_legacy_tenant_runtime_data",
        lambda app, tenant_slug=None: called.__setitem__("legacy", called["legacy"] + 1) or {},
    )

    runtime_bundle = build_application_runtime_bundle(app, cfg)

    assert runtime_bundle.scheduler_only is False
    assert called == {"sync": 0, "pack": 0, "legacy": 0}


def test_create_app_cloud_gestito_rinvia_bootstrap_moduli_ma_get_database_lo_esegue(
    monkeypatch,
    tmp_path: Path,
):
    _write_studio_config(tmp_path / "config" / "studio.json")
    calls: list[dict[str, str]] = []

    monkeypatch.setattr("web.services.core_runtime.is_managed_cloud_runtime", lambda: True)
    monkeypatch.setattr(
        "web.services.core_runtime.bootstrap_moduli_monitorati",
        lambda paths: calls.append(dict(paths)) or {},
    )

    app = create_app(_cfg_web(tmp_path))

    assert calls == []

    with app.app_context():
        app.extensions["core_runtime"]["get_database"]()

    assert len(calls) == 1


def test_root_repo_resta_pulita_e_spec_tecniche_stanno_fuori_dalla_root():
    root_test_files = sorted(path.name for path in REPO_ROOT.glob("test_*.py"))
    root_temp_logs = sorted(path.name for path in REPO_ROOT.glob("tmp_local_signer_*.log"))
    ministero_specs_dir = REPO_ROOT / "docs/specs/ministero"

    assert root_test_files == []
    assert root_temp_logs == []
    assert ministero_specs_dir.exists()
    assert (ministero_specs_dir / "Documentazione_servizi_web_v1.69.pdf").exists()
    assert (ministero_specs_dir / "A1_WSDL_CATALOG_v1.52").exists()


def test_auth_guard_keeps_login_public_and_redirects_protected_routes(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        login_page = client.get("/login")
        protected = client.get("/profilo")

    assert login_page.status_code == 200
    assert protected.status_code == 302
    assert protected.headers["Location"].endswith("/login?next=/profilo")


def test_api_pronto_restituisce_subito_stato_pronto(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        response = client.get("/api/pronto")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["stato"] == "pronto"
    assert payload["versione"] == APP_VERSION


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
    assert (
        app.jinja_env.filters["fmt_nota_import"]("Importato da PolisWeb il 2026-04-09")
        == "Importato da PolisWeb il 09/04/2026"
    )
    assert (
        app.jinja_env.filters["fmt_nota_import"](
            "Importato da SIGIT/PTT il 2026-04-09 — materia: tributario"
        )
        == "Importato da SIGIT/PTT il 09/04/2026 — materia: tributario"
    )
    assert globals_map["app_version"] == APP_VERSION
    assert globals_map["TipoAppuntamento"] is not None
    assert globals_map["recenti"] == []
    assert hasattr(globals_map["oggi"], "strftime")
    assert globals_map["mesi_italiani"][3] == "aprile"
    assert globals_map["giorni_settimana_brevi_italiani"][0] == "lun"


def test_pwa_routes_and_error_handlers_restano_registrati(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=False,
        )
        service_worker = client.get("/sw.js")
        offline = client.get("/offline")
        missing = client.get("/percorso-inesistente")

    assert service_worker.status_code == 200
    assert "javascript" in service_worker.content_type
    assert offline.status_code == 200
    assert missing.status_code == 404


def test_impostazioni_pec_espone_controllo_local_signer_e_password_salvata(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=False,
        )
        response = client.get("/impostazioni?tab=pec")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="iusentra-local-signer-monitor"' in html
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in html
    assert 'data-has-saved-password="1"' in html
    assert 'data-latest-version="' in html
    assert "/static/js/local-signer-monitor.js?v=" in html
    assert "Testa SMTP" in html
    assert "Diagnostica server (non invio reale)" in html
    assert "L'invio PEC reale deve passare dal PC locale tramite Local Signer" in html


def test_route_domini_estratti_restano_operativi(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    tenant_paths = (
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
        "/timesheet",
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
    )
    platform_paths = (
        "/admin/database",
        "/admin/governance",
        "/admin/assistente-migrazione",
        "/admin/crash-test-operativo",
        "/admin/siti-studio/",
        "/admin/copertura-ai",
        "/admin/copertura-ai/review",
        "/admin/aggiornamenti-legali",
        "/admin/aggiornamenti-legali/fonti",
        "/admin/aggiornamenti-legali/staging",
        "/admin/aggiornamenti-legali/analisi",
        "/admin/aggiornamenti-legali/archivio",
        "/admin/aggiornamenti-legali/review",
        "/admin/installazione-pack/",
        "/legal-intelligence/news",
    )

    with app.test_client() as tenant_client:
        login = tenant_client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=False,
        )
        assert login.status_code == 302

        for path in tenant_paths:
            response = tenant_client.get(path)
            assert response.status_code == 200, path

    with app.test_client() as platform_client:
        login = platform_client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code == 302

        for path in platform_paths:
            response = platform_client.get(path)
            assert response.status_code == 200, path


def test_nuovo_cliente_renderizza_il_form_prima_del_modal_scanner(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=False,
        )
        assert login.status_code == 302

        response = client.get("/clienti/nuovo?_legacy=1")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Dati studio" in html
    assert 'id="modalScanner"' in html
    assert html.index("Dati studio") < html.index('id="modalScanner"')


def test_web_app_dimagrisce_e_registra_i_moduli_estratti_finali():
    web_app = (REPO_ROOT / "web/app.py").read_text(encoding="utf-8")
    app_wiring = (REPO_ROOT / "web/bootstrap/app_wiring.py").read_text(encoding="utf-8")
    core_wiring = (REPO_ROOT / "web/bootstrap/core_surface_wiring.py").read_text(encoding="utf-8")
    fascicoli_wiring = (REPO_ROOT / "web/bootstrap/fascicoli_surface_wiring.py").read_text(encoding="utf-8")
    telematico_wiring = (REPO_ROOT / "web/bootstrap/telematico_surface_wiring.py").read_text(encoding="utf-8")

    assert "from web.bootstrap.app_wiring import register_app_wiring" in web_app
    assert "from web.bootstrap.flask_app_factory import create_flask_app" in web_app
    assert "from web.bootstrap.runtime_bundle import build_application_runtime_bundle" in web_app
    assert "from lex.providers.local_ai_service import get_local_ai_service" in web_app
    assert "from web.services.local_ai_runtime import get_local_ai_service" not in web_app
    assert "from web.services." not in web_app
    assert "from pct.scheduler import start_scheduler" not in web_app
    assert "register_app_wiring(" in web_app

    assert "from web.bootstrap.core_surface_wiring import register_core_surfaces" in app_wiring
    assert "from web.bootstrap.fascicoli_surface_wiring import register_fascicoli_surfaces" in app_wiring
    assert "from web.bootstrap.telematico_surface_wiring import register_telematico_surfaces" in app_wiring
    assert "register_core_surfaces(" in app_wiring
    assert "register_fascicoli_surfaces(" in app_wiring
    assert "register_telematico_surfaces(" in app_wiring

    for symbol in (
        "register_lex_operational_routes",
        "register_clienti_routes",
        "register_clienti_workspace_routes",
        "register_condivisioni_routes",
        "register_messages_routes",
        "register_backup_routes",
        "register_health_routes",
        "register_export_routes",
        "register_search_routes",
        "register_sync_runtime_routes",
        "register_scadenziario_routes",
        "register_dashboard_routes",
        "register_timesheet_routes",
    ):
        assert f"{symbol}(" in core_wiring

    for symbol in (
        "register_fascicoli_management_routes",
        "register_tariffario_routes",
        "register_fascicoli_document_routes",
        "register_fascicoli_editor_routes",
        "register_fascicoli_core_routes",
        "register_fascicoli_pdp_routes",
        "register_fascicoli_signature_routes",
        "register_reference_lookup_routes",
        "register_deposito_routes",
    ):
        assert f"{symbol}(" in fascicoli_wiring

    for symbol in (
        "register_polisweb_routes",
        "register_portali_acquisizione_routes",
        "register_telematico_dashboard_routes",
        "register_telematico_local_signer_routes",
        "register_telematico_portali_routes",
    ):
        assert f"{symbol}(" in telematico_wiring

    assert web_app.count("@app.route") == 0
    assert len(web_app.splitlines()) <= 250
    assert "from web.bootstrap.app_wiring import register_app_wiring" in web_app
    assert "create_flask_app(" in web_app
    assert "build_application_runtime_bundle(" in web_app
    assert "start_scheduler(" not in web_app
    assert "build_core_runtime(" not in web_app
    assert "build_fascicoli_runtime(" not in web_app
    assert "build_telematico_runtime(" not in web_app
    assert "build_pdp_penale_runtime(" not in web_app
    assert "build_ocr_runtime(" not in web_app
    assert "apply_security_defaults(" not in web_app


def _inline_style_totals() -> tuple[int, int, int]:
    style_tag = re.compile(r"<style\b", re.IGNORECASE)
    style_attr = re.compile(r"\sstyle=", re.IGNORECASE)
    files = 0
    tags = 0
    attrs = 0
    for path in (REPO_ROOT / "web/templates").rglob("*.html"):
        content = path.read_text(encoding="utf-8")
        file_tags = len(style_tag.findall(content))
        file_attrs = len(style_attr.findall(content))
        if file_tags or file_attrs:
            files += 1
            tags += file_tags
            attrs += file_attrs
    return files, tags, attrs


def test_i_moduli_bootstrap_restano_governabili():
    bootstrap_dir = REPO_ROOT / "web/bootstrap"
    default_limit = 650
    per_file_limits = {
        "deposito_routes.py": 1000,
        "scadenziario_routes.py": 700,
        "fascicoli_pdp_routes.py": 900,
        "core_surface_wiring.py": 250,
        "fascicoli_surface_wiring.py": 200,
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
        "web/templates/admin/base.html": ["Esci", "Piattaforma", "Aggiornamenti legali", "Pack installazione"],
        "web/templates/admin/installazione_pack.html": [
            "Product Pack, Studio Local Pack e Update Pack",
            "Rigenera bootstrap e manifest",
            "Bootstrap macchina",
            "Update Pack e repository SQL",
        ],
        "web/templates/admin/assistente_migrazione.html": [
            "Assistente migrazione dati",
            "Ultima esecuzione reale",
            "Come risolvere",
            "Snapshot pre-migrazione",
            "Log operativo della migrazione",
        ],
        "web/templates/admin/osservabilita.html": [
            "Osservabilita runtime",
            "Segnali di degrado",
            "Come intervenire",
        ],
        "web/templates/admin/legal_coverage_dashboard.html": [
            "Copertura AI e autopubblicazione controllata",
            "Studio per la coverage",
            "Database coverage",
        ],
        "web/templates/admin/legal_coverage_review.html": [
            "Coda revisione draft v2",
            "Come si usa questa schermata",
            "Contesto di retrieval",
            "Decisione reviewer",
            "Storico revisioni",
        ],
        "web/templates/admin/legal_updates_dashboard.html": [
            "Motore di aggiornamento normativo e giurisprudenziale",
            "Fonti monitorate",
            "Review pendenti",
        ],
        "web/templates/admin/legal_updates_review.html": [
            "Coda revisioni aggiornamenti",
            "Azione proposta",
            "Pubblica",
        ],
        "web/templates/dashboard.html": ["Panoramica dello studio"],
        "web/templates/agenda.html": ["Sincronizzazione automatica", "Configura sincronizzazione calendario"],
        "web/templates/impostazioni/index.html": ["Servizio locale sul dispositivo cliente", "Prepara il motore locale"],
        "web/templates/notifiche/pannello.html": ["Invia messaggio", "Registro notifiche"],
        "web/templates/wizard_pro/index.html": [
            "Preparazione Udienza Guidata",
            "Seleziona il fascicolo da cui avviare la preparazione dell'udienza",
        ],
        "web/templates/workspace_intelligente.html": ["Lex Operativo", "Ultima sincronizzazione"],
        "web/templates/lex_operational.html": ["Lex Fascicolo", "Regia telematica"],
        "web/templates/legal_intelligence/news.html": ["News giuridiche strutturate", "Fonte ufficiale"],
        "web/templates/portale/base.html": ["Operazione completata", "Inizio"],
        "web/templates/telematico_dashboard.html": ["Centro Servizi Telematici", "Ultimo allineamento"],
        "web/templates/timesheet/lista.html": ["Timesheet operativo", "Cosa fare adesso"],
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
        "web/templates/clienti/dettaglio.html",
        "web/templates/faldone.html",
        "web/templates/editor_documento.html",
        "web/templates/fascicoli/dettaglio.html",
        "web/templates/successo.html",
        "web/templates/clienti/copertina_faldone.html",
        "web/templates/fascicoli/copertina.html",
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
    copertina_content = (REPO_ROOT / "web/templates/fascicoli/copertina.html").read_text(encoding="utf-8")
    assert 'url_for(\'dettaglio_fascicolo\', id_fasc=fascicolo.id)' in copertina_content
    assert "javascript:history.back()" not in copertina_content


def test_lex_frontend_allinea_smalltalk_e_guardie_legali():
    js_content = (REPO_ROOT / "web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")

    assert "function looksLikeSmallTalk(text)" in js_content
    assert "legalReferenceGuardActive" in js_content
    assert "Non ho ancora una pronuncia verificata da citare con numero e PDF." in js_content
    assert "countIntentWords(clean) <= 4 && !matchFocusRule(clean)" not in js_content


def test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ollama:" in compose
    assert "scheduler-worker:" in compose
    assert "ocr-worker:" in compose
    assert 'command: ["python", "-m", "pct.scheduler_worker"]' in compose
    assert 'command: ["python", "-m", "pct.ocr_worker"]' in compose
    assert 'profiles: ["ollama-sidecar"]' in compose
    assert "image: ollama/ollama:latest" in compose
    assert "PCT_LOCAL_AI_BASE_URL: ${PCT_LOCAL_AI_BASE_URL:-http://host.docker.internal:11434/api}" in compose
    assert "PCT_OCR_QUEUE_DB: /data/search/ocr_jobs.db" in compose
    assert 'PCT_STORAGE_MODE: "SQLITE"' in compose
    assert 'PCT_SQLITE_MODE: "1"' in compose
    assert 'host.docker.internal:host-gateway' in compose


def test_bootstrap_pubblico_resta_allineato_a_password_temporanee_e_ci_reale():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    ci_workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    sync_workflow = (REPO_ROOT / ".github/workflows/sync-claude-to-codex.yml").read_text(encoding="utf-8")
    perf_workflow = (REPO_ROOT / ".github/workflows/performance-nightly.yml").read_text(encoding="utf-8")
    codeql_workflow = (REPO_ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
    dependency_review = (REPO_ROOT / ".github/workflows/dependency-review.yml").read_text(encoding="utf-8")
    security_workflow = (REPO_ROOT / ".github/workflows/security-supply-chain.yml").read_text(encoding="utf-8")
    repo_hygiene = (REPO_ROOT / "scripts/repo_hygiene.ps1").read_text(encoding="utf-8")
    autosync_script = (REPO_ROOT / "scripts/git_branch_autosync.ps1").read_text(encoding="utf-8")
    hook_runner = (REPO_ROOT / ".githooks/_run_powershell_hook.sh").read_text(encoding="utf-8")
    post_commit = (REPO_ROOT / ".githooks/post-commit").read_text(encoding="utf-8")
    post_checkout = (REPO_ROOT / ".githooks/post-checkout").read_text(encoding="utf-8")
    post_merge = (REPO_ROOT / ".githooks/post-merge").read_text(encoding="utf-8")
    post_rewrite = (REPO_ROOT / ".githooks/post-rewrite").read_text(encoding="utf-8")

    assert "admin / admin" not in compose
    assert "admin / admin" not in readme
    assert "bootstrap_admin.json" in compose
    assert "bootstrap_admin.json" in readme
    assert "PCT_BOOTSTRAP_ADMIN_PASSWORD" in env_example
    assert "PCT_SECRET_KEY=" in env_example
    assert "INSERISCI_UNA_CHIAVE_CASUALE" not in env_example
    assert "workflow principale applicativo è `.github/workflows/ci.yml`" in readme
    assert "github.com/antmm2605/IUSENTRA/actions/workflows/ci.yml" in readme
    assert ".github/workflows/sync-claude-to-codex.yml" in readme
    assert ".githooks/" in readme
    assert "name: CI" in ci_workflow
    assert "name: Governance repo" in ci_workflow
    assert "python tools/check_repo_governance.py" in ci_workflow
    assert "\n  push:\n" in ci_workflow
    assert '      - "Codex/legal-electronic-filing-kIxcV"' not in ci_workflow
    assert '      - "claude/legal-electronic-filing-kIxcV"' not in ci_workflow
    assert "name: Smoke scheduler worker" in ci_workflow
    assert "tests/test_storage_strategy.py" in ci_workflow
    assert "tests/test_observability_runtime.py" in ci_workflow
    assert "tests/test_ocr_worker.py" in ci_workflow
    assert "name: Sync Twin Branches" in sync_workflow
    assert '      - "Codex/legal-electronic-filing-kIxcV"' in sync_workflow
    assert '      - "claude/legal-electronic-filing-kIxcV"' in sync_workflow
    assert 'target="claude/legal-electronic-filing-kIxcV"' in sync_workflow
    assert 'target="Codex/legal-electronic-filing-kIxcV"' in sync_workflow
    assert 'git push origin "HEAD:refs/heads/${{ steps.branches.outputs.target }}" --force' in sync_workflow
    assert "core.hooksPath .githooks" in repo_hygiene
    assert "safe.directory" in repo_hygiene
    assert "git_branch_autosync.ps1" in hook_runner
    assert "branch -f $branch $currentHead" in autosync_script
    assert 'sh "$script_dir/_run_powershell_hook.sh" post-commit "$@"' in post_commit
    assert 'sh "$script_dir/_run_powershell_hook.sh" post-checkout "$@"' in post_checkout
    assert 'sh "$script_dir/_run_powershell_hook.sh" post-merge "$@"' in post_merge
    assert 'sh "$script_dir/_run_powershell_hook.sh" post-rewrite "$@"' in post_rewrite
    assert "name: Performance Nightly" in perf_workflow
    assert "tools/performance_smoke.py --strict" in perf_workflow
    assert "name: CodeQL" in codeql_workflow
    assert "github/codeql-action/analyze" in codeql_workflow
    assert "name: Dependency Review" in dependency_review
    assert "dependency-review-action" in dependency_review
    assert "name: Security Supply Chain" in security_workflow
    assert "pip-audit" in security_workflow
    assert "sbom" in security_workflow


def test_scheduler_worker_entrypoint_resta_separato_dal_runtime_web():
    scheduler_worker = (REPO_ROOT / "pct/scheduler_worker.py").read_text(encoding="utf-8")

    assert "def create_scheduler_app(" in scheduler_worker
    assert "def start_scheduler_worker(" in scheduler_worker
    assert 'cfg["SCHEDULER_ONLY"] = True' in scheduler_worker
    assert "from web.app import create_app" in scheduler_worker


def test_governance_lex_possiede_runtime_ai_locale_e_i_facade_web_restano_sottili():
    app_text = (REPO_ROOT / "web/app.py").read_text(encoding="utf-8")
    local_ai_facade = (REPO_ROOT / "web/services/local_ai_runtime.py").read_text(encoding="utf-8")
    ollama_facade = (REPO_ROOT / "web/services/ollama_runtime.py").read_text(encoding="utf-8")
    legacy_assistente = (REPO_ROOT / "web/assistente.py").read_text(encoding="utf-8")
    lex_local_ai = (REPO_ROOT / "lex/providers/local_ai_service.py").read_text(encoding="utf-8")
    lex_ollama_runtime = (REPO_ROOT / "lex/providers/ollama_runtime.py").read_text(encoding="utf-8")

    assert "from lex.providers.local_ai_service import get_local_ai_service" in app_text
    assert "from web.services.local_ai_runtime import get_local_ai_service" not in app_text
    assert "from lex.providers.local_ai_service import get_local_ai_service" in local_ai_facade
    assert "from lex.providers.ollama_runtime import (" in ollama_facade
    assert "from web.blueprints.admin import admin_bp, superadmin_required" in legacy_assistente
    assert "def get_local_ai_service() -> LocalAIService:" in lex_local_ai
    assert "def resolved_ollama_runtime(" in lex_ollama_runtime
    assert len(local_ai_facade.splitlines()) <= 40
    assert len(ollama_facade.splitlines()) <= 40
    assert len(legacy_assistente.splitlines()) <= 40


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
    assert "@use 'components/app-shell';" in app_scss
    assert "@use 'components/feedback';" in app_scss
    assert "@use 'components/compact-panels';" in app_scss
    assert "@use 'components/local-ai-assistant';" in app_scss
    assert "@use 'components/pct-lex-assistant';" in app_scss
    assert "@use 'pages/admin';" in app_scss
    assert "@use 'pages/dashboard';" in app_scss
    assert "@use 'pages/hearing-preparation';" in app_scss
    assert "@use 'pages/notifiche-whatsapp';" in app_scss
    assert "@use 'pages/settings';" in app_scss
    assert "@use 'pages/telematico-dashboard';" in app_scss
    assert "@use 'pages/workspace-intelligente';" in app_scss
    portal_scss = (REPO_ROOT / "web/static/scss/portal.scss").read_text(encoding="utf-8")
    assert "@use 'components/portale-shell';" in portal_scss
    assert "@use 'pages/portale-home';" in portal_scss

    app_shell_scss = (REPO_ROOT / "web/static/scss/components/_app-shell.scss").read_text(encoding="utf-8")
    admin_scss = (REPO_ROOT / "web/static/scss/pages/_admin.scss").read_text(encoding="utf-8")
    assert ".topbar-counter-badge" in app_shell_scss
    assert ".notifiche-panel" in app_shell_scss
    assert ".notif-item--unread" in app_shell_scss
    assert ".admin-page-header" in admin_scss
    assert ".admin-db-mode-card" in admin_scss
    assert "@media (max-width: 767.98px)" in admin_scss
    assert "@media (max-width: 575.98px)" in admin_scss

    for relative_path in (
        "web/templates/base.html",
        "web/templates/admin/base.html",
        "web/templates/admin/dashboard.html",
        "web/templates/admin/installazione_pack.html",
        "web/templates/admin/studio_nuovo.html",
        "web/templates/dashboard.html",
        "web/templates/impostazioni/index.html",
        "web/templates/notifiche/pannello.html",
        "web/templates/workspace_intelligente.html",
        "web/templates/portale/base.html",
        "web/templates/portale/home.html",
        "web/templates/telematico_dashboard.html",
    ):
        content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "<style" not in content

    base_template = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")
    admin_base = (REPO_ROOT / "web/templates/admin/base.html").read_text(encoding="utf-8")
    admin_dashboard = (REPO_ROOT / "web/templates/admin/dashboard.html").read_text(encoding="utf-8")
    admin_studio_nuovo = (REPO_ROOT / "web/templates/admin/studio_nuovo.html").read_text(encoding="utf-8")

    assert "style=" not in base_template
    assert "topbar-counter-badge" in base_template
    assert "notifiche-panel is-hidden" in base_template
    assert "notif-item__body" in base_template
    assert "ss-chip-identificativo" in base_template
    assert ("logo-iusentra.png" in base_template) or ("sb-brand-wordmark" in base_template)
    assert "logo-iusentra.png" in admin_base

    for css_link in (
        "/static/css/app.css?v={{ app_version }}",
        "/static/css/design-system.css?v={{ app_version }}",
        "/static/css/mobile.css?v={{ app_version }}",
        "/static/css/theme.css?v={{ app_version }}",
    ):
        assert css_link in admin_base
    assert "style=" not in admin_base
    assert "style=" not in admin_dashboard
    assert "style=" not in admin_studio_nuovo

    portale_base = (REPO_ROOT / "web/templates/portale/base.html").read_text(encoding="utf-8")
    assert "/static/css/portal.css?v={{ app_version }}" in portale_base


def test_template_html_restano_entra_il_budget_inline_style():
    files, tags, attrs = _inline_style_totals()

    assert files <= 165
    assert tags <= 53
    assert attrs <= 1464


def test_brand_asset_iusentra_restano_coerenti():
    manifest = json.loads((REPO_ROOT / "web/static/manifest.json").read_text(encoding="utf-8"))
    static_icon = (REPO_ROOT / "web/static/icons/icon.svg").read_text(encoding="utf-8")
    legacy_icon = (REPO_ROOT / "web/icon.svg").read_text(encoding="utf-8")

    assert manifest["name"] == "IUSENTRA"
    assert manifest["short_name"] == "IUSENTRA"
    assert manifest["icons"][0]["src"] == "/static/icons/icon.svg"
    assert "IUSENTRA" in static_icon
    assert "IUSENTRA" in legacy_icon


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
    assert "servizio locale" in ai_js.lower()
    assert "fetch(config.localSignerUrl + '/ai/status?' + params.toString(), {\n      method: 'GET',\n    });" in ai_js
    assert "fetch(config.localSignerUrl + '/ai/bootstrap', {\n          method: 'POST'," in ai_js
    assert 'data-local-signer-url="http://127.0.0.1:27272"' in template
    assert "data-local-signer-setup-windows" in template
    assert "Quando IUSENTRA e' online" in template


def test_local_signer_monitor_globale_verifica_versione_e_installer():
    base = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")
    monitor_js = (REPO_ROOT / "web/static/js/local-signer-monitor.js").read_text(encoding="utf-8")

    assert 'id="iusentra-local-signer-monitor"' in base
    assert 'data-local-signer-url="{{ local_signer_release.browser_url }}"' in base
    assert 'data-latest-version="{{ local_signer_release.version }}"' in base
    assert "/static/js/local-signer-monitor.js?v={{ app_version }}" in base

    assert "http://127.0.0.1:27272" in monitor_js
    assert "hacs-local-signer://restart" in monitor_js
    assert "compareVersions" in monitor_js
    assert "Fase 1: provo ad avviare" in monitor_js
    assert "Fase 2: versione rilevata" in monitor_js
    assert "Fase 3: installa il pacchetto" in monitor_js
    assert "Fase 4 completata" in monitor_js
    assert "autoOpenInstallerOnce" in monitor_js


def test_local_signer_distribution_include_bridge_ai(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        bridge = client.get("/polisWeb/local-signer/download/local-ai-bridge")
        lex_context = client.get("/polisWeb/local-signer/download/lex-document-context")
        visible_signature = client.get("/polisWeb/local-signer/download/visible-signature")
        ai_handlers = client.get("/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py")

    assert bridge.status_code == 200
    bridge_source = bridge.get_data(as_text=True)
    assert "class LocalAiHostBridge" in bridge_source
    assert "class OllamaLocalClient" in bridge_source

    assert lex_context.status_code == 200
    assert "build_attachment_prompt_block" in lex_context.get_data(as_text=True)
    assert visible_signature.status_code == 200
    assert "apply_visible_signature_stamp" in visible_signature.get_data(as_text=True)
    assert ai_handlers.status_code == 200
    assert "class LocalAiHandlerFacade" in ai_handlers.get_data(as_text=True)

    build_dist = (REPO_ROOT / "tools/build_dist.py").read_text(encoding="utf-8")
    build_windows = (REPO_ROOT / "tools/build_local_signer_windows_exe.ps1").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "tools/installa_local_signer_locale.ps1").read_text(encoding="utf-8")
    signer_routes = (REPO_ROOT / "web/bootstrap/telematico_local_signer_routes.py").read_text(encoding="utf-8")

    assert "local_ai_host_bridge.py" in build_dist
    assert "lex_document_context.py" in build_dist
    assert "local_signer_mod" in build_dist
    assert "local_ai_host_bridge.py" in build_windows
    assert "lex_document_context.py" in build_windows
    assert "visible_signature.py" in build_windows
    assert "local_signer_mod__ai_handlers.py" in build_windows
    assert "local_ai_host_bridge.py" in installer
    assert "lex_document_context.py" in installer
    assert "visible_signature.py" in installer
    assert "Copy-LocalSignerModule" in installer
    assert "/polisWeb/local-signer/download/local-ai-bridge" in signer_routes
    assert "/polisWeb/local-signer/download/lex-document-context" in signer_routes
    assert "/polisWeb/local-signer/download/visible-signature" in signer_routes
    assert "/polisWeb/local-signer/download/local-signer-mod/<path:filename>" in signer_routes


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


def test_email_e_sync_fascicolo_usano_date_italiane_e_target_corrente():
    email_template = (REPO_ROOT / "web/templates/email/client.html").read_text(encoding="utf-8")
    email_detail = (REPO_ROOT / "web/templates/email/_dettaglio_panel.html").read_text(encoding="utf-8")
    fascicolo_template = (REPO_ROOT / "web/templates/fascicoli/dettaglio.html").read_text(encoding="utf-8")

    assert "|fmt_ora" in email_template
    assert "|fmt_data" in email_template
    assert "ts[5:7]" not in email_template
    assert "ts[8:10]" not in email_template
    assert "|fmt_dataora" in email_detail
    assert "JSON.stringify({ id_fascicolo: '{{ fascicolo.id }}' })" in fascicolo_template
    assert "nextUrl.hash = 'sezione-comunicazioni-cancelleria';" in fascicolo_template
    assert "window.location.assign(nextUrl.toString())" in fascicolo_template


def test_ai_operativa_usa_bridge_browser_e_template_senza_logica_inline():
    fascicolo_template = (REPO_ROOT / "web/templates/fascicoli/dettaglio.html").read_text(encoding="utf-8")
    fascicolo_cockpit = (REPO_ROOT / "web/templates/components/fascicolo_cockpit_tabs.html").read_text(encoding="utf-8")
    fascicolo_component = (REPO_ROOT / "web/templates/components/fascicolo_smart_board.html").read_text(encoding="utf-8")
    workspace_template = (REPO_ROOT / "web/templates/workspace_intelligente.html").read_text(encoding="utf-8")
    bridge_js = (REPO_ROOT / "web/static/js/local-ai-browser-bridge.js").read_text(encoding="utf-8")
    fascicolo_js = (REPO_ROOT / "web/static/js/fascicolo-ai.js").read_text(encoding="utf-8")
    workspace_js = (REPO_ROOT / "web/static/js/workspace-ai.js").read_text(encoding="utf-8")

    assert '{% include "components/fascicolo_cockpit_tabs.html" %}' in fascicolo_template
    assert '{% include "components/fascicolo_smart_board.html" %}' in fascicolo_cockpit
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
    assert 'id="pct-ai-presets"' in widget_template
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
    assert "renderPresetPills" in widget_js
    assert "runPreset" in widget_js
    assert "SURFACE_PRESETS" in widget_js
    assert "Lex Fascicolo" in widget_js
    assert "Lex Udienza" in widget_js
    assert "Lex Telematico" in widget_js
    assert "Lex Operativo" in widget_js
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
    assert "renderConfidence" in widget_js
    assert "Affidabilita" in widget_js
    assert "appendMetaMessage" not in widget_js
    assert "assistantAvatarMarkup" in widget_js
    assert "dataset.lexIconUrl" in widget_js
    assert "resetPosition" in widget_js
    assert "startResize" in widget_js
    assert ".pct-ai-callout--confidence" in widget_scss
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
    assert "Servizio locale del dispositivo raggiunto, ma la richiesta non e\\' andata a buon fine" in widget_js
    assert "Local Signer raggiungibile, ma il motore locale non e\\' operativo su questo dispositivo." in widget_js
    assert "remoteHosted" in widget_js
    assert "Lex sta scrivendo dal dispositivo locale" not in widget_js
    assert "Risposta generata sul dispositivo locale." in widget_js
    assert "Servizio locale del dispositivo non raggiungibile, attivo il percorso alternativo sul motore locale di IUSENTRA..." in widget_js
    assert "sendLocal(text);" in widget_js
    assert "var preparedLegalReferenceGuardActive = false;" in widget_js
    assert "preparedLegalReferenceGuardActive = Boolean(prepared && prepared.legal_reference_guard_active);" in widget_js
    assert "legalReferenceGuardActive: Boolean(payload.legalReferenceGuardActive || preparedLegalReferenceGuardActive)" in widget_js
    assert "legalReferenceGuardActive: Boolean(payload.legalReferenceGuardActive || (prepared && prepared.legal_reference_guard_active))" not in widget_js
    assert "payload.answer = prependSocialPrefix(preparedSocialPrefix, payload.answer || '')" not in widget_js
    assert "partial = prependSocialPrefix(preparedSocialPrefix, partial);" not in widget_js
    assert "pct-ai-thinking-copy" in widget_scss
    assert "pct-ai-status-pill--inline" in widget_scss
    assert "pct-ai-widget--fullscreen" in widget_scss
    assert ".pct-ai-widget--fullscreen.pct-ai-widget--open .pct-ai-fab" in widget_scss
    assert ".pct-ai-presets" in widget_scss
    assert ".pct-ai-preset-pill" in widget_scss
    assert ".pct-ai-callout" in widget_scss
    assert ".pct-ai-action-pill" in widget_scss

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

    init_block = widget_js.split("function init()", 1)[1].split("window.pctAI", 1)[0]
    assert "primeAssistantContext();" not in init_block
    assert "checkStatus();" not in init_block
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
    followup_service = (REPO_ROOT / "lex/memory/followup.py").read_text(encoding="utf-8")
    followup_wrapper = (REPO_ROOT / "web/services/assistente_followup.py").read_text(encoding="utf-8")
    social_service = (REPO_ROOT / "web/services/assistente_social.py").read_text(encoding="utf-8")
    social_intent_service = (REPO_ROOT / "lex/memory/social_intent.py").read_text(encoding="utf-8")
    social_intent_wrapper = (REPO_ROOT / "web/services/assistente_social_intent.py").read_text(encoding="utf-8")
    today_summary_service = (REPO_ROOT / "lex/context/today_summary.py").read_text(encoding="utf-8")
    today_summary_wrapper = (REPO_ROOT / "web/services/assistente_today_summary.py").read_text(encoding="utf-8")
    language_guidance_service = (REPO_ROOT / "lex/prompts/language_guidance.py").read_text(encoding="utf-8")
    language_guidance_wrapper = (REPO_ROOT / "web/services/assistente_language_guidance.py").read_text(encoding="utf-8")
    competence_service = (REPO_ROOT / "web/services/assistente_competencies.py").read_text(encoding="utf-8")
    web_execution_service = (REPO_ROOT / "web/services/assistente_web_execution.py").read_text(encoding="utf-8")
    assistente_blueprint = (REPO_ROOT / "web/blueprints/assistente.py").read_text(encoding="utf-8")
    lex_blueprint = (REPO_ROOT / "lex/blueprint.py").read_text(encoding="utf-8")
    lex_routes = (REPO_ROOT / "lex/routes.py").read_text(encoding="utf-8")
    lex_service = (REPO_ROOT / "lex/service.py").read_text(encoding="utf-8")
    lex_orchestrator = (REPO_ROOT / "lex/orchestrator.py").read_text(encoding="utf-8")
    lex_orchestrator_http = (REPO_ROOT / "lex/orchestrator_http.py").read_text(encoding="utf-8")
    assistente_prompt = (REPO_ROOT / "lex/prompts/prompt_builder.py").read_text(encoding="utf-8")
    prompt_wrapper = (REPO_ROOT / "web/services/assistente_prompt.py").read_text(encoding="utf-8")

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
    assert "_legal_dashboard_headline" in context_service
    assert 'chat_mode = str(mode or "").strip().lower() == "chat"' in context_service
    assert "selected_detail_titles = (" in context_service
    assert "force_web_fallback = web_execution_requested or _should_force_web_fallback(" in context_service
    assert '"sources": deduped_sources[:10 if chat_mode else 12]' in context_service
    assert 'research_strategy = _clean_spaces(focus.get("research_strategy"))' in context_service
    assert 'Ricerca ampia su sentenze civili: Lex deve partire dalle pronunce civili piu\' recenti' in context_service
    assert '"web_fallback_used": bool(force_web_fallback)' in context_service
    assert '"legal_dashboard_headline": legal_dashboard_headline' in context_service
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
    assert "from lex.memory.social_intent import is_small_talk_message" in focus_service
    assert "_FALLBACK_DEFAULT_SOURCE_IDS" in live_web_service
    assert "force: bool = False" in live_web_service
    assert "explicit_source_ids" in live_web_service
    assert "resolve_effective_query as resolve_web_effective_query" in followup_service
    assert "is_web_execution_request as is_web_execution_command" in followup_service
    assert "from lex.memory.followup import (" in followup_wrapper
    assert "classify_social_message" in social_service
    assert "build_social_reply" in social_service
    assert "prepend_social_prefix" in social_service
    assert "is_social_only_intent" in social_service
    assert "class SocialRoutingResult" in social_intent_service
    assert "resolve_social_and_operational_intent" in social_intent_service
    assert "build_daily_overview_lead" in social_intent_service
    assert "build_social_only_reply" in social_intent_service
    assert "from lex.memory.social_intent import (" in social_intent_wrapper
    assert "build_today_operational_summary" in today_summary_service
    assert "_TODAY_SECTION_FACTORIES" in today_summary_service
    assert "from lex.context.today_summary import build_today_operational_summary" in today_summary_wrapper
    assert "class LanguageGuidance" in language_guidance_service
    assert "def build_language_guidance" in language_guidance_service
    assert "Controllo io sul web. Parto dalle sentenze civili piu' recenti e rilevanti" in language_guidance_service
    assert "from lex.prompts.language_guidance import LanguageGuidance, build_language_guidance" in language_guidance_wrapper
    assert "class LexCompetenceProfile" in competence_service
    assert "def build_competence_catalog_prompt" in competence_service
    assert "Centro Servizi Telematici" in competence_service
    assert "Tariffario, preventivi, fatturazione e pagamenti" in competence_service
    assert "from lex.memory.web_execution import (" in web_execution_service
    assert "WebExecutionIntent" in web_execution_service
    assert "is_web_execution_request" in web_execution_service
    assert "resolve_effective_query" in web_execution_service
    assert "resolve_web_execution_intent" in web_execution_service
    assert "create_lex_blueprint" in assistente_blueprint
    assert "_build_lex_dependencies" in assistente_blueprint
    assert "from lex.runtime_dependencies import (" in assistente_blueprint
    assert "build_runtime_lex_dependencies" in assistente_blueprint
    assert "require_authenticated_flask_user" in assistente_blueprint
    assert 'assistente = create_lex_blueprint(' in assistente_blueprint
    runtime_dependencies = (REPO_ROOT / "lex/runtime_dependencies.py").read_text(encoding="utf-8")
    assert "def build_runtime_lex_dependencies() -> LexDependencies:" in runtime_dependencies
    assert "def require_authenticated_flask_user(fn):" in runtime_dependencies
    assert "from .context.studio_context import build_lex_studio_context, warm_lex_studio_context" in runtime_dependencies
    assert "from .providers.health import resolved_runtime, warm_runtime" in runtime_dependencies
    assert "from web.services.assistente_studio_context import (" not in runtime_dependencies
    assert "from web.services.ollama_runtime import (" not in runtime_dependencies
    assert "from .memory.followup import resolve_followup_query" in runtime_dependencies
    assert "from .memory.social_intent import (" in runtime_dependencies
    assert "from .prompts.language_guidance import build_language_guidance" in runtime_dependencies
    assert "from .prompts.prompt_builder import build_assistente_prompt" in runtime_dependencies
    assert "register_routes(bp, service=service, login_required=login_required)" in lex_blueprint
    assert 'Blueprint("assistente", __name__)' in lex_blueprint
    assert 'bp.add_url_rule("/api/assistente/warmup"' in lex_routes
    assert "def assistente_chat()" in lex_routes
    assert "LexOrchestrator" in lex_service
    assert "build_context_response" in lex_orchestrator
    assert "chat_response" in lex_orchestrator
    assert "messages_with_effective_question" in lex_orchestrator
    assert "social_context_payload" in lex_orchestrator_http
    assert "direct_answer_payload" in lex_orchestrator_http
    assert '"query_type": "assistente_chat"' in lex_orchestrator_http
    assert '"daily_overview_lead": opening_line' in lex_orchestrator_http
    assert '"language_mode": str(language_guidance.mode or "").strip()' in lex_orchestrator_http
    assert '"competence_labels": list(studio_context.get("competence_labels") or [])' in lex_orchestrator_http
    assert '"social_prefix": str(social_prefix or "").strip()' in lex_orchestrator_http
    assert '"focus_label": str(studio_context.get("focus_label") or "").strip()' in lex_orchestrator_http
    assert "web_fallback_used = bool(studio_context.get(\"web_fallback_used\")) or bool(" in lex_orchestrator_http
    assert "web_execution_requested = bool(studio_context.get(\"web_execution_requested\")) or bool(followup.is_web_request)" in lex_orchestrator_http
    assert '"web_fallback_used": web_fallback_used' in lex_orchestrator_http
    assert '"web_execution_requested": web_execution_requested' in lex_orchestrator_http
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
    assert "from lex.prompts.prompt_builder import build_assistente_prompt, latest_user_message" in prompt_wrapper


def test_preparazione_udienza_guidata_usa_componenti_modulari_e_js_esterno():
    base_template = (REPO_ROOT / "web/templates/base.html").read_text(encoding="utf-8")
    admin_base_template = (REPO_ROOT / "web/templates/admin/base.html").read_text(encoding="utf-8")
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
    assert "Sito Studio" in base_template
    assert "Siti studio" in admin_base_template

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
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=True,
        )
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
    assert "spazio limitato IUSENTRA ha sostituito la copia precedente" in dettaglio
    assert "sincronizzazione in tempo reale" in deposito
    assert "spazio limitato IUSENTRA ha sostituito la copia precedente" in deposito
    assert '{% from "components/firma_visibile_selector.html" import render_firma_visibile_selector %}' in dettaglio
    assert '{% from "components/firma_visibile_selector.html" import render_firma_visibile_selector %}' in deposito
    assert "{{ render_firma_visibile_selector('dettaglioFirma', firma_visibile_place, firma_visibile_mode|default('laterale')) }}" in dettaglio
    assert "{{ render_firma_visibile_selector('depositoFirma', firma_visibile_place, firma_visibile_mode|default('laterale')) }}" in deposito
    assert "/static/js/firma-visibile-mode.js?v={{ app_version }}" in dettaglio
    assert "/static/js/firma-visibile-mode.js?v={{ app_version }}" in deposito
    assert "Laterale verticale" in selector
    assert "In basso a sinistra" in selector
    assert "In basso a destra" in selector
    assert 'data-signature-place="{{ place }}"' in selector
    assert 'data-signature-default-mode="{{ mode }}"' in selector
    assert "window.HacsFirmaVisibileMode" in helper_js
    assert "getSelectedMode" in helper_js
    assert "getSignaturePlace" in helper_js


def test_cockpit_fascicolo_unifica_quadro_workflow_e_controlli_operativi():
    dettaglio = (REPO_ROOT / "web/templates/fascicoli/dettaglio.html").read_text(encoding="utf-8")
    cockpit = (REPO_ROOT / "web/templates/components/fascicolo_cockpit_tabs.html").read_text(encoding="utf-8")
    smart_board = (REPO_ROOT / "web/templates/components/fascicolo_smart_board.html").read_text(encoding="utf-8")
    app_scss = (REPO_ROOT / "web/static/scss/app.scss").read_text(encoding="utf-8")
    cockpit_scss = (REPO_ROOT / "web/static/scss/pages/_fascicolo-cockpit.scss").read_text(encoding="utf-8")
    smart_board_scss = (REPO_ROOT / "web/static/scss/pages/_fascicolo-smart-board.scss").read_text(encoding="utf-8")

    assert '{% include "components/fascicolo_cockpit_tabs.html" %}' in dettaglio
    assert "Cabina fascicolo" in cockpit
    assert "Quadro intelligente" in cockpit
    assert "Workflow -> incasso" in cockpit
    assert "Controllo economico" in cockpit
    assert "Governo documentale" in cockpit
    assert "Deposito e conformita'" in cockpit
    assert 'class="btn btn-sm btn-outline-primary fascicolo-cockpit__switch"' in cockpit
    assert '{% include "components/fascicolo_smart_board.html" %}' in cockpit
    assert "_activateFascicoloCockpitTab" in dettaglio
    assert "bootstrap.Tab.getOrCreateInstance" in dettaglio
    assert 'data-bs-target="#collapse-sezione-intelligenza-fascicolo"' in smart_board
    assert 'id="collapse-sezione-intelligenza-fascicolo"' in smart_board
    assert "Cambia stato" in smart_board
    assert "Azioni" in smart_board
    assert "Avanzamento pratica" in smart_board
    assert "Cliente" in smart_board
    assert "Parti del procedimento" in smart_board
    assert "Collegamenti rapidi" in smart_board
    assert "@use 'pages/fascicolo-cockpit';" in app_scss
    assert "@use 'pages/fascicolo-smart-board';" in app_scss
    assert "@use 'pages/lex-operational';" in app_scss
    assert ".fascicolo-cockpit__nav" in cockpit_scss
    assert ".fascicolo-cockpit__grid" in cockpit_scss
    assert ".fascicolo-cockpit__deposit-grid" in cockpit_scss
    assert ".fascicolo-smart-board__quick-link" in smart_board_scss
    assert ".fascicolo-smart-board__hero" in smart_board_scss


def test_assistente_stato_usa_runtime_ollama_risolto(monkeypatch, tmp_path: Path):
    from web.app import create_app

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    class FakeResponse:
        def json(self):
            return {"models": [{"name": "gemma3:1b"}]}

    called = {}

    def fake_get(url, timeout):
        called["url"] = url
        called["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "lex.runtime_dependencies.resolved_ollama_runtime",
        lambda: {
            "api_base_url": "http://host.docker.internal:11434/api",
            "base_url": "http://host.docker.internal:11434",
            "chat_model": "gemma3:1b",
            "keep_alive": "10m",
        },
    )
    monkeypatch.setattr("lex.runtime_dependencies.requests.get", fake_get)

    with app.test_client() as client:
        client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=True,
        )
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
    studio, tenant_admin = _seed_tenant_admin(app)

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
        "lex.runtime_dependencies.resolved_ollama_runtime",
        lambda: {
            "api_base_url": "http://host.docker.internal:11434/api",
            "base_url": "http://host.docker.internal:11434",
            "chat_model": "gemma3:1b",
            "keep_alive": "12m",
        },
    )
    monkeypatch.setattr("lex.runtime_dependencies.requests.post", fake_post)

    with app.test_client() as client:
        client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=True,
        )
        response = client.post(
            "/api/assistente/chat",
            json={"messages": [{"role": "user", "content": "Preparami una bozza di memoria per la pratica"}]},
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


def test_audit_log_riconcilia_eventi_storici_con_fascicolo_corrente(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(
        app,
        studio_nome="Studio Audit",
        studio_slug="studio-audit",
        username="audit-admin",
    )
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    paths = tm.percorsi_dati(studio.slug)

    fascicoli = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
        studio_db=None,
    )
    fascicolo = fascicoli.nuovo(
        "Vendita immobili",
        TipoFascicolo.CIVILE,
        nome_cliente="Cliente Test",
    )
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "Ordinanza_32473463.pdf",
        TipoDocumento.ORDINANZA,
        b"pdf-demo",
        caricato_da="admin",
    )

    utenti = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    admin = utenti.autentica(tenant_admin.username, "PasswordSicura!123")
    assert admin is not None
    utenti.registra_evento(
        "fascicoli.documento.visualizza",
        id_utente=admin.id,
        username=admin.username,
        risorsa_tipo="fascicolo",
        risorsa_id="8962DDEB",
        dettagli="doc BB94330C - Ordinanza_32473463.pdf",
        ip="127.0.0.1",
        esito="OK",
    )

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=False,
        )
        assert login.status_code == 302
        response = client.get("/audit")

    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Riconciliato" in html
    assert "Evento storico registrato con ID 8962DDEB" in html
    assert fascicolo.id in html
    assert "Vendita immobili" in html


def test_file_critici_non_contengono_marker_di_mojibake():
    critical_files = [
        REPO_ROOT / ".editorconfig",
        REPO_ROOT / ".env.example",
        REPO_ROOT / "Dockerfile",
        REPO_ROOT / "README.md",
        REPO_ROOT / "railway.toml",
        REPO_ROOT / "pct/auth.py",
        REPO_ROOT / "pct/product_governance.py",
        REPO_ROOT / "pct/scheduler.py",
        REPO_ROOT / "web/services/core_runtime.py",
        REPO_ROOT / "web/services/observability_runtime.py",
        REPO_ROOT / "web/services/product_governance_surface.py",
        REPO_ROOT / "web/templates/base.html",
        REPO_ROOT / "web/templates/auth/audit.html",
        REPO_ROOT / "web/templates/auth/login.html",
        REPO_ROOT / "web/templates/auth/login_2fa.html",
        REPO_ROOT / "web/templates/admin/assistente_migrazione.html",
        REPO_ROOT / "web/templates/admin/osservabilita.html",
        REPO_ROOT / "web/templates/admin/legal_coverage_dashboard.html",
        REPO_ROOT / "web/templates/admin/legal_coverage_review.html",
        REPO_ROOT / "web/templates/admin/legal_updates_dashboard.html",
        REPO_ROOT / "web/templates/admin/legal_updates_review.html",
        REPO_ROOT / "web/templates/polisWeb.html",
        REPO_ROOT / "web/templates/portale/acquisizione_wizard.html",
        REPO_ROOT / "docs/STORAGE_MATRIX.md",
        REPO_ROOT / "docs/AUTHORIZATION_MODEL.md",
        REPO_ROOT / "docs/STORAGE_MIGRATION_PLAN.md",
        REPO_ROOT / "docs/E2E_TESTING_MATRIX.md",
        REPO_ROOT / "docs/OBSERVABILITY_AUDIT_PRODUCT.md",
        REPO_ROOT / "docs/LEGAL_UPDATE_INTELLIGENCE.md",
        REPO_ROOT / "docs/RELEASE_PROCESS.md",
    ]

    for path in critical_files:
        text = path.read_text(encoding="utf-8")
        assert MOJIBAKE_PATTERN.search(text) is None, path.name

    governance = (REPO_ROOT / "tools/check_repo_governance.py").read_text(encoding="utf-8")
    assert "MOJIBAKE_PATTERN" in governance
    assert "_find_mojibake_or_non_utf8_files" in governance
    assert "non UTF-8" in governance
