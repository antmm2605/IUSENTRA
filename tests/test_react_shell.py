from __future__ import annotations

import json
import io
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from pypdf import PdfReader

from pct.agenda import Agenda, TipoAppuntamento
from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.email_client import CartellaEmail, EmailRicevuta, GestioneEmailRicevute, StatoEmail
from pct.fascicoli import GestioneFascicoli, StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.messaggi import CanaleMsggio, ConfigMessaggistica, GestioneMessaggi, Messaggio, StatoMessaggio
from pct.privacy import GestioneTrattamenti
from pct.preventivi import GestionePreventivi, StatoPreventivo, VocePreventivo
from pct.scadenziario import GestioneScadenziario, PrioritaTermine, TipoTermine
from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto
from tests.test_applicazioni import _crea_operatore, _login
from web.app import create_app
from web.bootstrap.blueprint_registry import BLUEPRINT_REGISTRY

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    app.config["PRIVACY_DB"] = str(tmp_path / "privacy" / "registro.json")
    return app


def test_react_blueprints_registered(tmp_path: Path):
    app = _app(tmp_path)

    assert "react_shell" in app.blueprints
    assert "api_v1_react" in app.blueprints
    assert "api_v1_guida_pratica" in app.blueprints
    assert any(entry.name == "react_shell" for entry in BLUEPRINT_REGISTRY)
    assert any(entry.name == "api_v1_react" for entry in BLUEPRINT_REGISTRY)
    assert any(entry.name == "api_v1_guida_pratica" for entry in BLUEPRINT_REGISTRY)


def test_react_shell_primo_blocco_richiede_login(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/app-v2")

    assert response.status_code in {302, 303}
    assert "/login" in response.headers["Location"]


def test_acquisizione_telematica_senza_sessione_non_mostra_ui_mista(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/portali/pst/acquisizione?numero=1025&anno=2024")

    assert response.status_code in {302, 303}
    assert "/login" in response.headers["Location"]
    assert "next=/portali/pst/acquisizione" in response.headers["Location"]


def test_react_shell_app_v2_route_operativa_e_spegnibile_da_feature_flag(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        assert client.get("/app-v2").status_code == 200
        assert client.get("/app-v2/documenti").status_code == 200

    app.config["FEATURE_FLAGS"] = {
        "routes.appV2.dashboard.home": False,
        "routes.appV2.documents.list": False,
    }
    with app.test_client() as client:
        _login(client)
        assert client.get("/app-v2").status_code == 403
        assert client.get("/app-v2/documenti").status_code == 403


def test_react_shell_sidebar_usa_profilo_reale_sessione(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/admin/database")
        api = client.get("/api/v1/ui/bootstrap")

    html = response.get_data(as_text=True)
    match = re.search(
        r'<script id="iusentra-react-bootstrap" type="application/json">(.*?)</script>',
        html,
        flags=re.S,
    )
    assert response.status_code == 200
    assert match
    payload = json.loads(match.group(1))
    assert payload["user"]["displayName"] == "Operatore Test"
    assert payload["user"]["username"] == "operatore"
    assert payload["user"]["email"] == "operatore@example.it"
    assert payload["user"]["role"] == "AMMINISTRATORE"
    assert payload["user"]["initials"] == "O"
    assert payload["tenant"] is None
    assert payload["actions"]["profile"] == "/profilo"
    assert payload["actions"]["logout"] == "/logout"
    assert "Avv. Roberto Rossi" not in html
    assert "<span>8</span>" not in Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    api_payload = api.get_json()
    assert api.status_code == 200
    assert api_payload["user"]["displayName"] == "Operatore Test"
    assert api_payload["user"]["username"] == "operatore"
    assert api_payload["user"]["role"] == "AMMINISTRATORE"


def test_profilo_e_import_agenda_sono_route_react_operativa(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        profilo = client.get("/profilo")
        profilo_api = client.get("/api/v1/ui/profilo")
        import_agenda = client.get("/agenda/importa")

    assert profilo.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in profilo.get_data(as_text=True)
    assert profilo_api.status_code == 200
    assert profilo_api.get_json()["user"]["username"] == "operatore"
    assert import_agenda.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in import_agenda.get_data(as_text=True)
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "ProfiloPage" in app_source
    assert "AgendaImportPage" in app_source


def test_react_shell_mobile_sblocca_scroll_e_compatta_card():
    template = Path("web/templates/react_shell.html").read_text(encoding="utf-8")
    css = Path("frontend/src/index.css").read_text(encoding="utf-8")

    assert '<html lang="it" class="react-shell-document">' in template
    assert "body.react-shell-page .iu-shell" in css
    assert "overflow-y:auto!important" in css
    assert ".iu-metrics{\n    grid-template-columns:repeat(2,minmax(0,1fr));" in css
    assert ".iu-metric{\n    min-height:74px;" in css


def test_react_sidebar_contiene_navigazione_enterprise_completa():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/index.css").read_text(encoding="utf-8")

    for label in (
        "Recenti",
        "Calendario",
        "Nuovo Appuntamento",
        "Timesheet",
        "Tutti i Fascicoli",
        "Nuovo Fascicolo",
        "Cartelle Condivise",
        "Nuovo SMS/WA",
        "Preparazione Udienza Guidata",
        "Centro Servizi Telematici",
        "Guida firma digitale",
        "Parcelle e Fatture",
        "Preventivi e Incarichi",
        "Archivio Giurisprudenza",
        "Sincronizzazione Calendari",
        "Profili e Permessi",
        "Importa pratiche da Studio Telematico",
        "Registro Attività",
        "Registro GDPR",
    ):
        assert label in source

    assert ".iu-nav-section__head" in css
    assert ".iu-sidebar__nav{min-height:0;overflow-x:hidden;scrollbar-width:thin" in css
    assert "overflow-x:hidden;" in css
    assert ".iu-sidebar{\n  overflow-x:hidden;" in css
    assert ".iu-nav-link:hover{\n  transform:none;" in css
    assert "overflow-wrap:anywhere;" in css
    legacy_css = Path("web/static/scss/app.scss").read_text(encoding="utf-8")
    assert "#sidebar .sb-scroll {\n  overflow-x: hidden;" in legacy_css
    assert "#sidebar .sb-link,\n#sidebar .sb-link:hover {\n  transform: none;" in legacy_css
    assert "useState<string | null>(activeSectionId)" in source
    assert "openSectionId === section.id" in source
    assert "setOpenSectionId(current=>current===id?null:id)" in source
    assert "onCloseMobile" in source
    assert "onNavigate={onCloseMobile}" in source
    assert "mobileOpen ? 'Chiudi menu'" in source
    assert "{ label: 'Regia Operativa', icon: Sparkles, href: '/workspace-intelligente' }" in source
    assert "{ label: 'Nuovo Appuntamento', icon: CirclePlus, href: '/agenda/nuovo' }" in source
    assert "{ label: 'Preparazione Udienza Guidata', icon: Building2, href: '/wizard-pro/' }" in source
    assert ".iu-sidebar.iu-sidebar--mobile-open .iu-sidebar__toggle" in css
    assert "@media(min-width:821px) and (max-width:1180px)" in css
    assert ".iu-sidebar:not(.iu-sidebar--mobile-open){display:flex}" in css
    assert "@media(max-width:820px)" in css
    assert "AppErrorBoundary" in source
    assert ".iu-react-error" in css


def test_nav_legacy_allineata_react_senza_nascondere_sidebar():
    base = Path("web/templates/base.html").read_text(encoding="utf-8")
    settings_scss = Path("web/static/scss/pages/_settings.scss").read_text(encoding="utf-8")
    compiled_css = Path("web/static/css/app.css").read_text(encoding="utf-8")

    assert 'data-nav-surface="react-aligned-legacy"' in base
    for label in (
        "Servizi Telematici",
        "Centro Servizi Telematici",
        "PolisWeb / PST",
        "PDP Penale",
        "PAT Amministrativo",
        "PTT Tributario",
        "Tribunali / PEC",
        "Checklist deposito",
        "Guida firma digitale",
        "Studio",
        "Parcelle e Fatture",
        "Preventivi e Incarichi",
        "Compensi Forensi",
        "Editor professionale",
        "Redazione Atti",
        "Statistiche",
        "Ricerca Legale",
        "Archivio Giurisprudenza",
        "Strumenti Forensi",
        "Strumenti Operativi",
        "Sito Studio",
        "Notifiche",
        "Pagamenti",
        "Backup",
        "Impostazioni Studio",
        "Sincronizzazione Calendari",
        "Amministrazione",
        "Utenti",
        "Profili e Permessi",
        "Registro Attività",
        "Database",
        "Registro GDPR",
    ):
        assert label in base

    assert "request.blueprint in ('fatturazione'" in base
    assert "'impostazioni')" in base
    assert "'impostazioni_calendario')" in base
    for css_source in (settings_scss, compiled_css):
        assert "settings-modern-page) #sidebar" not in css_source
        assert "--sidebar-w: 0px" not in css_source
        assert "settings-modern-page) #app-body" not in css_source

    react_shell_allowlist = {
        "web/bootstrap/deposito_routes.py": [
            'render_react_shell_response(f"fascicoli/{id_fasc}/deposito/prepara")',
        ],
        "web/bootstrap/auth_management_routes.py": [
            'render_react_shell_response("profilo")',
        ],
    }

    for path in (
        "web/bootstrap/telematico_dashboard_routes.py",
        "web/bootstrap/polisweb_routes.py",
        "web/bootstrap/telematico_portali_routes.py",
        "web/bootstrap/deposito_routes.py",
        "web/bootstrap/reference_lookup_routes.py",
        "web/blueprints/fatturazione.py",
        "web/blueprints/template_atti.py",
        "web/blueprints/statistiche.py",
        "web/blueprints/legal_intelligence.py",
        "web/blueprints/giurisprudenza.py",
        "web/blueprints/strumenti_legali.py",
        "web/blueprints/notifiche.py",
        "web/blueprints/pagamenti.py",
        "web/bootstrap/backup_routes.py",
        "web/bootstrap/calendar_routes.py",
        "web/bootstrap/auth_management_routes.py",
        "web/bootstrap/admin_database_routes.py",
        "web/bootstrap/privacy_routes.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        if path in react_shell_allowlist:
            assert source.count("render_react_shell_response") == len(react_shell_allowlist[path]) + 1
            for expected_call in react_shell_allowlist[path]:
                assert expected_call in source
        else:
            assert "render_react_shell_response" not in source, path


def test_editor_professionale_resta_route_autonoma_distinta_da_redazione_atti():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/EditorProfessionalePage.tsx").read_text(encoding="utf-8")
    route_gate = Path("web/bootstrap/react_route_gate.py").read_text(encoding="utf-8")
    shell_source = Path("web/blueprints/react_shell.py").read_text(encoding="utf-8")
    manifest = json.loads(Path("tools/react-migration/route-manifest.json").read_text(encoding="utf-8"))

    assert "{ label: 'Editor professionale', icon: FilePenLine, href: '/editor-professionale' }" in app_source
    assert "{ label: 'Redazione Atti', icon: FilePenLine, href: '/redazione-atti' }" in app_source
    assert "const isEditorProfessionalePage = routeKey === '/editor-professionale'" in app_source
    assert "isEditorProfessionalePage?<EditorProfessionalePage/>" in app_source
    assert "Redazione Atti quando serve il modulo specifico degli atti" in page_source
    assert "Lettore documenti legali" in page_source
    assert "XML.P7M" in page_source
    assert '"/editor-professionale"' in route_gate
    assert '("/editor-professionale", "src/components/EditorProfessionalePage.tsx")' in shell_source
    editor_entry = next((entry for entry in manifest["routes"] if entry.get("route") == "/editor-professionale"), None)
    assert editor_entry is not None
    assert editor_entry["status"] == "react_operational_full"
    assert editor_entry["targetComponent"] == "frontend/src/components/EditorProfessionalePage.tsx"


def test_react_blocco_finale_studio_admin_completo():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    module_source = Path("frontend/src/studioModuleData.ts").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/StudioModulePage.tsx").read_text(encoding="utf-8")
    page_css = Path("frontend/src/components/StudioModulePage.css").read_text(encoding="utf-8")
    contracts = Path("frontend/scripts/check-react-contracts.mjs").read_text(encoding="utf-8")
    final_routes = Path("web/bootstrap/react_final_block_routes.py").read_text(encoding="utf-8")

    expected_routes = (
        "/studio",
        "/fatturazione",
        "/fatturazione/nuova",
        "/preventivi",
        "/preventivi/nuovo",
        "/preventivi/wizard",
        "/preventivi/conferimento/nuovo",
        "/compensi-forensi",
        "/documenti",
        "/editor-professionale",
        "/redazione-atti",
        "/template-atti/catalogo",
        "/template-atti/nuovo",
        "/portali/pst/acquisizione",
        "/statistiche",
        "/ricerca-legale",
        "/legal-intelligence/news",
        "/legal-intelligence/mediazione",
        "/giurisprudenza",
        "/giurisprudenza/nuova",
        "/strumenti-legali",
        "/strumenti-operativi",
        "/timesheet",
        "/cartelle-condivise",
        "/sito-studio",
        "/sito-studio/builder",
        "/sito-studio/contatti",
        "/notifiche-whatsapp",
        "/incassi-pagamenti",
        "/backup",
        "/impostazioni-studio",
        "/sincronizzazione-calendari",
        "/amministrazione",
        "/importa-pratiche-studio-telematico",
        "/utenti",
        "/utenti/nuovo",
        "/profili",
        "/registro-attivita",
        "/audit",
        "/admin/osservabilita",
        "/admin/database",
        "/registro-gdpr",
        "/privacy/registro/nuovo",
    )
    for route in expected_routes:
        assert route in module_source

    for label in (
        "Studio",
        "Parcelle e Fatture",
        "Preventivi e Incarichi",
        "Compensi Forensi",
        "Documenti",
        "Editor professionale",
        "Redazione Atti",
        "Importa pratica da PST",
        "Statistiche",
        "Ricerca Legale",
        "Archivio Giurisprudenza",
        "Strumenti Forensi",
        "Strumenti Operativi",
        "Timesheet",
        "Cartelle Condivise",
        "Sito Studio",
        "Notifiche",
        "Incassi e Pagamenti",
        "Backup",
        "Impostazioni Studio",
        "Sincronizzazione Calendari",
        "Amministrazione",
        "Importa pratiche da Studio Telematico",
        "Utenti",
        "Profili e Permessi",
        "Registro Attività",
        "Database",
        "Registro GDPR",
    ):
        assert label in module_source

    assert "StudioModulePage" in app_source
    assert "isStudioModulePage?<StudioModulePage/>" in app_source
    assert "findStudioModule(route)" in app_source
    assert "render_react_shell_response" not in final_routes
    assert "Nessuna rotta finale viene registrata qui" in final_routes
    assert "iusentra:open-floating-lex" in page_source
    assert "iusentra:lex-context" in page_source
    assert "_legacy=1" not in module_source
    assert "clean.length > best.length" in module_source
    assert "href: legacy('/fatturazione" not in module_source
    assert "href: legacy('/preventivi" not in module_source
    assert "href: legacy('/utenti" not in module_source
    assert "legacy(" not in module_source
    assert "/lex-operativo" not in module_source
    assert "href: '/portali/pst/acquisizione'" in module_source
    assert "href: '/portali/pst/acquisizione#checklist-operativa'" in module_source
    assert "href: '/impostazioni#dati-studio'" in module_source
    assert "href: '/impostazioni?tab=pec'" in module_source
    assert "href: '/impostazioni?tab=firma'" in module_source
    assert "href: '/impostazioni?tab=ai'" in module_source
    assert "anchorForCard" in page_source
    assert "handleActivateCard" in page_source
    assert "isSameModuleHref" in page_source
    assert 'id="funzione-operativa"' in page_source
    assert "window.history.pushState" in page_source
    assert "scrollIntoView({ behavior: 'smooth', block: 'center' })" in page_source
    assert "data-pct-ai-drag-handle" in Path("web/templates/components/pct_ai_widget.html").read_text(encoding="utf-8")
    assert "iusentra:open-floating-lex" in Path("web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")
    assert ".iu-sm-cards" in page_css
    assert ".iu-sm-card.is-selected" in page_css
    assert ".iu-sm-focus" in page_css
    assert ".iu-sm-hero aside{\n    display:none;" in page_css
    assert "clamp(" not in page_css
    assert "letter-spacing:-" not in page_css
    assert "studioModuleData" in contracts


def test_react_firma_documento_profonda_non_degrada_a_dettaglio_generico():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    signature_routes = Path("web/bootstrap/fascicoli_signature_routes.py").read_text(encoding="utf-8")
    gate_source = Path("web/bootstrap/react_route_gate.py").read_text(encoding="utf-8")

    assert 'kind: \'signature\'' in source
    assert "parts[1] === 'documenti' && parts[3] === 'firma'" in source
    assert "return <SignaturePage id={route.id} documentId={route.documentId}/>" in source
    assert "window.__IUSENTRA_LOCAL_SIGNER_URL__" in source
    assert "http://127.0.0.1:27272" in source
    assert "localSignerEndpoint('/ping')" in source
    assert "localSignerEndpoint('/firma')" in source
    assert "token_probe_fresh" in source
    assert "riavvio_signer_consigliato" in source
    assert "Token rilevato, riallineamento automatico" in source
    assert "localSignerCanSign" in source
    assert "localSignerOutdated" in source
    assert "Il PIN comparirà solo quando versione e token saranno allineati e pronti." in source
    assert "LOCAL_SIGNER_RESTART_URI = 'iusentra-local-signer://restart'" in source
    assert "LOCAL_SIGNER_UPDATE_URI = 'iusentra-local-signer://update'" in source
    assert "href={LOCAL_SIGNER_RESTART_URI}" in source
    assert "Riallinea automaticamente" in source
    assert "Se il browser chiede conferma" not in source
    assert "localSignerEndpoint('/diagnosi')" in source
    assert "visible_signature_mode: visibleSignatureMode" in source
    assert "visible_signature_place: visibleSignaturePlace" in source
    assert "visible_signature_datetime_mode: visibleSignatureDatetimeMode" in source
    assert "form.append('visible_signature_mode', visibleSignatureMode)" in source
    assert "form.append('visible_signature_place', visibleSignaturePlace)" in source
    assert "form.append('visible_signature_datetime_mode', visibleSignatureDatetimeMode)" in source
    assert 'name="visible_signature_mode" value={visibleSignatureMode}' in source
    assert 'name="visible_signature_place" value={visibleSignaturePlace}' in source
    assert 'name="visible_signature_datetime_mode" value={visibleSignatureDatetimeMode}' in source
    assert "Data e orario nel timbro" in source
    assert "Luogo firma" in source
    assert "basso_sinistra" in source
    assert "basso_destra" in source
    assert "Attenzione: documento già firmato." in source
    assert "confirm_resign" in source
    assert "alreadySigned && !confirmResign" in source
    assert '<JsonPostForm className="iu-fas-signature-form" action={firmaUrl} encType="multipart/form-data">' in source
    assert "/api/fascicoli/${encodedId}/documenti/${encodedDocId}/info-firma" in source
    assert 'methods=["GET", "POST"]' in signature_routes
    assert "requires_confirm_resign" in signature_routes
    assert 'render_react_shell_response(f"fascicoli/{id_fasc}/documenti/{id_doc}/firma")' in signature_routes
    assert 'lower.startswith("/fascicoli/") and "/wizard/" in lower' in gate_source
    assert ".iu-fascicolo-signature-page" in css
    assert ".iu-fas-signature-grid" in css
    assert ".iu-fas-signer-actions" in css
    assert ".iu-fas-resign-confirm" in css


def test_react_blocco_finale_route_reali_e_vista_classica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        operational_routes = (
            ("/studio", "Accesso ai portali", True),
            ("/fatturazione/", "Fatturazione", False),
            ("/fatturazione/nuova", "Nuova parcella", False),
            ("/preventivi/", "Preventivi e Incarichi", False),
            ("/preventivi/nuovo", "Nuovo Preventivo", False),
            ("/preventivi/conferimento/nuovo", "Conferimento", False),
            ("/tariffario", "Tariffario Forense", False),
            ("/compensi-forensi", "Tariffario Forense", True),
            ("/documenti", "Documenti", True),
            ("/editor-professionale", "Editor professionale", True),
            ("/redazione-atti", "Redazione Atti", True),
            ("/template-atti/catalogo", "Catalogo Atti", False),
            ("/portali/pst/acquisizione", "Importa pratica da PST", False),
            ("/statistiche/", "Statistiche Studio", False),
            ("/giurisprudenza/", "Archivio Giurisprudenza", False),
            ("/strumenti-legali/", "Strumenti Forensi", False),
            ("/strumenti-operativi", "Strumenti Operativi", True),
            ("/sito-studio/", "Sito Studio", False),
            ("/sito-studio/builder", "Sito Studio", False),
            ("/sito-studio/redazione-ai", "Sito Studio", False),
            ("/notifiche-whatsapp", "WhatsApp", True),
            ("/incassi-pagamenti", "Incassi", True),
            ("/impostazioni-studio", "Impostazioni", True),
            ("/sincronizzazione-calendari", "Sincronizzazione", True),
            ("/utenti", "Utenti", False),
            ("/profili", "Profili", False),
            ("/registro-attivita", "Registro", True),
        )
        for route, marker, follow_redirects in operational_routes:
            response = client.get(route, follow_redirects=True)
            assert response.status_code == 200, route
            html = response.get_data(as_text=True)
            if "IUSENTRA - React Shell" in html:
                assert 'id="root"' in html
            else:
                assert marker in html

        wizard_react = client.get("/preventivi/wizard?id_cliente=&from_page=")
        assert wizard_react.status_code == 200
        wizard_html = wizard_react.get_data(as_text=True)
        assert "IUSENTRA - React Shell" in wizard_html
        assert 'id="root"' in wizard_html

        for route in ("/privacy/registro", "/privacy/registro/nuovo", "/registro-gdpr", "/admin/database"):
            response = client.get(route, follow_redirects=True)
            assert response.status_code == 200, route
            html = response.get_data(as_text=True)
            assert "IUSENTRA - React Shell" in html
            assert 'id="root"' in html

        for route in (
            "/fatturazione/?_legacy=1",
            "/fatturazione/nuova?_legacy=1",
            "/preventivi/?_legacy=1",
            "/preventivi/nuovo?_legacy=1",
            "/preventivi/wizard?_legacy=1",
            "/preventivi/conferimento/nuovo?_legacy=1",
            "/tariffario?_legacy=1",
            "/strumenti-legali/?tool=contributo_unificato&_legacy=1",
            "/strumenti-legali/?tool=onorari_forensi&_legacy=1",
            "/timesheet?_legacy=1",
            "/cartelle-condivise?_legacy=1",
            "/portali/pst/acquisizione?_legacy=1",
            "/statistiche/?_legacy=1",
            "/ricerca-legale/news?_legacy=1",
            "/ricerca-legale/mediazione?_legacy=1",
            "/giurisprudenza/nuova?_legacy=1",
            "/sito-studio/builder?_legacy=1",
            "/sito-studio/contatti?_legacy=1",
            "/sito-studio/redazione-ai?_legacy=1",
            "/template-atti/catalogo?_legacy=1",
            "/template-atti/nuovo?_legacy=1",
            "/notifiche/?_legacy=1",
            "/utenti/nuovo?_legacy=1",
            "/audit?_legacy=1",
            "/privacy/registro/nuovo?_legacy=1",
            "/backup?_legacy=1",
            "/admin/database?_legacy=1",
        ):
            response = client.get(route)
            assert response.status_code == 200, route
            assert "IUSENTRA - React Shell" not in response.get_data(as_text=True)

        legacy_alias = client.get("/legal-intelligence/news?_legacy=1")
        assert legacy_alias.status_code == 301
        assert legacy_alias.headers["Location"].endswith("/ricerca-legale/news?_legacy=1")

        shortcut = client.get("/polisWeb/acquisizione?_legacy=1")
        assert shortcut.status_code in {302, 303}
        assert shortcut.headers["Location"].endswith("/portali/pst/acquisizione?_legacy=1")

        for route in (
            "/statistiche/api/produttivita?_legacy=1",
            "/statistiche/api/depositi-trend?_legacy=1",
        ):
            response = client.get(route)
            assert response.status_code == 200, route
            assert response.is_json
            assert "IUSENTRA - React Shell" not in response.get_data(as_text=True)


def test_statistiche_react_full_non_espone_fallback_legacy(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/statistiche", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    manifest = json.loads(Path("tools/react-migration/route-manifest.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["routes"] if item["route"] == "/statistiche")
    route_sources = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "frontend/src/components/StatistichePage.tsx",
            "frontend/src/statisticheData.ts",
            "web/services/react_statistiche_bridge.py",
        )
    )

    assert response.status_code == 200
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["writes"] == "none"
    assert entry["status"] == "react_operational_full"
    assert entry["unlockFromGate"] is True
    assert "/statistiche?_legacy=1" not in route_sources
    assert all("_legacy=1" not in action.get("href", "") for action in payload["actions"])


def test_blocco_telematico_studio_admin_resta_legacy_first():
    """Restano legacy-first solo aree non parificate o sottopercorsi sensibili."""

    gate_source = Path("web/bootstrap/react_route_gate.py").read_text(encoding="utf-8").lower()
    shell_source = Path("web/blueprints/react_shell.py").read_text(encoding="utf-8").lower()
    final_routes_source = Path("web/bootstrap/react_final_block_routes.py").read_text(encoding="utf-8")

    legacy_first_prefixes = (
        "/admin/osservabilita",
        "/applicazioni",
        "/checklist",
        "/database",
        "/portali",
    )

    for prefix in legacy_first_prefixes:
        quoted = f'"{prefix}"'
        assert quoted in gate_source, prefix
        assert quoted in shell_source, prefix

    for source in (gate_source, shell_source):
        assert "_react_telematico_graphical_paths" in source
        for exact in (
            "/telematico",
            "/servizi-telematici",
            "/polisweb",
            "/pdp",
            "/pat",
            "/sigit",
            "/tribunali",
            "/guida/firma-digitale",
        ):
            assert f'"{exact}"' in source, exact

    assert "FINAL_REACT_ROUTES: dict[str, str] = {\n" in final_routes_source
    assert "render_react_shell_response" not in final_routes_source


def test_react_ui_pack_componenti_token_e_array_operativi():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/data.ts").read_text(encoding="utf-8")
    component_source = Path("frontend/src/components/dashboard.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/index.css").read_text(encoding="utf-8")
    tokens = Path("frontend/src/design-system/tokens.ts").read_text(encoding="utf-8")

    for component in ("Panel", "KpiCard", "DossierCard", "SourceCard", "Badge", "Button"):
        assert f"function {component}" in component_source
        assert component in app_source or component in component_source

    assert "export type Dossier" in data_source
    assert "export type Source" in data_source
    assert "dossiers: asDossiers(payload)" in data_source
    assert "sources: asSources(payload, dashboard)" in data_source
    assert "@media(max-width:980px)" in css
    assert "--iu-space-4" in css
    assert "--iu-radius-md" in css
    assert "--iu-shadow-drawer" in css
    assert "spacing:" in tokens
    assert "typography:" in tokens


def test_react_ricerca_studio_e_pagina_separata_senza_mock():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    search_component = Path("frontend/src/components/RicercaStudioPage.tsx").read_text(encoding="utf-8")
    search_data = Path("frontend/src/searchData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/index.css").read_text(encoding="utf-8")

    assert "/global-search" in app_source
    assert "isSearchPage?<RicercaStudioPage" in app_source
    assert "Centro operativo di oggi" not in app_source
    assert "mockResults" not in search_component
    assert "searchStudio(" in search_data
    assert "/api/global-search" in search_data
    assert "reindexStudioSearch" in search_data
    assert "Ctrl K" in search_component
    assert "ArrowDown" in search_component
    assert ".iu-search-page" in css
    assert "@media(max-width:720px)" in css


def test_react_agenda_pagina_separata_collegata_nav_e_api():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    agenda_page = Path("frontend/src/components/AgendaPage.tsx").read_text(encoding="utf-8")
    agenda_data = Path("frontend/src/agendaData.ts").read_text(encoding="utf-8")
    floating_lex = Path("frontend/src/components/FloatingLex.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/index.css").read_text(encoding="utf-8")

    assert "/agenda" in app_source
    assert "isAgendaPage?<AgendaPage/>" in app_source
    assert "{ label: 'Calendario', icon: CalendarDays, href: '/agenda' }" in app_source
    assert "AgendaPage" in agenda_page
    assert "getAgendaPage" in agenda_data
    assert "/api/v1/ui/agenda" in agenda_data
    assert "/api/v1/agenda" in agenda_data
    assert "moveEventToDay" in agenda_data
    assert "moveEventToDateTime" in agenda_data
    assert "agendaRange" in agenda_data
    assert "createAppointmentHref" in agenda_page
    assert "onCreateSlot" in agenda_page
    assert "iu-ag-slot" in agenda_page
    assert "iu-ag-week--month" in agenda_page
    assert "/api/agenda/${encodeURIComponent(event.id)}/sposta" in agenda_page
    assert "messageReminderHref" in agenda_page
    assert "linkedDeadlineHref" in agenda_page
    assert 'action="/timesheet/nuovo"' in agenda_page
    assert "iusentra:open-floating-lex" in agenda_page
    assert 'href="/timesheet"' not in agenda_page
    assert ('href="/le' + 'x?context=agenda"') not in agenda_page
    assert "IUSENTRA_LEX_CONTEXT" in floating_lex
    assert "iusentra:lex-context" in floating_lex
    assert "return null" in floating_lex
    assert "const openMobileLex = () => {" in app_source
    assert "mobileFullscreen: true" in app_source
    assert 'className="iu-mobile__lex"' in app_source
    assert ".iu-agenda-page" in css
    assert ".iu-ag-slot" in css
    assert ".iu-ag-week--month" in css
    assert ".iu-mobile__lex" in css
    assert ".iu-lex-float{display:none!important}" not in css
    assert "bottom:calc(84px + env(safe-area-inset-bottom,0px))!important" in css
    assert "@media(max-width:760px)" in css
    assert "prefers-reduced-motion" in css


def test_react_nuovo_appuntamento_pagina_separata_con_backend_operativo():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    appointment_page = Path("frontend/src/components/NuovoAppuntamentoPage.tsx").read_text(encoding="utf-8")
    appointment_css = Path("frontend/src/components/NuovoAppuntamentoPage.css").read_text(encoding="utf-8")

    assert "/agenda/nuovo" in app_source
    assert "isNewAppointmentPage||isAppointmentEditPage?<NuovoAppuntamentoPage" in app_source
    assert "{ label: 'Nuovo Appuntamento', icon: CirclePlus, href: '/agenda/nuovo' }" in app_source
    assert "const isEditMode = Boolean(editId)" in appointment_page
    assert "const formAction = isEditMode ? `/agenda/${encodeURIComponent(editId)}/modifica` : '/agenda/nuovo'" in appointment_page
    assert "submitFormJson(formAction" in appointment_page
    assert "Salva modifiche" in appointment_page
    assert "params.get('ora')" in appointment_page
    assert "/api/clienti" in appointment_page
    assert "safeJson" in appointment_page
    assert "autocomplete: '1'" in appointment_page
    assert "normaliseClientSuggestion" in appointment_page
    assert "clientSuggestionsFromPayload" in appointment_page
    assert "firstText" in appointment_page
    assert "safeClientMatches" in appointment_page
    assert "Array.isArray(payload)" in appointment_page
    assert "Array.isArray(payload.data)" in appointment_page
    assert "agendaItemsFromPayload" in appointment_page
    assert "const itemDataOra = asText(item.data_ora)" in appointment_page
    assert ".catch(() =>" in appointment_page
    assert "Cliente senza nome" in appointment_page
    assert "/api/agenda?da=" in appointment_page
    assert "toUpperCase" in appointment_page
    assert "Completa titolo" in appointment_page
    assert "Contesto appuntamento pronto per Lex" in appointment_page
    assert ".iu-appointment-page" in appointment_css
    assert ".iu-appt-lex-float" not in appointment_css
    assert "@media(max-width:760px)" in appointment_css


def test_react_clienti_page_collegata_nav_api_e_lex():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/AnagraficaClientiPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/clientiData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/AnagraficaClientiPage.css").read_text(encoding="utf-8")
    floating_lex = Path("frontend/src/components/FloatingLex.tsx").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "/clienti" in app_source
    assert "isClientiPage?<AnagraficaClientiPage" in app_source
    assert "{ label: 'Anagrafica', icon: UsersRound, href: '/clienti' }" in app_source
    assert "getClientiPage" in data_source
    assert "/api/v1/ui/clienti" in data_source
    assert '@api_v1_react.get("/clienti")' in api_source
    assert "AnagraficaClientiPage" in page_source
    assert "FloatingLex" in page_source
    assert 'context="clienti"' in page_source
    assert "Senza recapiti" in page_source
    assert "Privacy" in page_source
    assert "Documenti scaduti" in page_source
    assert "IUSENTRA_LEX_CONTEXT" in floating_lex
    assert "iusentra:lex-context" in floating_lex
    assert "return null" in floating_lex
    assert ".iu-clienti-page" in css
    assert ".iu-cli-table" in css
    assert "@media(max-width:760px)" in css


def test_react_clienti_cartella_profonda_collegata_route_api_e_card_operative():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/CartellaClientePage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/clientiCartellaData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/CartellaClientePage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    route_source = Path("web/bootstrap/clienti_workspace_routes.py").read_text(encoding="utf-8")
    clienti_routes = Path("web/bootstrap/clienti_routes.py").read_text(encoding="utf-8")

    assert "CartellaClientePage" in app_source
    assert "isClientFolderPage?<CartellaClientePage/>" in app_source
    assert "isNewClientPage||isNewSubjectPage||isClientEditPage||isSubjectEditPage?<NuovoClientePage/>" in app_source
    assert '@api_v1_react.get("/clienti/<id_cliente>/cartella")' in api_source
    assert '@api_v1_react.get("/clienti/<id_cliente>/modifica")' in api_source
    assert 'render_react_shell_response(f"clienti/{id_cliente}/cartella")' in route_source
    assert 'redirect(_url_senza_vista_legacy(), code=302)' in route_source
    assert 'render_react_shell_response(f"clienti/{id_cliente}")' in clienti_routes
    assert 'render_react_shell_response(f"clienti/{id_cliente}/modifica")' in clienti_routes
    assert "data.actions.newDeadline" in page_source
    assert "data.actions.newMatter" in page_source
    assert "data.actions.newMessage" in page_source
    assert "Faldone cliente" in page_source
    assert "?_legacy=1" not in page_source
    assert "FloatingLex" in page_source
    assert "/api/v1/ui/clienti/${encodeURIComponent(idCliente)}/cartella" in data_source
    assert ".iu-cartella-cliente-page" in css
    assert ".iu-cart-actions" in css


def test_react_clienti_bridge_usa_repository_reali(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Marco",
        cognome="Moscato",
        codice_fiscale="MSCMRC75E26L063G",
    )
    cliente_repo.aggiorna_recapiti(cliente.id, email="antmm2605@gmail.com", cellulare="+393474940097")

    response = client.get("/api/v1/ui/clienti", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["contracts"]["route_owner"] == "react_shell"
    assert payload["summary"]["total"] >= 1
    assert payload["items"][0]["name"] == "Moscato Marco"
    assert payload["items"][0]["type"] == "pf"
    assert payload["items"][0]["email"] == "antmm2605@gmail.com"
    assert payload["items"][0]["phone"] == "+393474940097"
    assert payload["items"][0]["href"] == f"/clienti/{cliente.id}"


def test_route_ufficiali_clienti_e_soggetti_servono_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)

        for path in ("/clienti", "/clienti/nuovo", "/soggetti", "/soggetti/nuovo"):
            response = client.get(path)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html
            assert 'id="root"' in html

        classic_clienti = client.get("/clienti?_legacy=1")
        classic_cliente_form = client.get("/clienti/nuovo?_legacy=1")
        classic_soggetti = client.get("/soggetti?_legacy=1")
        classic_soggetto_form = client.get("/soggetti/nuovo?_legacy=1")

    assert classic_clienti.status_code == 200
    assert classic_cliente_form.status_code == 200
    assert classic_soggetti.status_code == 200
    assert classic_soggetto_form.status_code == 200
    assert 'id="root"' not in classic_clienti.get_data(as_text=True)
    assert 'id="modalScanner"' in classic_cliente_form.get_data(as_text=True)


def test_route_post_clienti_e_soggetti_restano_su_backend_operativo(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)

        created_client = client.post(
            "/clienti/nuovo",
            data={
                "tipo": "PERSONA_FISICA",
                "nome": "Giulia",
                "cognome": "Bianchi",
                "codice_fiscale": "BNCGLI80A41H501C",
                "telefono": "+390600000000",
            },
            follow_redirects=False,
        )
        created_subject = client.post(
            "/soggetti/nuovo",
            data={
                "tipo": "PERSONA_FISICA",
                "nome": "Luca",
                "cognome": "Verdi",
                "codice_fiscale": "VRDLCU80A01H501M",
                "qualifica": "CONTROPARTE",
            },
            follow_redirects=False,
        )

    assert created_client.status_code == 302
    assert created_subject.status_code == 302
    assert created_client.headers["Location"].startswith("/clienti/")
    assert created_subject.headers["Location"].startswith("/soggetti/")


def test_react_autocomplete_clienti_usa_payload_minimale_sicuro(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
    )

    response = client.get("/api/clienti", query_string={"q": "rossi", "autocomplete": "1", "limit": "8"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == [
        {
            "id": cliente.id,
            "nome": "Mario",
            "cognome": "Rossi",
            "ragione_sociale": "",
            "nome_completo": "Rossi Mario",
            "codice_fiscale": "RSSMRA80A01H501Z",
            "email": "",
            "pec": "",
            "procedimento": "",
            "numero_procedimento": "",
            "tribunale": "",
            "avvocato": "",
        }
    ]


def test_react_regia_operativa_e_pagina_separata_non_in_panorama():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert "/workspace-intelligente" in app_source
    assert "isRegiaPage?<RegiaOperativaPage" in app_source
    assert "{ label: 'Regia Operativa', icon: Sparkles, href: '/workspace-intelligente' }" in app_source
    assert "Azioni operative" in app_source
    assert "Centro operativo di oggi" not in app_source


def test_react_api_bridge_richiede_autenticazione(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/bootstrap")

    assert response.status_code == 401
    assert response.get_json()["errore"] == "Autenticazione richiesta."


def test_react_api_utenti_nuovo_crea_utente_json_senza_password(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/utenti/nuovo",
            json={
                "username": "nuovo.reactive",
                "password": "Temporanea123!",
                "ruolo": "SEGRETERIA",
                "nome_completo": "Nuovo Utente React",
                "email": "nuovo.reactive@example.it",
            },
        )
        lista_response = client.get("/api/v1/ui/utenti")
        audit_response = client.get("/api/v1/ui/audit")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["item"]["username"] == "nuovo.reactive"
    assert payload["item"]["role"] == "SEGRETERIA"
    assert "password" not in json.dumps(payload).lower()
    lista_payload = lista_response.get_json()
    audit_text = audit_response.get_data(as_text=True)
    assert any(record["username"] == "nuovo.reactive" for record in lista_payload["records"])
    assert "utenti.crea" in audit_text
    assert "Temporanea123!" not in audit_text


def test_react_api_utenti_nuovo_valida_campi_e_permesso(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    with app.app_context():
        gestore = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
        )
        gestore.crea(
            username="lettore",
            password="Lettore123!",
            ruolo=RuoloUtente.PRATICANTE,
            must_change_password=False,
        )

    with app.test_client() as client:
        _login(client)
        invalid = client.post(
            "/api/v1/ui/utenti/nuovo",
            json={"username": "", "password": "breve", "ruolo": "SUPERADMIN"},
        )
        client.post("/logout")
        client.post("/login", data={"username": "lettore", "password": "Lettore123!"})
        forbidden = client.post(
            "/api/v1/ui/utenti/nuovo",
            json={"username": "vietato", "password": "Temporanea123!", "ruolo": "SEGRETERIA"},
        )
    payload = invalid.get_json()
    forbidden_payload = forbidden.get_json()

    assert invalid.status_code == 200
    assert payload["ok"] is False
    assert "username" in payload["errors"]
    assert "password" in payload["errors"]
    assert "ruolo" in payload["errors"]
    assert "password" not in json.dumps(payload["item"] if "item" in payload else {}).lower()
    assert forbidden.status_code == 403
    assert forbidden_payload["ok"] is False
    assert "utenti.scrivi" in forbidden_payload["message"]


def test_react_api_bootstrap_espone_flag_primo_blocco_ufficiale(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/bootstrap", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["product"] == "IUSENTRA"
    assert payload["shell"] == "react"
    assert payload["mounted_at"] == "/app-v2"
    assert payload["route_flags"]["replace_dashboard"] is True
    assert payload["route_flags"]["replace_regia_operativa"] is True
    assert payload["route_flags"]["replace_global_search"] is True
    assert payload["route_flags"]["replace_agenda"] is True
    assert payload["route_flags"]["replace_fascicoli"] is True
    assert payload["route_flags"]["replace_clienti"] is True
    assert payload["route_flags"]["replace_soggetti"] is True
    assert payload["route_flags"]["replace_email"] is True
    assert payload["route_flags"]["replace_messaggi"] is True
    assert payload["route_flags"]["replace_telematico"] is True
    assert payload["route_flags"]["replace_telematico_surfaces"] is True
    assert payload["route_flags"]["replace_tribunali_pec"] is True
    assert payload["route_flags"]["replace_checklist_deposito"] is True
    assert payload["route_flags"]["replace_guida_firma_digitale"] is True


def test_react_comunicazioni_email_messaggi_collegate_nav_e_shell():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    email_page = Path("frontend/src/components/EmailPecPage.tsx").read_text(encoding="utf-8")
    email_data = Path("frontend/src/emailData.ts").read_text(encoding="utf-8")
    messaggi_page = Path("frontend/src/components/MessaggiPage.tsx").read_text(encoding="utf-8")
    messaggi_data = Path("frontend/src/messaggiData.ts").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "{ label: 'Email PEC', icon: Mail, href: '/email/', badge: 'PEC' }" in app_source
    assert "{ label: 'Email ordinaria', icon: Mail, href: '/email-ordinaria/', badge: 'SMTP' }" in app_source
    assert "{ label: 'Notifiche legali', icon: ShieldCheck, href: '/notifiche-legali', badge: 'L.53' }" in app_source
    assert "{ label: 'Messaggi', icon: MessageCircle, href: '/messaggi' }" in app_source
    assert "{ label: 'Nuovo SMS/WA', icon: Send, href: '/messaggi/nuovo' }" in app_source
    assert "isEmailOrdinariaPage?<EmailOrdinariaPage/>" in app_source
    assert "isNotificheLegaliPage?<NotificheLegaliPage/>" in app_source
    assert "isEmailPage?<EmailPecPage/>" in app_source
    assert "isNewMessagePage?<NuovoMessaggioPage/>" in app_source
    assert "isMessagesPage?<MessaggiPage/>" in app_source
    assert "Casella PEC dello studio" in email_page
    assert "Casella email ordinaria dello studio" in email_page
    assert "Cartelle PEC" in email_page
    assert "Cartelle email ordinaria" in email_page
    assert "getEmailPecPage" in email_data
    assert "getEmailOrdinariaPage" in email_data
    assert "/api/v1/ui/email" in email_data
    assert "/api/v1/ui/email-ordinaria" in email_data
    assert "/notifiche-legali" in email_data
    assert ("/lex" + "?context=email-pec") not in email_page
    assert ("/lex" + "?context=email-ordinaria") not in email_page
    assert ("/lex" + "?context=email-pec") not in email_data
    assert ("/lex" + "?context=email-ordinaria") not in email_data
    assert "Chiedi a Lex" not in email_page
    assert "cache: 'no-store'" in email_data
    assert "query.set('_ts', String(Date.now()))" in email_data
    dashboard_data = Path("frontend/src/data.ts").read_text(encoding="utf-8")
    assert "getDashboard(options: { refresh?: boolean } = {})" in dashboard_data
    assert "query.set('refresh', '1')" in dashboard_data
    assert "/api/v1/ui/dashboard${suffix}" in dashboard_data
    assert "syncDashboardMailboxes" in dashboard_data
    assert "query.set('_ts', String(Date.now()))" not in dashboard_data
    assert "cache:'no-store'" not in dashboard_data
    assert "cache: 'no-store'" not in dashboard_data
    assert "Nuovo messaggio" in messaggi_page
    assert "getMessaggiData" in messaggi_data
    assert "sendEndpoint" in messaggi_data
    assert "/api/v1/ui/messaggi" in messaggi_data
    assert '@api_v1_react.get("/email")' in api_source
    assert '@api_v1_react.get("/email-ordinaria")' in api_source
    assert '@api_v1_react.get("/notifiche-legali")' in api_source
    assert 'response.headers["Cache-Control"] = "no-store, max-age=0"' in api_source
    assert '@api_v1_react.get("/messaggi")' in api_source
    assert '@api_v1_react.get("/messaggi/nuovo")' in api_source


def test_route_ufficiali_email_messaggi_servono_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)

        for path in ("/email/", "/email-ordinaria/", "/notifiche-legali", "/messaggi", "/messaggi/nuovo"):
            response = client.get(path)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html
            assert 'id="root"' in html

        classic_email = client.get("/email/?_legacy=1")
        classic_ordinary = client.get("/email-ordinaria/?_legacy=1")
        classic_messages = client.get("/messaggi?_legacy=1")
        classic_new_message = client.get("/messaggi/nuovo?_legacy=1")

    assert classic_email.status_code == 200
    assert classic_ordinary.status_code in {200, 302}
    assert classic_messages.status_code == 200
    assert classic_new_message.status_code == 200
    assert 'id="root"' not in classic_email.get_data(as_text=True)
    assert 'id="root"' not in classic_messages.get_data(as_text=True)


def test_react_telematico_collegato_nav_api_e_lex():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/TelematicoPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/telematicoData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/TelematicoPage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "const TelematicoPage" in app_source
    assert "isTelematicoPage" in app_source
    assert "legacyOperationalRedirectHref(activePath)" in app_source
    assert "window.location.replace(forcedLegacyHref)" in app_source
    assert "Centro Servizi Telematici" in app_source
    assert "getTelematicoPage" in data_source
    assert "/api/v1/ui/telematico" in data_source
    assert '@api_v1_react.get("/telematico")' in api_source
    assert "FloatingLex" in page_source
    assert 'context="telematico"' in page_source
    assert ".iu-telematico-page" in css
    assert "@media(max-width:760px)" in css


def test_route_telematico_ufficiale_serve_shell_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/telematico", follow_redirects=True)
        html = response.get_data(as_text=True)
        classic = client.get("/telematico?_legacy=1")

    assert response.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in html
    assert 'id="root"' in html
    assert classic.status_code == 200
    assert 'id="root"' not in classic.get_data(as_text=True)


def test_react_telematico_bridge_payload_minimo(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/telematico", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["route_owner"] == "react_shell"
    assert {card["id"] for card in payload["channels"]} == {"pst", "pdp", "pat", "ptt"}
    assert "summary" in payload
    assert "controlTower" in payload


def test_react_superfici_telematiche_collegate_nav_api_css():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/TelematicoSurfacePage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/telematicoSurfacesData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/TelematicoSurfacePage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    bridge_source = Path("web/services/react_telematico_bridge.py").read_text(encoding="utf-8")
    polisweb_routes = Path("web/bootstrap/polisweb_routes.py").read_text(encoding="utf-8")
    portali_routes = Path("web/bootstrap/telematico_portali_routes.py").read_text(encoding="utf-8")
    deposito_routes = Path("web/bootstrap/deposito_routes.py").read_text(encoding="utf-8")
    lookup_routes = Path("web/bootstrap/reference_lookup_routes.py").read_text(encoding="utf-8")
    dashboard_routes = Path("web/bootstrap/telematico_dashboard_routes.py").read_text(encoding="utf-8")

    assert "const TelematicoSurfacePage" in app_source
    assert "isTelematicoSurfacePage" in app_source
    assert "isTelematicoSurfacePage?<TelematicoSurfacePage/>" in app_source
    assert "function isTelematicoSurfaceRoute" in app_source
    assert "route.startsWith('/portali/pst')" in app_source
    assert "route.startsWith('/portali/pdp')" in app_source
    assert "{ label: 'Centro Servizi Telematici', icon: BriefcaseBusiness, href: '/telematico' }" in app_source
    assert "{ label: 'PolisWeb / PST', icon: CloudUpload, href: '/polisWeb' }" in app_source
    assert "Panoramica PST" not in app_source
    assert "SIGP - Giudice di Pace" not in app_source
    assert "href: '/sigp/'" not in app_source
    assert "{ label: 'PDP Penale', icon: ShieldCheck, href: '/pdp' }" in app_source
    assert "{ label: 'PAT Amministrativo', icon: FileText, href: '/pat' }" in app_source
    assert "{ label: 'PTT Tributario', icon: FileText, href: '/sigit' }" in app_source
    assert "getTelematicoSurfacePage" in data_source
    assert "/api/v1/ui/telematico/surface/" in data_source
    assert "function initialSurfaceData" in page_source
    assert "useState<TelematicoSurfaceData>(() => initialSurfaceData(surfaceId))" in page_source
    assert "payload.surface.id === surfaceId ? payload : initialSurfaceData(surfaceId)" in page_source
    assert "route.startsWith('/portali/pdp')" in page_source
    assert "route.startsWith('/portali/pst')" in page_source
    assert "OfficeDirectory" in page_source
    assert "SurfaceSidePanels" in page_source
    assert "iu-tel-tribunali-workspace" in page_source
    assert 'id="acquisizione-portale"' in page_source
    assert "function AcquisitionWizard" in page_source
    assert "portalJson(portal, 'search'" in page_source
    assert "portalJson(portal, 'preview'" in page_source
    assert "portalJson(portal, 'analyze'" in page_source
    assert "portalJson(portal, 'import'" in page_source
    assert "portalJson(portal, 'importa-payload'" in page_source
    assert "portalJson(portal, 'importa-file'" in page_source
    assert "Sessione IUSENTRA" in page_source
    assert "Consegna finale PAT / SIGA e rientro ricevute" in page_source
    assert "Apri SIGA per consegna finale" in page_source
    assert "Step 3 - Rientro ricevute SIGA" in page_source
    assert "Step 4 - File ufficiali da registrare" in page_source
    assert "Il portale SIGA non viene incastrato in iframe" in page_source
    assert "Vai alla consegna SIGA" in page_source
    assert "create new" not in page_source
    assert "item.practiceId || item.id" in page_source
    assert "Endpoint browser:" not in page_source
    assert "collectAcquisitionFiles" in page_source
    assert "downloaded_files" in page_source
    assert "Local Signer" in page_source
    assert "Default PST: copia di consultazione" in page_source
    assert 'id="checklist-operativa"' in page_source
    assert 'id="operazione-attiva"' in page_source
    assert "navigateAction" in page_source
    assert "isSameSurfaceAction" in page_source
    assert "window.history.pushState" in page_source
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })" in page_source
    assert "Checklist operativa" in page_source
    assert "iu-tel-surface-hero__meta" in page_source
    assert "iu-tel-surface-hero__eyebrow" in page_source
    assert '"pst": "Importa pratica da PST"' in bridge_source
    assert '"practiceId": practice_id' in bridge_source
    assert '"importa-pratica"' in bridge_source
    assert '@api_v1_react.get("/telematico/surface/<surface>")' in api_source
    assert "build_react_telematico_surface_payload" in api_source
    assert "build_react_tribunali_payload" in api_source
    assert "render_react_shell_response" not in polisweb_routes
    assert "render_react_shell_response" not in portali_routes
    assert deposito_routes.count("render_react_shell_response") == 2
    assert 'render_react_shell_response(f"fascicoli/{id_fasc}/deposito/prepara")' in deposito_routes
    assert "render_react_shell_response" not in lookup_routes
    assert "render_react_shell_response" not in dashboard_routes
    assert '"telematico_dashboard.html"' in dashboard_routes
    assert '"polisWeb.html"' in polisweb_routes
    assert '"pdp.html"' in portali_routes
    assert '"pat.html"' in portali_routes
    assert '"sigit.html"' in portali_routes
    assert 'render_template("deposito_checklist.html")' in deposito_routes
    assert 'render_template("guida_firma_digitale.html")' in deposito_routes
    assert 'render_template("tribunali.html", uffici=uffici)' in lookup_routes
    assert ".iu-tel-surface-page" in css
    assert ".iu-tel-op-card.is-selected" in css
    assert ".iu-tel-active-op" in css
    assert ".iu-tel-acquisition" in css
    assert ".iu-tel-acq-form" in css
    assert ".iu-tel-acq-results" in css
    assert ".iu-tel-acq-import-result" in css
    assert ".iu-tel-surface-hero__meta a" in css
    assert "background:rgba(255,255,255,.16)" in css
    assert ".iu-tel-offices" in css
    assert ".iu-tel-tribunali-workspace" in css
    assert "grid-template-columns:minmax(0,1fr) 360px" in css
    assert "@media(max-width:860px)" in css


def test_route_ufficiali_superfici_telematiche_esatte_servono_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        for path in (
            "/telematico",
            "/servizi-telematici",
            "/polisWeb",
            "/portali/pst/acquisizione",
            "/pdp",
            "/pat",
            "/sigit",
            "/tribunali",
            "/guida/firma-digitale",
        ):
            response = client.get(path, follow_redirects=True)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html
            assert 'id="root"' in html

        for path in (
            "/portali/pdp/acquisizione",
            "/portali/pat/acquisizione",
            "/portali/ptt/acquisizione",
            "/portali/sigit/acquisizione",
        ):
            response = client.get(path, follow_redirects=True)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html
            assert 'id="root"' in html
            assert "Portale ufficiale assistito" not in html
            assert "Local Connector non raggiungibile" not in html

        for path in ("/sigp/", "/sigp-sync/"):
            response = client.get(path)
            assert response.status_code in {302, 303}, path
            assert response.headers["Location"].endswith("/portali/pst/acquisizione")

        checklist = client.get("/deposito/checklist", follow_redirects=True)
        checklist_html = checklist.get_data(as_text=True)
        assert checklist.status_code == 200
        assert '<html lang="it" class="react-shell-document">' in checklist_html
        assert 'id="root"' in checklist_html

        for path in ("/polisWeb?_legacy=1", "/pdp?_legacy=1", "/pat?_legacy=1", "/sigit?_legacy=1", "/tribunali?_legacy=1", "/deposito/checklist?_legacy=1", "/guida/firma-digitale?_legacy=1"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert 'id="root"' not in response.get_data(as_text=True)


def test_react_superfici_telematiche_api_payload_reale(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    def collect_hrefs(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "href" and isinstance(item, str):
                    yield item
                else:
                    yield from collect_hrefs(item)
        elif isinstance(value, list):
            for item in value:
                yield from collect_hrefs(item)

    checklist = client.get("/api/v1/ui/telematico/surface/checklist", headers={"X-API-Key": "react-test-key"})
    firma = client.get("/api/v1/ui/telematico/surface/firma", headers={"X-API-Key": "react-test-key"})
    polisweb = client.get("/api/v1/ui/telematico/surface/polisweb", headers={"X-API-Key": "react-test-key"})
    tribunali = client.get("/api/v1/ui/telematico/surface/tribunali", headers={"X-API-Key": "react-test-key"})

    checklist_payload = checklist.get_json()
    firma_payload = firma.get_json()
    polisweb_payload = polisweb.get_json()
    tribunali_payload = tribunali.get_json()

    assert checklist.status_code == 200
    assert checklist_payload["source"] == "repository_reali"
    assert checklist_payload["contracts"]["mock_fallback"] is False
    assert checklist_payload["surface"]["id"] == "checklist"
    assert checklist_payload["checklistGroups"]
    assert firma.status_code == 200
    assert firma_payload["surface"]["id"] == "firma"
    assert any("Local Signer" in group["title"] for group in firma_payload["checklistGroups"])
    assert polisweb.status_code == 200
    assert polisweb_payload["surface"]["id"] == "polisweb"
    assert polisweb_payload["surface"]["portal"] == "pst"
    assert polisweb_payload["operationCards"][0]["id"] == "importa-pratica"
    assert polisweb_payload["operationCards"][0]["title"] == "Importa pratica da PST"
    assert polisweb_payload["operationCards"][0]["actions"][0]["href"] == "/portali/pst/acquisizione"
    assert polisweb_payload["links"][1]["label"] == "Importa pratica da PST"
    assert polisweb_payload["links"][1]["href"] == "/portali/pst/acquisizione"
    assert polisweb_payload["channel"]["quickActions"][0]["label"] == "Importa pratica da PST"
    assert polisweb_payload["channel"]["quickActions"][0]["href"] == "/portali/pst/acquisizione"
    assert polisweb_payload["channel"]["quickActions"][1]["label"] == "Apri pagina"
    assert polisweb_payload["channel"]["quickActions"][1]["href"] == "/polisWeb"
    assert polisweb_payload["operationCards"][1]["actions"][0]["href"] == "/polisWeb"
    assert polisweb_payload["localSigner"]["browserUrl"] == "http://127.0.0.1:27272"
    assert polisweb_payload["localSigner"]["latestVersion"]
    assert polisweb_payload["localSigner"]["windowsUrl"].endswith("/setup/windows")
    for surface, expected_href, expected_home in (
        ("pdp", "/portali/pdp/acquisizione", "/pdp"),
        ("pat", "/portali/pat/acquisizione", "/pat"),
        ("ptt", "/portali/ptt/acquisizione", "/sigit"),
    ):
        payload = client.get(
            f"/api/v1/ui/telematico/surface/{surface}",
            headers={"X-API-Key": "react-test-key"},
        ).get_json()
        assert payload["operationCards"][0]["actions"][0]["href"] == expected_href
        assert payload["channel"]["quickActions"][0]["href"] == expected_href
        assert payload["channel"]["quickActions"][1]["href"] == expected_home
        assert not any(href.startswith("/app-v2/") for href in collect_hrefs(payload)), surface
        if surface == "pat":
            pat_procedure = payload["patProcedure"]
            module_ids = {module["id"] for module in pat_procedure["modules"]}
            assert pat_procedure["portal"]["officialUrl"] == "https://pe.prod.cloud.giustizia-amministrativa.it"
            assert pat_procedure["regime"]["formwebPriorityFrom"] == "2026-02-01"
            assert pat_procedure["regime"]["portalUploadLegacyRemoved"] is True
            assert pat_procedure["limits"]["formweb"]["maxFiles"] == 50
            assert pat_procedure["limits"]["formweb"]["maxTotalSizeMb"] == 300
            assert pat_procedure["limits"]["formweb"]["signature"] == "PADES"
            assert payload["surface"]["officialHref"] == ""
            assert {"deposito_ricorso", "deposito_atto", "richieste_segreteria", "foglio_excel_parti"} <= module_ids
            assert any(card["id"] == "pat-formweb" for card in payload["operationCards"])
            assert any(
                action["label"] == "Sessione SIGA"
                for card in payload["operationCards"]
                for action in card["actions"]
            )
            assert any(item["id"] == "pades" for group in payload["checklistGroups"] for item in group["items"])
            assert not any(".cer PST" in item["description"] and item["critical"] is False for group in payload["checklistGroups"] for item in group["items"])
    assert not any(href.startswith("/app-v2/") for href in collect_hrefs(polisweb_payload))
    telematico_payload = client.get("/api/v1/ui/telematico", headers={"X-API-Key": "react-test-key"}).get_json()
    assert not any(href.startswith("/app-v2/") for href in collect_hrefs(telematico_payload))
    assert tribunali.status_code == 200
    assert tribunali_payload["surface"]["id"] == "tribunali"
    assert not any(href.startswith("/app-v2/") for href in collect_hrefs(tribunali_payload))
    assert tribunali_payload["officeSummary"]["perType"] is not None
    assert tribunali_payload["officeSummary"]["sources"]
    assert "PEC di deposito" in tribunali_payload["officeSummary"]["policy"]
    assert any(row["indirizziTelematici"] for row in tribunali_payload["offices"] if row["pec"])

    component_source = Path("frontend/src/components/TelematicoSurfacePage.tsx").read_text(encoding="utf-8")
    assert "function PatProcedureWorkspace" in component_source
    pat_workspace_source = component_source.split("function PatProcedureWorkspace", 1)[1].split("function portalLabel", 1)[0]
    assert 'id="pat-step-5"' in pat_workspace_source
    assert "iu-pat-session-board" in pat_workspace_source
    assert "iu-pat-session-launch" in pat_workspace_source
    assert "/api/portali/pat/assistant" in pat_workspace_source
    assert "data.localSigner.browserUrl" in pat_workspace_source
    assert "patLocalConnectorJson('/portal-assistant/session/start'" in pat_workspace_source
    assert "local_session_id" in pat_workspace_source
    assert "Raccogli ricevute" in pat_workspace_source
    assert "window.open" not in pat_workspace_source
    assert "Avvia SIGA" in pat_workspace_source
    assert "Documenti del fascicolo" in pat_workspace_source
    assert "Genera modulo ufficiale" in pat_workspace_source
    assert "documentSelectionLimit" in pat_workspace_source
    assert "docs.slice(0, documentSelectionLimit)" in pat_workspace_source
    assert "Limite Formweb raggiunto" in pat_workspace_source
    assert "Formweb accetta massimo" in pat_workspace_source
    assert "/api/v1/ui/pat/moduli/compila" in pat_workspace_source
    assert "/api/v1/ui/pat/moduli/prefill" in pat_workspace_source
    assert "X-IUSENTRA-PAT-Preview" in pat_workspace_source
    assert "pdfDownloadUrl" in pat_workspace_source
    assert "iu-pat-pdf-ready__actions" in pat_workspace_source
    assert "href={pdfPreviewUrl}" in pat_workspace_source
    assert "pdfDownloadUrl || pdfPreviewUrl" not in pat_workspace_source
    assert "Scarica PDF" in pat_workspace_source
    css_source = Path("frontend/src/components/TelematicoSurfacePage.css").read_text(encoding="utf-8")
    assert "iu-pat-op-grid" in css_source
    assert "iu-pat-doc-row" in css_source
    assert "iu-pat-preview-panel" in css_source
    assert "iu-pat-generated-pdf-viewer" in css_source
    assert ".iu-pat-session-toolbar button.iu-pat-session-launch:hover:not(:disabled)" in css_source
    assert ".iu-pat-session-toolbar button.iu-pat-session-launch:focus-visible" in css_source
    assert "color:#ffffff" in css_source
    assert "<iframe" not in pat_workspace_source
    assert "setPreviewDocument(doc)" in pat_workspace_source
    assert "Anteprima documento" in pat_workspace_source
    assert "Controllo PDF prodotto da IUSENTRA" in pat_workspace_source
    assert "Dati compilati nel modulo ufficiale" in pat_workspace_source
    assert "Allegati inclusi nel PDF" in pat_workspace_source
    assert "Anteprima PDF non disponibile nel browser" not in pat_workspace_source
    assert "Apri fuori" not in pat_workspace_source
    assert "sandbox=" not in pat_workspace_source
    assert "Scarica modulo ufficiale" not in pat_workspace_source


def test_react_pat_modulo_compilabile_produce_pdf(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.post(
        "/api/v1/ui/pat/moduli/compila",
        headers={"X-API-Key": "react-test-key"},
        json={
            "module_id": "deposito_ricorso",
            "fields": {
                "sede": "TAR Lazio - Roma",
                "parte_depositante": "Mario Rossi",
                "codice_fiscale": "RSSMRA80A01H501U",
                "oggetto": "Impugnazione provvedimento amministrativo",
                "tipo_ricorso": "Ordinario",
                "ricorrente": "Mario Rossi",
                "resistente": "Comune di Roma",
                "contributo_unificato": "Pagato",
            },
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert len(response.data) > 1_000_000
    assert "ModuloDepositoRicorso_4.02_compilato_iusentra.pdf" in response.headers["Content-Disposition"]
    reader = PdfReader(io.BytesIO(response.data))
    assert len(reader.pages) >= 2
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Modulo PAT compilato da IUSENTRA" in extracted_text
    assert "Mario Rossi" in extracted_text
    assert "Impugnazione provvedimento amministrativo" in extracted_text
    assert "requires Adobe Reader" not in extracted_text
    embedded = reader.trailer["/Root"]["/Names"].get_object()["/EmbeddedFiles"].get_object()["/Names"]
    assert any(str(item) == "ModuloDepositoRicorso_4.02_ufficiale_XFA_compilato.pdf" for item in embedded)


def test_react_pat_modulo_compilabile_allega_documenti_del_fascicolo(tmp_path: Path):
    app = _app(tmp_path)
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501U",
    )
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Ricorso appalti PNRR",
        TipoFascicolo.AMMINISTRATIVO,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="TAR Lazio - Roma",
        numero_rg="1234",
        anno_rg=2026,
        controparte="Comune di Roma",
        oggetto="Impugnazione gara appalti PNRR",
    )
    documento = fascicoli.aggiungi_documento(
        fascicolo.id,
        "Ricorso principale.pdf",
        TipoDocumento.RICORSO,
        b"%PDF-1.4\n%ricorso allegato\n",
        note="Atto principale PAT",
    )

    client = app.test_client()
    response = client.post(
        "/api/v1/ui/pat/moduli/compila",
        headers={"X-API-Key": "react-test-key"},
        json={
            "moduleId": "deposito_ricorso",
            "fascicoloId": fascicolo.id,
            "fields": {
                "sede": "TAR Lazio - Roma",
                "parte_depositante": "Mario Rossi",
                "codice_fiscale": "RSSMRA80A01H501U",
                "oggetto": "Impugnazione gara appalti PNRR",
                "tipo_ricorso": "Ordinario",
                "ricorrente": "Mario Rossi",
                "resistente": "Comune di Roma",
                "contributo_unificato": "Pagato",
            },
            "documents": [{"id": documento.id, "role": "atto_principale", "requiresSignature": True}],
        },
    )

    assert response.status_code == 200
    reader = PdfReader(io.BytesIO(response.data))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Modulo PAT compilato da IUSENTRA" in extracted_text
    assert "Mario Rossi" in extracted_text
    assert "Impugnazione gara appalti PNRR" in extracted_text
    assert "requires Adobe Reader" not in extracted_text
    names = reader.trailer["/Root"].get("/Names")
    assert names
    embedded = names.get_object()["/EmbeddedFiles"].get_object()["/Names"]
    assert any(str(item) == "ModuloDepositoRicorso_4.02_ufficiale_XFA_compilato.pdf" for item in embedded)
    assert any(str(item) == "Ricorso principale.pdf" for item in embedded)


def test_react_pat_modulo_compilabile_espone_anteprima_sessione(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.post(
        "/api/v1/ui/pat/moduli/compila",
        headers={"X-API-Key": "react-test-key", "X-IUSENTRA-PAT-Preview": "1"},
        json={
            "moduleId": "deposito_ricorso",
            "fields": {
                "sede": "TAR Lazio - Roma",
                "parte_depositante": "Mario Rossi",
                "codice_fiscale": "RSSMRA80A01H501U",
                "oggetto": "Impugnazione provvedimento amministrativo",
                "tipo_ricorso": "Ordinario",
                "ricorrente": "Mario Rossi",
                "resistente": "Comune di Roma",
                "contributo_unificato": "Pagato",
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["filename"] == "ModuloDepositoRicorso_4.02_compilato_iusentra.pdf"
    assert payload["previewUrl"].startswith("/api/v1/ui/pat/moduli/preview/")
    assert payload["downloadUrl"].endswith("?download=1")

    preview = client.get(payload["previewUrl"], headers={"X-API-Key": "react-test-key"})
    assert preview.status_code == 200
    assert preview.mimetype == "application/pdf"
    assert preview.data.startswith(b"%PDF")
    assert preview.headers["Cache-Control"] == "no-store"

    download = client.get(payload["downloadUrl"], headers={"X-API-Key": "react-test-key"})
    assert download.status_code == 200
    assert "attachment" in download.headers["Content-Disposition"]


def test_react_pat_modulo_compilabile_valida_campi_obbligatori(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.post(
        "/api/v1/ui/pat/moduli/compila",
        headers={"X-API-Key": "react-test-key"},
        json={"moduleId": "deposito_ricorso", "fields": {}},
    )

    assert response.status_code == 422
    payload = response.get_json()
    assert payload["ok"] is False
    assert "Compilare i campi obbligatori" in payload["errore"]
    assert "Sede TAR / CDS / CGARS" in payload["missing"]


def test_react_pat_prefill_usa_fascicoli_clienti_reali(tmp_path: Path):
    app = _app(tmp_path)
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501U",
    )
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Ricorso appalti PNRR",
        TipoFascicolo.AMMINISTRATIVO,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="TAR Lazio - Roma",
        numero_rg="1234",
        anno_rg=2026,
        controparte="Comune di Roma",
        oggetto="Impugnazione gara appalti PNRR CIG 123",
    )
    documento = fascicoli.aggiungi_documento(
        fascicolo.id,
        "Ricorso principale.pdf",
        TipoDocumento.RICORSO,
        b"%PDF-1.4\n%ricorso\n",
        note="Atto principale PAT",
        fonte_documento="CARICAMENTO_STUDIO",
    )
    decreto = fascicoli.aggiungi_documento(
        fascicolo.id,
        "decretoGenerico.pdf",
        TipoDocumento.DECRETO,
        b"%PDF-1.4\n%decreto\n",
        note="Provvedimento storico da allegare",
        fonte_documento="CARICAMENTO_STUDIO",
    )
    ricevuta = fascicoli.aggiungi_documento(
        fascicolo.id,
        "ricevuta_pagopa_contributo.pdf",
        TipoDocumento.ALLEGATO,
        b"%PDF-1.4\n%ricevuta\n",
        note="Ricevuta contributo unificato",
        fonte_documento="CARICAMENTO_STUDIO",
    )

    client = app.test_client()
    response = client.get("/api/v1/ui/pat/moduli/prefill", headers={"X-API-Key": "react-test-key"})

    assert response.status_code == 200
    payload = response.get_json()
    matter = next(item for item in payload["matters"] if item["id"] == fascicolo.id)
    assert matter["source"] == "repository_fascicoli_clienti_soggetti"
    assert matter["fields"]["sede"] == "TAR Lazio - Roma"
    assert matter["fields"]["ricorrente"] == "Rossi Mario"
    assert matter["fields"]["resistente"] == "Comune di Roma"
    assert matter["fields"]["tipo_ricorso"] == "Appalti"
    assert matter["documentsSummary"] == "3 documenti disponibili nel fascicolo"
    assert matter["fields"]["descrizione_allegati"] == "Ricorso principale.pdf, decretoGenerico.pdf, ricevuta_pagopa_contributo.pdf"
    documents_by_name = {item["name"]: item for item in matter["documents"]}
    assert documents_by_name["Ricorso principale.pdf"]["id"] == documento.id
    assert documents_by_name["Ricorso principale.pdf"]["suggestedRole"] == "atto_principale"
    assert documents_by_name["Ricorso principale.pdf"]["previewUrl"].endswith(f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/visualizza")
    assert documents_by_name["Ricorso principale.pdf"]["downloadUrl"].endswith(f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/scarica")
    assert documents_by_name["decretoGenerico.pdf"]["id"] == decreto.id
    assert documents_by_name["decretoGenerico.pdf"]["suggestedRole"] == "allegato"
    assert documents_by_name["ricevuta_pagopa_contributo.pdf"]["id"] == ricevuta.id
    assert documents_by_name["ricevuta_pagopa_contributo.pdf"]["suggestedRole"] == "ricevuta_pagamento"


def test_react_user_facing_links_non_espongono_app_v2_prefix():
    pattern = re.compile(
        r"""(?:href|homeHref|importHref|presideHref|appHref|primaryHref|secondaryHref)\s*[:=]\s*["']\/app-v2(?:\/|["'])"""
    )
    roots = [Path("frontend/src"), Path("web/services")]
    allowed = {
        Path("web/services/app_v2_routing.py"),
        Path("web/services/feature_flags.py"),
        Path("frontend/src/app/router.tsx"),
        Path("frontend/src/lib/featureFlags.ts"),
        Path("frontend/src/wizardProData.ts"),
        Path("frontend/src/studioModuleData.ts"),
    }
    offenders = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx"} or path in allowed:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if pattern.search(text):
                offenders.append(str(path))
    assert offenders == []


def test_react_telematico_scroll_usa_offset_topbar_non_scroll_into_view():
    source = Path("frontend/src/components/TelematicoPage.tsx").read_text(encoding="utf-8")
    assert "function scrollToActiveChannel()" in source
    assert "window.scrollTo({ top, behavior: reducedMotion ? 'auto' : 'smooth' })" in source
    assert "document.querySelector<HTMLElement>('.iu-topbar')" in source
    assert "scrollIntoView" not in source
    assert "focusedChannelFromLocation()" in source

    surface_source = Path("frontend/src/components/TelematicoSurfacePage.tsx").read_text(encoding="utf-8")
    assert "function scrollToSurfaceTarget(targetId: string)" in surface_source
    assert "document.querySelector<HTMLElement>('.iu-topbar')" in surface_source
    assert "window.scrollTo({ top, behavior: reducedMotion ? 'auto' : 'smooth' })" in surface_source
    assert "scrollIntoView" not in surface_source


def test_react_wizard_pst_ricerca_ufficio_non_usa_evento_react_pooled():
    """Regressione reale: scrivere nel campo ufficio non deve rompere la shell.

    React azzera currentTarget prima degli updater funzionali di stato. Il
    wizard deve catturare il valore dell'input prima di chiamare setQuery,
    altrimenti digitando nell'ufficio giudiziario la pagina finisce nella
    error boundary.
    """

    source = Path("frontend/src/components/TelematicoSurfacePage.tsx").read_text(encoding="utf-8")
    broken_pattern = "setQuery((current) => ({\n                        ...current,\n                        ufficio: event.currentTarget.value"
    assert broken_pattern not in source
    assert "const nextOffice = event.currentTarget.value" in source
    assert "ufficio: nextOffice" in source


def test_react_wizard_pst_verifica_local_signer_dal_browser():
    source = Path("frontend/src/components/TelematicoSurfacePage.tsx").read_text(encoding="utf-8")
    assert "data.localSigner.browserUrl" in source
    assert "/ping?light=1" in source
    assert "iusentra-local-signer://restart" in source
    assert "isDesktopLocalSignerHost" in source
    assert "portalNeedsLocalSigner && !localSignerDesktopSupported" in source
    assert "Da mobile o tablet il controllo non viene eseguito" in source
    assert "Local Signer non rilevato su questo PC" in source
    assert "disabled={localSigner.checking || localSigner.unsupported}" in source
    assert "Local Signer non pronto sul PC" not in source
    assert "let checkedSigner = localSigner.ok ? localSigner : await checkLocalSigner(false)" in source
    assert "ok: reachable" in source
    assert "disabled={busy === 'search' || portalUsesOfficialAssistant || (portalNeedsLocalSigner && !localSignerDesktopSupported)}" in source
    assert "REACT_PST_SESSION_KEY" in source
    assert "localSignerJson('/pst/preflight-auth'" not in source
    assert "localSignerJson('/pst/ricerca-snapshot'" in source
    assert "localSignerJson('/pst/ricerca'" in source
    assert "localSignerPstFascicoloSnapshotJob" in source
    assert "localSignerJson('/pst/fascicolo-snapshot-job'" in source
    assert "localSignerJson(`/pst/jobs/${encodeURIComponent(jobId)}`" in source
    assert "localSignerJson('/pst/download-documenti-batch'" in source
    assert "localSignerJson('/portal-assistant/session/start'" in source
    assert "{official && !portalUsesOfficialAssistant ?" in source
    assert "'/pst/download-documento'" not in source
    assert "const prepared = await ensurePstPortalSession(tribunale)" not in source
    assert "ensurePstPortalSession" not in source
    assert "const exactPstSearch = Boolean(asText(query.numero) && asText(query.anno))" in source
    assert "nome_parte: exactPstSearch ? '' : (query.assistito || query.controparte)" in source
    assert "cf_parte: exactPstSearch ? '' : query.cf" in source
    assert "codiceFiscale: extractItalianFiscalCode(" in source
    assert "function coercePstCertificate(value: unknown): PstCertificate | null" in source
    assert "function certificateMatchesPstPreferences" in source
    assert "const LOCAL_SIGNER_PST_SEARCH_TIMEOUT_MS = 360_000" in source
    assert "const LOCAL_SIGNER_PST_DOWNLOAD_TIMEOUT_MS = 480_000" in source
    assert "const LOCAL_SIGNER_PST_STATUS_TIMEOUT_MS = 60_000" in source
    assert "function statusHasPstCertificatePreference" in source
    assert "const statusForPstCertificate = async (): Promise<JsonRecord>" in source
    assert "const certificateStatus = await statusForPstCertificate()" in source


def test_react_wizard_pst_anteprima_riusa_snapshot_ricerca_rg():
    source = Path("frontend/src/components/TelematicoSurfacePage.tsx").read_text(encoding="utf-8")
    assert "const signerDocumenti = asList(signerPayload.documenti || signerPayload.documents || signerPayload.catalogo)" in source
    assert "...(searchDocumenti.length ? { documenti: searchDocumenti } : {})" in source
    assert "activeSelection.raw.documenti || activeSelection.raw.documents || activeSelection.raw.catalogo" in source
    assert "snapshot = { fascicolo: activeSelection.raw, documenti, catalogo: documenti }" in source
    assert "function pstDocumentHasDirectPortalDownload(row: JsonRecord): boolean" in source
    assert "downloadDocumentoSemplice.action" in source
    assert "const hasSearchSnapshotPayload = Object.keys(snapshot).length > 0" in source
    assert "const hasSearchSnapshotDocuments = hasSearchSnapshotPayload" in source
    assert "const hasCompleteSearchSnapshotDocuments = hasSearchSnapshotDocuments" in source
    assert "activeSelection.raw.full_snapshot" in source
    assert "snapshot.master_detail" in source
    assert "Uso il catalogo documenti completo" in source
    assert "Uso i documenti gi" in source
    cached_branch = source.split("if (hasSearchSnapshotPayload)", 1)[1].split("} else {", 1)[0]
    fallback_branch = source.split("if (hasSearchSnapshotPayload)", 1)[1].split("} else {", 1)[1].split("payload = await portalJson(portal, 'preview'", 1)[0]
    assert "localSignerPstFascicoloSnapshotJob" not in cached_branch
    assert "localSignerPstFascicoloSnapshotJob" in fallback_branch
    assert "if (!documenti.length && !Object.keys(snapshot).length) throw refreshError" in fallback_branch
    assert "Apro l\\'anteprima con i documenti" in fallback_branch
    assert "localSignerJson(`/ping${signerCertPreferenceQuery(certificateStatus)}`" in source
    assert "const payload = await localSignerJson(`/seleziona-certificato${signerCertPreferenceQuery(certificateStatus)}`" in source
    assert "const pstAttorneyFiscalCode = (cert?: PstCertificate | null)" in source
    assert "cert?.codiceFiscale || status.codice_fiscale_avvocato || ''" in source
    assert "status.codice_fiscale_avvocato || cert?.codiceFiscale" not in source
    assert "cf_avvocato_fonte: pstCfSourceForDiagnostic" in source
    assert "cf_avvocato: pstCfForDiagnostic" in source
    assert "cf_avvocato: exactPstSearch ? ''" not in source
    assert "function ministerialHintsFromQuery(query: AcquisitionQuery): JsonRecord" in source
    assert "Tabella ministeriale" in source
    assert "Lavoro e previdenza" in source
    assert "Cassazione penale" in source
    assert "...ministerialHintsFromQuery(query)" in source
    assert "const pstHasPartySearch = () => Boolean(" in source
    assert "const pstHasYearSearch = () => portal === 'pst' && Boolean(asText(query.anno) && !asText(query.numero) && !pstHasPartySearch())" in source
    assert "const pstHasSearchCriteria = () => pstHasExactOrPartySearch() || pstHasYearSearch()" in source
    assert "un anno per vedere l'elenco fascicoli" in source
    assert "pstHasYearSearch() ? 'Cerca fascicoli' : 'Cerca fascicolo'" in source
    assert "const runPreview = async (activeSelection: AcquisitionResult | null = selection)" in source
    assert "if (portal === 'pst' && pstHasYearSearch()) void runPreview(result)" in source
    assert "const signerRows = asList(signerPayload.fascicoli || signerPayload.results)" in source
    assert "const snapshotFascicolo = asRecord(snapshot.fascicolo)" in source
    assert "const sourceRows = signerRows.length" in source
    assert "pst_session_id: session?.sessionId || ''" in source
    assert "function coercePstSessionFromPayload" in source
    assert "const session = activePstSessionFor(tribunale, cert)" in source
    assert "coercePstSessionFromPayload(selection?.raw?.pst_session, tribunale, cert)" in source
    assert "coercePstSessionFromPayload(preview.pst_session, tribunale, cert)" in source
    assert "function acquisitionInitialMappingMode" in source
    assert "mode: acquisitionInitialMappingMode(initialTargetFascicoloId)" in source
    assert "target_fascicolo_id: initialTargetFascicoloId" in source
    assert "const mappingTargetOptions = useMemo(() => {" in source
    assert "add(initialTargetFascicoloId, 'Pratica locale selezionata')" in source
    assert "params.get('mode')" in source
    assert "params.get('fascicolo_id')" in source
    assert "Step 4 - Cosa scaricare" in source
    assert "Step 4 - File ufficiali da registrare" in source
    assert "Scarico separato dall'importazione finale" in source
    assert "Registrazione separata dalla consegna ufficiale" in source
    assert "Documenti da scaricare:" in source
    assert "Vai alla destinazione" in source
    assert "Step 4 - Selezione" not in source
    assert "Scarica selezionati" in source
    assert "Scarica tutti" in source
    assert "Scarica selezionati dal PST" not in source
    assert "Scarica tutti dal PST" not in source
    assert "selectedDocumentKeys" in source
    assert "downloadSelectedPstDocuments" in source
    assert "filterPreviewForSelectedDocuments" in source
    assert "filterDownloadedFilesForSelectedPstDocuments" in source
    assert "missingPstDocumentsForDownload" in source
    assert "downloadedPstDocumentKeySet" in source
    assert "pstDocumentsMatch(file, doc)" in source
    assert "downloaded ? 'Scaricato' : selected ? 'Da scaricare' : 'Escluso'" in source
    assert "Usa pratica esistente" in source
    assert "Importa nel fascicolo" in source
    assert "Step 7 - Importa nel fascicolo" in source
    assert "Riepilogo importazione finale" in source
    assert "Importa nel fascicolo selezionato" in source
    assert "Crea pratica e importa" in source
    assert "function importResultRedirectHref(result: JsonRecord): string" in source
    assert "payload.documenti_url" in source
    assert "nested.documenti_url" in source
    assert "summary.documenti_url" in source
    assert "#sezione-documenti-fascicolo" in source
    assert "const importRedirectHref = importResultRedirectHref(payload)" in source
    assert "window.location.assign(importRedirectHref)" in source
    assert "Importazione completata. Apro il fascicolo importato." in source
    assert "Fascicolo importato" in source
    assert "Importazione completata. Fascicolo registrato nel gestionale." not in source
    assert "il collegamento al fascicolo non è stato restituito" in source
    assert "Importazione completata o presa in carico dal gestionale operativo" not in source
    assert "Importa nel gestionale" not in source
    assert "Import completato" not in source
    assert "Vai alla destinazione" in source
    assert "Scegli destinazione" not in source
    assert "Aggiorna pratica esistente" not in source
    assert "Collega a pratica esistente" not in source
    assert "Fascicolo locale da aggiornare" not in source
    assert "Fascicolo locale target" not in source
    assert "Dati fascicolo" in source
    assert "Documenti nel fascicolo" in source
    assert "function AcquisitionProgressView" in source
    assert "iu-tel-acq-progress" in source
    assert source.count("<AcquisitionProgressView progress={importProgress} />") == 1
    assert "Ricerca PST in corso" in source
    assert "Consultazione PST ancora in attesa" in source
    assert "Scaricamento documenti dal PST" in source
    assert "function pstPreviewDocumentIsDownloadable" in source
    assert "rawPreviewDocumentTitle" in source
    assert "function pstPreviewDocumentContentKey" in source
    assert "seenContent" in source
    assert "Aggiorno scheda ministeriale, allegati e comunicazioni disponibili" in source
    run_preview_source = source.split("const runPreview = async", 1)[1].split("const runAnalysis = async", 1)[0]
    assert "localSignerPstFascicoloSnapshotJob({" in run_preview_source
    assert "localSignerJson('/pst/fascicolo-snapshot'" not in run_preview_source
    assert "if (!documenti.length && !Object.keys(snapshot).length) throw refreshError" in run_preview_source


def test_import_studio_telematico_react_pubblica_exe_e_barra_avanzamento():
    data_source = Path("frontend/src/quickOrganizerImportData.ts").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/QuickOrganizerImportPage.tsx").read_text(encoding="utf-8")
    css_source = Path("frontend/src/components/QuickOrganizerImportPage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "/static/tools/PreparaPacchettoStudioTelematico.exe" in data_source
    assert "/static/tools/PreparaPacchettoStudioTelematico.exe" in api_source
    assert "/static/tools/prepara_import_studio_telematico.ps1" not in data_source
    assert "/static/tools/prepara_import_studio_telematico.ps1" not in api_source
    assert "type WorkProgress" in page_source
    assert "function WorkProgressBar" in page_source
    assert "sourcePath" in page_source
    assert "Pacchetto grande sul PC" in page_source
    assert "localPathEnabled" in data_source
    assert "Controllo con avvisi" in page_source
    assert "ZIP preparato dalla postazione Studio Telematico completa" in page_source
    assert "stage_referenced_package" in api_source
    assert "<WorkProgressBar progress={workProgress} />" in page_source
    assert "Caricamento e controllo del pacchetto in corso" in page_source
    assert "Importazione in corso" in page_source
    assert ".iu-st-import-progress" in css_source
    assert ".iu-st-import-local-path" in css_source


def test_portale_acquisizione_accetta_alias_fascicolo_id_per_mapping():
    source = Path("web/bootstrap/portali_acquisizione_routes.py").read_text(encoding="utf-8")
    template = Path("web/templates/portale/acquisizione_wizard.html").read_text(encoding="utf-8")

    assert 'request.args.get("id_fasc")' in source
    assert 'request.args.get("fascicolo_id")' in source
    assert 'request.args.get("target_fascicolo_id")' in source
    assert 'request.args.get("mode")' in source
    assert '"update_existing" if linked_fascicolo else "create_new"' in source
    assert "Destinazione pratica" in template
    assert "Fascicolo locale" in template
    assert "Aggiorna pratica esistente" not in template
    assert "Collega a pratica esistente" not in template
    assert "Fascicolo locale da aggiornare" not in template
    assert 'name="awMapMode" value="update_existing"' in template
    assert "function awSyncMappingModeFromTarget" in template


def test_portale_acquisizione_legacy_step4_preseleziona_aggiorna_pratica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Pratica PST da aggiornare",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="466",
        anno_rg=date.today().year,
    )

    with app.test_client() as client:
        _login(client)
        response = client.get(
            f"/portali/pst/acquisizione?_legacy=1&fascicolo_id={fascicolo.id}&mode=update_existing"
        )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Step 4 — Scelta contenuti da importare" in html
    assert "Destinazione pratica" in html
    assert "Usa pratica esistente" in html
    assert "Aggiorna pratica esistente" not in html
    assert "Collega a pratica esistente" not in html
    assert "Fascicolo locale da aggiornare" not in html
    assert f'data-initial-target="{fascicolo.id}"' in html
    assert 'name="awMapMode" value="update_existing" checked' in html


def test_react_wizard_acquisizione_portale_usa_endpoint_operativi_reali(tmp_path: Path):
    """Il wizard React deve poter chiamare la stessa filiera del vecchio wizard.

    Il test non finge il download dal portale: verifica invece che ogni endpoint
    operativo resti raggiungibile e risponda JSON controllato, anche quando il
    canale non ha una sessione Local Signer o una selezione valida.
    """

    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        status = client.get("/api/portali/pst/acquisizione/status")
        search = client.post(
            "/api/portali/pst/acquisizione/search",
            json={"ufficio": "Tribunale di Milano", "numero": "139", "anno": "2023"},
        )
        preview = client.post("/api/portali/pst/acquisizione/preview", json={})
        analyze = client.post("/api/portali/pst/acquisizione/analyze", json={})
        import_response = client.post("/api/portali/pst/acquisizione/import", json={})
        import_payload = client.post(
            "/api/portali/pst/acquisizione/importa-payload",
            json={"payload": {"selection": {}, "preview": {}}},
        )

    for response in (status, search, preview, analyze, import_response, import_payload):
        assert response.status_code == 200
        assert response.is_json

    assert status.get_json()["ok"] is True
    assert "status" in status.get_json()
    assert "results" in search.get_json()
    assert "preview" in preview.get_json()
    assert "analysis" in analyze.get_json()
    assert "errore" in import_response.get_json()
    assert "errore" in import_payload.get_json()


def test_route_importa_pratica_pst_resta_raggiungibile_dalla_nav(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/portali/pst/acquisizione")
        legacy = client.get("/portali/pst/acquisizione?_legacy=1")
        shortcut = client.get("/polisWeb/acquisizione")
        legacy_shortcut = client.get("/polisWeb/acquisizione?_legacy=1")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "IUSENTRA - React Shell" in html
    assert '<html lang="it" class="react-shell-document">' in html
    assert 'id="root"' in html
    assert "Importa pratica da PST" in Path("frontend/src/studioModuleData.ts").read_text(encoding="utf-8")
    legacy_html = legacy.get_data(as_text=True)
    assert legacy.status_code == 200
    assert "/api/portali/pst/acquisizione/search" in legacy_html
    assert "IUSENTRA - React Shell" not in legacy_html
    assert shortcut.status_code in {302, 303}
    assert shortcut.headers["Location"].endswith("/portali/pst/acquisizione")
    assert legacy_shortcut.status_code in {302, 303}
    assert legacy_shortcut.headers["Location"].endswith("/portali/pst/acquisizione?_legacy=1")


def test_route_ufficiali_primo_blocco_servono_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Primo blocco React",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="123",
        anno_rg=date.today().year,
    )

    with app.test_client() as client:
        _login(client)

        for path in (
            "/",
            "/workspace-intelligente",
            "/global-search",
            "/agenda",
            "/agenda/nuovo",
            "/fascicoli",
            "/fascicoli/archivio",
            "/fascicoli/esporta",
            "/fascicoli/nuovo",
            f"/fascicoli/{fascicolo.id}",
            f"/fascicoli/{fascicolo.id}/deposito/prepara",
            f"/fascicoli/{fascicolo.id}/modifica",
            f"/fascicoli/{fascicolo.id}/quadro",
        ):
            response = client.get(path)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html
            assert 'id="root"' in html

        classic_dashboard = client.get("/?_legacy=1")
        classic_workspace = client.get("/workspace-intelligente?_legacy=1")
        classic_search = client.get("/global-search?_legacy=1")
        classic_agenda = client.get("/agenda?_legacy=1")
        classic_fascicoli = client.get("/fascicoli?_legacy=1")

    assert classic_dashboard.status_code == 200
    assert classic_workspace.status_code == 200
    assert classic_search.status_code == 200
    assert classic_agenda.status_code == 200
    assert classic_fascicoli.status_code == 200
    assert 'id="root"' not in classic_dashboard.get_data(as_text=True)
    assert 'id="root"' not in classic_fascicoli.get_data(as_text=True)


def test_react_route_gate_copre_rotte_profonde_e_preserva_contratti_operativi(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Giulia", cognome="Bianchi")
    soggetti = GestioneSoggetti(app.config["SOGGETTI_DB"], app.config["SOGGETTI_PARTI_DB"])
    soggetto = soggetti.crea(TipoSoggetto.PERSONA_FISICA, nome="Mario", cognome="Verdi")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Rotta profonda React",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
    )
    fascicolo_penale = fascicoli.nuovo(
        "Rotta penale legacy",
        TipoFascicolo.PENALE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
    )
    scadenza = GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"]).nuova(
        "Deposito nota",
        TipoTermine.DEPOSITO_MEMORIA,
        date.today().isoformat(),
        id_fascicolo=fascicolo.id,
    )

    with app.test_client() as client:
        _login(client)
        for path in (
            f"/clienti/{cliente.id}",
            f"/clienti/{cliente.id}/cartella",
            f"/clienti/{cliente.id}/faldone",
            f"/clienti/{cliente.id}/portale",
            f"/fascicoli/{fascicolo.id}/quadro",
            f"/scadenziario/{scadenza.id}",
            f"/scadenziario/{scadenza.id}/modifica",
            f"/soggetti/{soggetto.id}",
            "/impostazioni",
            "/impostazioni-studio",
            "/impostazioni?tab=pec",
            "/impostazioni?tab=firma",
            "/impostazioni?tab=ai",
            "/impostazioni?tab=pagamenti",
            "/impostazioni?tab=notifiche",
            "/impostazioni?tab=backup",
            "/impostazioni?tab=calendario",
            "/impostazioni/calendario",
            "/impostazioni/pagamenti",
            "/impostazioni/sdi",
            "/notifiche",
            "/notifiche-whatsapp",
            "/backup",
            "/sincronizzazione-calendari",
            "/sito-studio/articoli/1/modifica",
        ):
            response = client.get(path)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html, path
            assert 'id="root"' in html, path

        legacy_cartella_redirect = client.get(f"/clienti/{cliente.id}/cartella?_legacy=1&tab=timeline", follow_redirects=False)
        legacy_cartella = client.get(f"/clienti/{cliente.id}/cartella?_legacy=1&tab=timeline", follow_redirects=True)

        for path in (
            f"/fascicoli/{fascicolo.id}/deposito/prepara?_legacy=1",
            f"/fascicoli/{fascicolo.id}/copertina",
            f"/fascicoli/{fascicolo_penale.id}/penale/pdp",
            "/checklist/test-template",
            "/applicazioni/fascicoli",
            "/scadenziario/export.ics",
            f"/scadenziario/{scadenza.id}/completa",
            "/sito-studio/articoli/art-1/modifica",
        ):
            response = client.get(path, follow_redirects=True)
            html = response.get_data(as_text=True)
            assert "IUSENTRA - React Shell" not in html, path
            assert '<html lang="it" class="react-shell-document">' not in html, path

        for path in (
            "/portali/pdp/acquisizione",
            "/portali/pat/acquisizione",
            "/portali/ptt/acquisizione",
            "/portali/sigit/acquisizione",
        ):
            response = client.get(path, follow_redirects=True)
            html = response.get_data(as_text=True)
            assert "IUSENTRA - React Shell" in html, path
            assert '<html lang="it" class="react-shell-document">' in html, path

        legacy = client.get("/impostazioni?tab=pec&_legacy=1")
        firma_operativa = client.get("/impostazioni?tab=firma")
        api = client.get("/api/v1/ui/dashboard", headers={"X-API-Key": "react-test-key"})
        csv = client.get("/fascicoli/export.csv")
        ics = client.get("/agenda/export.ics")
        visualizza = client.get(f"/fascicoli/{fascicolo.id}/documenti/documento-assente/visualizza")
        post = client.post(
            f"/fascicoli/{fascicolo.id}/stato",
            data={"stato": StatoFascicolo.ARCHIVIATO.value},
            follow_redirects=False,
        )

    assert legacy_cartella_redirect.status_code in {302, 303}
    assert legacy_cartella_redirect.headers["Location"] == f"/clienti/{cliente.id}/cartella?tab=timeline"
    legacy_cartella_html = legacy_cartella.get_data(as_text=True)
    assert legacy_cartella.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in legacy_cartella_html
    assert 'id="root"' in legacy_cartella_html
    assert "clienti/cartella.html" not in legacy_cartella_html
    assert legacy.status_code == 200
    assert 'id="root"' not in legacy.get_data(as_text=True)
    assert firma_operativa.status_code == 200
    assert 'id="root"' in firma_operativa.get_data(as_text=True)
    assert api.status_code == 200
    assert api.is_json
    assert "IUSENTRA - React Shell" not in api.get_data(as_text=True)
    assert csv.status_code == 200
    assert "IUSENTRA - React Shell" not in csv.get_data(as_text=True)
    assert ics.status_code == 200
    assert "IUSENTRA - React Shell" not in ics.get_data(as_text=True)
    assert "IUSENTRA - React Shell" not in visualizza.get_data(as_text=True)
    assert post.status_code in {302, 303}


def test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti():
    from web.bootstrap.react_route_gate import _excluded, _normalise_path

    legacy_first_routes = {
        "/admin/osservabilita",
            "/applicazioni",
            "/checklist",
            "/database",
        }

    for raw in sorted(legacy_first_routes):
        path = _normalise_path(raw)
        assert _excluded(path), path

    for raw in (
        "/portali/pdp/acquisizione",
        "/portali/pat/acquisizione",
        "/portali/ptt/acquisizione",
        "/portali/sigit/acquisizione",
        "/portali/pst/acquisizione",
        "/guida/firma-digitale",
        "/pat",
        "/pdp",
        "/polisWeb",
        "/servizi-telematici",
        "/sigit",
        "/telematico",
        "/tribunali",
    ):
        path = _normalise_path(raw)
        assert not _excluded(path), path

    for raw in (
        "/studio",
        "/amministrazione",
        "/utenti",
        "/profili",
        "/registro-attivita",
        "/admin/database",
        "/audit",
        "/backup",
        "/incassi-pagamenti",
        "/privacy/registro",
        "/privacy/registro/nuovo",
        "/sito-studio",
        "/sito-studio/builder",
        "/sito-studio/redazione-ai",
        "/sito-studio/articoli/2/modifica",
        "/scadenziario",
        "/scadenziario/nuova",
        "/scadenziario/scad-react",
        "/scadenziario/scad-react/modifica",
        "/statistiche",
        "/impostazioni",
        "/impostazioni-studio",
        "/impostazioni/pagamenti",
        "/impostazioni/calendario",
        "/impostazioni/sdi",
        "/notifiche",
        "/notifiche-whatsapp",
        "/sincronizzazione-calendari",
        "/fatturazione",
        "/preventivi",
        "/compensi-forensi",
        "/tariffario",
        "/documenti",
        "/redazione-atti",
        "/template-atti",
        "/template-atti/catalogo",
        "/ricerca-legale",
        "/legal-intelligence",
        "/legal-intelligence/news",
        "/legal-intelligence/mediazione",
        "/giurisprudenza",
        "/giurisprudenza/nuova",
        "/deposito/checklist",
        "/strumenti-legali",
        "/strumenti-operativi",
    ):
        assert not _excluded(_normalise_path(raw)), raw
    assert _excluded(_normalise_path("/deposito/checklist/download"))
    assert _excluded(_normalise_path("/privacy/registro/ABC123/elimina"))
    assert _excluded(_normalise_path("/scadenziario/export.ics"))
    assert _excluded(_normalise_path("/scadenziario/bulk-completa"))
    assert _excluded(_normalise_path("/scadenziario/scad-react/completa"))
    assert not _excluded(_normalise_path("/sito-studio/articoli/2/modifica"))
    assert _excluded(_normalise_path("/sito-studio/articoli/art-1/modifica"))


def test_impostazioni_react_api_redige_segreti_e_salva_configurazioni(tmp_path: Path):
    from pct.config_studio import GestioneConfigStudio

    config_path = tmp_path / "config" / "studio.json"
    app = _app(tmp_path)
    manager = GestioneConfigStudio(str(config_path))
    cfg = manager.config
    cfg.pec.password = "pec-super-segreta"
    cfg.smtp.password = "smtp-super-segreta"
    cfg.firma.password = "firma-super-segreta"
    cfg.whatsapp.twilio_token = "twilio-super-segreto"
    cfg.whatsapp.callmebot_key = "callmebot-super-segreta"
    manager.aggiorna(cfg)

    with app.test_client() as client:
        response = client.get("/api/v1/ui/impostazioni", headers={"X-API-Key": "react-test-key"})
        save_pec = client.post(
            "/api/v1/ui/impostazioni/pec",
            json={
                "indirizzo": "studio.nuovo@pec.example.it",
                "password": "",
                "smtp_host": "smtp.pec.example.it",
                "smtp_port": 465,
                "imap_host": "imap.pec.example.it",
                "imap_port": 993,
                "use_ssl": True,
            },
            headers={"X-API-Key": "react-test-key"},
        )
        save_firma = client.post(
            "/api/v1/ui/impostazioni/firma",
            json={
                "backend_preferito": "pkcs11",
                "cf_avvocato": "RSSMRA80A01H501Z",
                "visible_signature_mode": "basso_sinistra",
            },
            headers={"X-API-Key": "react-test-key"},
        )
        save_studio = client.post(
            "/api/v1/ui/impostazioni/studio",
            json={
                "nome": "Studio Legale Test",
                "avvocato": "Avv. Test",
                "qualifica_professionale": "Patrocinante in Cassazione",
                "numero_iscrizione_albo": "123",
                "ordine_avvocati": "Palmi",
                "piva": "",
                "cf": "",
                "indirizzo": "Via del Foro 1",
                "city": "Palmi",
                "province": "RC",
                "patron_name": "",
                "patron_day": 0,
                "patron_month": 0,
                "telefono": "",
                "email": "",
                "sito_web": "",
                "iban": "",
                "banca": "",
                "codice_fiscale_avvocato": "RSSMRA80A01H501Z",
            },
            headers={"X-API-Key": "react-test-key"},
        )
        save_pagamenti = client.post(
            "/api/v1/ui/impostazioni/pagamenti",
            json={
                "stripe_abilitato": True,
                "stripe_modo": "test",
                "stripe_pk_test": "pk_test_pubblica",
                "stripe_sk_test": "stripe-segreta",
                "paypal_abilitato": True,
                "paypal_modo": "sandbox",
                "paypal_client_id": "paypal-client",
                "paypal_client_secret": "paypal-segreta",
                "bonifico_abilitato": True,
                "bonifico_iban": "IT60X0542811101000000123456",
                "bonifico_intestazione": "Studio Legale",
            },
            headers={"X-API-Key": "react-test-key"},
        )
        link_notifica = client.post(
            "/api/v1/ui/impostazioni/notifiche/link",
            json={"numero": "+393331112233", "testo": "Messaggio di prova"},
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["contracts"]["writes"] == "json_api"
    assert payload["contracts"]["secrets_exposed"] is False
    assert payload["warnings"] == []
    assert {section["label"] for section in payload["sections"]} >= {
        "Dati Studio",
        "PEC",
        "Firma Digitale",
        "Email SMTP",
        "WhatsApp",
        "Scheduler",
            "AI Locale",
            "Pagamenti",
            "Notifiche",
            "Backup",
            "Calendari",
        }
    assert payload["pec"]["password"]["present"] is True
    assert payload["smtp"]["password"]["present"] is True
    assert payload["firma"]["password"]["present"] is True
    assert payload["whatsapp"]["twilio_token"]["present"] is True
    assert payload["whatsapp"]["callmebot_key"]["present"] is True
    assert payload["pagamenti"]["provider_attivi"] == ["bonifico"]
    assert "notifiche" in payload
    assert "backup" in payload
    assert "calendari" in payload
    for secret in (
        "pec-super-segreta",
        "smtp-super-segreta",
        "firma-super-segreta",
        "twilio-super-segreto",
        "callmebot-super-segreta",
    ):
        assert secret not in serialized

    assert save_pec.status_code == 200
    assert save_pec.get_json()["ok"] is True
    assert save_firma.status_code == 200
    assert save_firma.get_json()["ok"] is True
    assert save_studio.status_code == 200
    assert save_studio.get_json()["ok"] is True
    assert save_studio.get_json()["studio"]["qualifica_professionale"] == "Patrocinante in Cassazione"
    assert save_pagamenti.status_code == 200
    assert save_pagamenti.get_json()["ok"] is True
    assert save_pagamenti.get_json()["pagamenti"]["stripe_sk_test"]["present"] is True
    assert "stripe-segreta" not in json.dumps(save_pagamenti.get_json(), ensure_ascii=False)
    assert "paypal-segreta" not in json.dumps(save_pagamenti.get_json(), ensure_ascii=False)
    assert link_notifica.status_code == 200
    assert link_notifica.get_json()["ok"] is True
    from urllib.parse import urlparse

    link_whatsapp = urlparse(link_notifica.get_json()["link"])
    assert link_whatsapp.scheme == "https"
    assert link_whatsapp.netloc == "wa.me"
    assert link_whatsapp.path == "/393331112233"
    saved = GestioneConfigStudio(str(config_path)).config
    assert saved.pec.indirizzo == "studio.nuovo@pec.example.it"
    assert saved.pec.password == "pec-super-segreta"
    assert saved.firma.backend_preferito == "pkcs11"
    assert saved.firma.visible_signature_mode == "basso_sinistra"
    assert saved.studio.qualifica_professionale == "Patrocinante in Cassazione"
    from pct.studio_timbro import default_timbro_payload

    timbro = default_timbro_payload(config_studio=saved)
    assert timbro["qualifiche_professionali"] == "Patrocinante in Cassazione"


def test_impostazioni_firma_salva_scadenza_certificato_local_signer(tmp_path: Path):
    from pct.config_studio import GestioneConfigStudio

    config_path = tmp_path / "config" / "studio.json"
    app = _app(tmp_path)
    expiry = date.today() + timedelta(days=15)

    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/impostazioni/firma/certificato",
            json={
                "thumbprint": "AUTH-CF",
                "soggetto": "MNTRRT64L01L063H / Roberto Montagnese",
                "codice_fiscale": "MNTRRT64L01L063H",
                "emittente": "ArubaPEC EU Authentication Certificates CA G1",
                "scadenza": expiry.isoformat(),
            },
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    saved = GestioneConfigStudio(str(config_path)).config

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["firma"]["certificato_scadenza"] == expiry.isoformat()
    assert payload["firma"]["certificato_scadenza_it"] == expiry.strftime("%d/%m/%Y")
    assert payload["firma"]["certificato_giorni_scadenza"] == 15
    assert payload["firma"]["certificato_avviso_login"] is True
    assert saved.firma.certificato_codice_fiscale == "MNTRRT64L01L063H"
    assert saved.firma.certificato_scadenza_it == expiry.strftime("%d/%m/%Y")


def test_avviso_login_certificato_firma_a_venti_giorni():
    from pct.config_studio import ConfigStudio
    from web.services.signature_certificate_alerts import build_signature_certificate_login_warning

    cfg = ConfigStudio()
    cfg.firma.certificato_scadenza = "2026-07-01"
    cfg.firma.certificato_scadenza_it = "01/07/2026"
    alert = build_signature_certificate_login_warning(cfg, today=date(2026, 6, 16))

    assert alert is not None
    assert alert.category == "warning"
    assert alert.days == 15
    assert "mancano 15 giorni" in alert.message
    assert "01/07/2026" in alert.message


def test_impostazioni_notifiche_mostra_avvisi_operativi_persistenti(tmp_path: Path):
    from pct.notifications import NotificationRepository, NotificationRecord

    app = _app(tmp_path)
    _crea_operatore(app)
    with app.app_context():
        users = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
        ).tutti(solo_attivi=True)
        user_id = next(user.id for user in users if user.username == "operatore")
        NotificationRepository(app.config["NOTIFICATIONS_DB"]).upsert_notification(
            NotificationRecord(
                tenant_id="default",
                user_id=user_id,
                type="pec_deadline",
                priority="important",
                title="Scadenza PEC registrata",
                body="Presidio PEC collegato allo scadenziario e all'agenda per il 2030-01-15.",
                href="/scadenziario?vista=pec",
                source_type="pec_deadline",
                source_id="pec-test",
                dedupe_key="PEC_AUDIT:pec-test:deadline",
            )
        )

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/v1/ui/impostazioni?tab=notifiche")

    payload = response.get_json()
    avvisi = payload["notifiche"]["avvisi_operativi"]

    assert response.status_code == 200
    assert payload["notifiche"]["avvisi_operativi_non_letti"] == 1
    assert avvisi[0]["titolo"] == "Scadenza PEC registrata"
    assert avvisi[0]["href"] == "/scadenziario?vista=pec"


def test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale():
    page = Path("frontend/src/features/impostazioni/ImpostazioniPage.tsx").read_text(encoding="utf-8")
    form = Path("frontend/src/features/impostazioni/components/SettingsSectionForm.tsx").read_text(encoding="utf-8")
    actions = Path("frontend/src/features/impostazioni/components/SettingsActions.tsx").read_text(encoding="utf-8")
    payments = Path("frontend/src/features/impostazioni/components/PaymentsSettingsPanel.tsx").read_text(encoding="utf-8")
    notifications = Path("frontend/src/features/impostazioni/components/NotificationsSettingsPanel.tsx").read_text(encoding="utf-8")
    backup = Path("frontend/src/features/impostazioni/components/BackupSettingsPanel.tsx").read_text(encoding="utf-8")
    calendari = Path("frontend/src/features/impostazioni/components/CalendarSettingsPanel.tsx").read_text(encoding="utf-8")
    summary = Path("frontend/src/features/impostazioni/components/SettingsSummary.tsx").read_text(encoding="utf-8")
    styles = Path("frontend/src/features/impostazioni/ImpostazioniPage.css").read_text(encoding="utf-8")
    signer = Path("frontend/src/features/impostazioni/localSigner.ts").read_text(encoding="utf-8")
    api = Path("frontend/src/features/impostazioni/api.ts").read_text(encoding="utf-8")
    bridge = Path("web/services/react_impostazioni_bridge.py").read_text(encoding="utf-8")

    constants = Path("frontend/src/features/impostazioni/constants.ts").read_text(encoding="utf-8")
    assert "Dati Studio" in constants
    assert "Canali SdI" in constants
    assert "fatturapa_specifiche_formato" in bridge or "fatturapa_specifiche_formato" in constants
    assert "Qualifica professionale" in constants
    assert "Patrocinante in Cassazione" in constants
    assert "Eye, EyeOff" in form
    assert "Mostra valore inserito" in form
    assert "SettingsSummary" in page
    assert "checkLocalSigner" in actions
    assert "Certificato memorizzato" in actions
    assert "saveSignatureCertificateStatus" in actions
    assert "/api/v1/ui/impostazioni/firma/certificato" in api
    assert "certificato_scadenza_it" in bridge
    assert ".iu-settings-certificate" in styles
    assert "token_probe_fresh" in signer
    assert "certificato_windows_selezionato" in signer
    assert "iusentra-local-signer://restart" in api
    assert "/api/v1/ui/impostazioni/ai/bootstrap" in api
    assert "/api/v1/ui/impostazioni/notifiche/invia" in api
    assert "/api/v1/ui/impostazioni/calendari/profili" in api
    assert "/api/v1/ui/impostazioni/calendari/rigenera-link" in api
    assert "PaymentsSettingsPanel" in page
    assert "NotificationsSettingsPanel" in page
    assert "BackupSettingsPanel" in page
    assert "CalendarSettingsPanel" in page
    assert "sequence={false}" in Path("frontend/src/components/iusentra/IusFormSection.tsx").read_text(encoding="utf-8")
    assert "const headerSequenceProps = sequence ? { 'data-iusentra-sequence-slot': 'page-header' } : {}" in Path("frontend/src/components/iusentra/IusSectionHeader.tsx").read_text(encoding="utf-8")
    assert "Mostra valore inserito" in payments
    assert "Prepara link WhatsApp" in notifications
    assert "Invia promemoria" in notifications
    assert "Avvisi operativi" in notifications
    assert "avvisi_operativi" in notifications
    assert "createBackup" in backup
    assert "verifyBackupIntegrity" in backup
    assert "createCalendarProfile" in calendari
    assert "Rigenera link" in calendari
    assert "_legacy=1" not in api
    assert "Fonte:" not in summary
    assert "config_studio" not in summary
    assert "json_api" not in summary
    assert "React operativo" not in page
    assert "bridge impostazioni" not in page
    assert "segreti_redatti" not in page
    assert "Segreti protetti" not in page
    assert "Password e token sono indicati" not in page
    assert "Modello conversazione" not in constants
    assert "Modello ricerca documenti" not in constants
    assert "Automatico (consigliato)" in constants
    assert "Risposte dell'assistente" in constants
    assert "Genera password per le app Google" in constants
    assert "https://myaccount.google.com/apppasswords" in constants
    assert "helpLink.href" in form
    assert ".iu-settings-tabs {\n  display: flex;" in styles
    assert "flex-direction: column;" in styles
    assert ".iu-settings-tabs__list {\n  display: flex;" in styles
    assert "hidden={!isActiveSection}" in page
    assert "aria-hidden={!isActiveSection}" in page
    assert ".iu-settings-tabs [data-slot=\"tabs-content\"][hidden]" in styles


def test_impostazioni_react_ai_status_e_bootstrap_usano_runtime_locale(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    calls = {"bootstrap": 0, "refresh": 0}

    class FakeService:
        def health_snapshot(self):
            return {"runtime": {"status": "ready"}, "models": [{"name": "gemma3:1b"}]}

        def bootstrap_runtime(self, force=False):
            calls["bootstrap"] += 1
            return {"status": "ready", "force": force}

    monkeypatch.setattr("lex.providers.local_ai_service.get_local_ai_service", lambda: FakeService())
    monkeypatch.setattr(
        "lex.providers.ollama_runtime.refresh_live_ollama_runtime",
        lambda: calls.__setitem__("refresh", calls["refresh"] + 1),
    )

    with app.test_client() as client:
        status = client.get("/api/v1/ui/impostazioni/ai/status", headers={"X-API-Key": "react-test-key"})
        bootstrap = client.post(
            "/api/v1/ui/impostazioni/ai/bootstrap",
            json={"force": True},
            headers={"X-API-Key": "react-test-key"},
        )

    assert status.status_code == 200
    assert status.get_json()["ok"] is True
    assert status.get_json()["status_payload"]["runtime"]["status"] == "ready"
    assert bootstrap.status_code == 200
    assert bootstrap.get_json()["ok"] is True
    assert bootstrap.get_json()["result"]["force"] is True
    assert calls == {"bootstrap": 1, "refresh": 1}


def test_react_privacy_registro_operativo_secondo_pattern_oss(tmp_path: Path):
    """La pagina GDPR puo' essere React solo se il flusso e' completo.

    Il test riflette il protocollo in REACT_MIGRATION_PATTERNS_FROM_OSS:
    API tipizzata, form reali, POST legacy auditati, card non decorative e
    fallback tecnico `_legacy=1`.
    """

    app = _app(tmp_path)
    _crea_operatore(app)
    registro = GestioneTrattamenti(app.config["PRIVACY_DB"])
    extra = registro.nuovo(
        nome="Test trasferimento extra UE",
        finalita="Verifica migrazione React",
        categoria_dati="Dati identificativi",
        base_giuridica="Contratto (art. 6.1.b GDPR)",
        soggetti_interessati="Clienti",
        destinatari="Provider cloud",
        trasferimento_extra_ue=True,
        paese_destinazione="Stati Uniti",
    )

    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/privacyRegistroData.ts").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/PrivacyRegistroPage.tsx").read_text(encoding="utf-8")
    css_source = Path("frontend/src/components/PrivacyRegistroPage.css").read_text(encoding="utf-8")
    bridge_source = Path("web/services/react_privacy_bridge.py").read_text(encoding="utf-8")
    patterns = Path("docs/REACT_MIGRATION_PATTERNS_FROM_OSS.md").read_text(encoding="utf-8")
    plan = Path("docs/REACT_MIGRATION_MASTER_PLAN.md").read_text(encoding="utf-8")

    assert "const PrivacyRegistroPage" in app_source
    assert "isPrivacyRegistroPage?<PrivacyRegistroPage/>" in app_source
    assert "/api/v1/ui/privacy/registro" in data_source
    assert "mock_fallback" in data_source
    assert "submitFormJson(data.actions.create" in page_source
    assert "submitFormJson(item.deleteAction" in page_source
    assert "window.confirm" in page_source
    assert "_legacy=1" not in page_source
    assert ".iu-privacy-page" in css_source
    assert "@media(max-width:860px)" in css_source
    assert "BASE_GIURIDICA_OPTIONS" in bridge_source
    assert "Solo `react_operational_complete`" in plan
    assert "Protocollo obbligatorio pagina-per-pagina" in patterns

    with app.test_client() as client:
        _login(client)
        shell = client.get("/privacy/registro")
        new_shell = client.get("/privacy/registro/nuovo")
        legacy = client.get("/privacy/registro?_legacy=1")
        payload_response = client.get("/api/v1/ui/privacy/registro", headers={"X-API-Key": "react-test-key"})
        post_response = client.post(
            "/privacy/registro/nuovo",
            data={
                "nome": "Registro React POST",
                "finalita": "Controllo scrittura auditata",
                "categoria_dati": "Dati anagrafici",
                "base_giuridica": "Obbligo legale (art. 6.1.c GDPR)",
                "soggetti_interessati": "Clienti",
                "destinatari": "Studio",
                "termine_conservazione": "10 anni",
                "misure_sicurezza": "Backup e accesso profilato",
            },
            follow_redirects=False,
        )

    payload = payload_response.get_json()
    assert shell.status_code == 200
    assert "IUSENTRA - React Shell" in shell.get_data(as_text=True)
    assert new_shell.status_code == 200
    assert "IUSENTRA - React Shell" in new_shell.get_data(as_text=True)
    assert legacy.status_code == 200
    assert "IUSENTRA - React Shell" not in legacy.get_data(as_text=True)
    assert payload_response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["actions"]["create"] == "/privacy/registro/nuovo"
    assert payload["actions"]["exportAuditCsv"] == "/audit/esporta.csv"
    assert any(item["id"] == extra.id and item["extraEuTransfer"] for item in payload["treatments"])
    assert payload["summary"]["extraEu"] >= 1
    assert payload["summary"]["warnings"] >= 1
    assert post_response.status_code in {302, 303}
    assert post_response.headers["Location"].endswith("/privacy/registro")


def test_react_admin_database_operativo_secondo_pattern_oss(tmp_path: Path):
    """La pagina database e' React solo con dati reali e azioni amministrative esistenti."""

    app = _app(tmp_path)
    _crea_operatore(app)

    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/adminDatabaseData.ts").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/AdminDatabasePage.tsx").read_text(encoding="utf-8")
    css_source = Path("frontend/src/components/AdminDatabasePage.css").read_text(encoding="utf-8")
    bridge_source = Path("web/services/react_admin_database_bridge.py").read_text(encoding="utf-8")
    template_source = Path("web/templates/react_shell.html").read_text(encoding="utf-8")
    agents_source = Path("AGENTS.md").read_text(encoding="utf-8")

    assert "const AdminDatabasePage" in app_source
    assert "isAdminDatabasePage?<AdminDatabasePage/>" in app_source
    assert "readShellBootstrap" in app_source
    assert "Avv. Roberto Rossi" not in app_source
    assert "<span>8</span>" not in app_source
    assert "2026/004 - N.RG" not in app_source
    assert "/api/v1/ui/admin/database" in data_source
    assert "mock_fallback" in data_source
    assert "data.actions.verify" in page_source
    assert "data.actions.repair" in page_source
    assert "data.actions.optimize" in page_source
    assert "data.actions.migrate" in page_source
    assert "data.actions.precheckSqlite" in page_source
    assert "data.actions.reconcileSqlite" in page_source
    assert "data.actions.activateSqlite" in page_source
    assert "data.actions.exportZip" in page_source
    assert "data.actions.governance" not in page_source
    assert "data.actions.systemHealth" not in page_source
    assert "Governance" not in page_source
    assert "Salute sistema" not in page_source
    assert "'X-CSRF-Token': csrfToken()" in page_source
    assert "<JsonPostForm action={logoutAction}>" in app_source
    assert ".iu-db-page" in css_source
    assert "@media(max-width:900px)" in css_source
    assert "build_react_admin_database_payload" in bridge_source
    assert '"writes": "operational_routes"' in bridge_source
    assert "iusentra-react-bootstrap" in template_source
    assert "non mostrare mai dati inventati" in agents_source

    with app.test_client() as client:
        _login(client)
        shell = client.get("/admin/database")
        legacy = client.get("/admin/database?_legacy=1")
        payload_response = client.get("/api/v1/ui/admin/database")
        verify_response = client.get("/admin/database/verifica")
        repair_response = client.post("/admin/database/verifica-ripara")

    payload = payload_response.get_json()
    verify_payload = verify_response.get_json()
    repair_payload = repair_response.get_json()
    assert shell.status_code == 200
    assert "IUSENTRA - React Shell" in shell.get_data(as_text=True)
    assert "Operatore Test" in shell.get_data(as_text=True)
    assert legacy.status_code == 200
    assert "IUSENTRA - React Shell" not in legacy.get_data(as_text=True)
    assert payload_response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["actions"]["verify"] == "/admin/database/verifica"
    assert payload["actions"]["repair"] == "/admin/database/verifica-ripara"
    assert payload["actions"]["optimize"] == "/admin/database/ottimizza"
    assert payload["actions"]["migrate"] == "/admin/database/migra"
    assert payload["actions"]["precheckSqlite"] == "/admin/database/preverifica-sqlite"
    assert payload["actions"]["reconcileSqlite"] == "/admin/database/riconcilia-sqlite"
    assert payload["actions"]["activateSqlite"] == "/admin/database/attiva-sqlite"
    assert payload["actions"]["exportZip"] == "/admin/database/export"
    assert "governance" not in payload["actions"]
    assert "systemHealth" not in payload["actions"]
    assert payload["summary"]["modulesMonitored"] >= 1
    assert payload["modules"]
    assert verify_response.status_code == 200
    assert verify_payload["ok"] is True
    assert "problemi" in verify_payload
    assert repair_response.status_code == 200
    assert "riparazioni" in repair_payload


def test_pst_acquisizione_usa_lookup_uffici_reali_importati(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/v1/ui/telematico/surface/polisweb", headers={"X-API-Key": "react-test-key"})

    payload = response.get_json()
    offices = payload["offices"]
    assert response.status_code == 200
    assert len(offices) >= 1
    assert any(
        "Vibo Valentia" in office["nome"]
        and office["codice"]
        and office["codiceMinistero"] == "1020470090"
        and office["servizioPst"] == "JPW_SICID"
        for office in offices
    )
    assert any(
        office["nome"] == "Tribunale di Palmi"
        and office["codice"] == "0910011"
        and office["codiceMinistero"] == "0800570094"
        and office["servizioPst"] == "JPW_SICID"
        for office in offices
    )

    page_source = Path("frontend/src/components/TelematicoSurfacePage.tsx").read_text(encoding="utf-8")
    assert "Cerca mentre scrivi: es. Tribunale di Vibo Valentia" in page_source
    assert "officeMatches" in page_source
    assert "officeTypeFilter" in page_source
    assert "ufficio_codice: resolvedOfficeCode()" in page_source
    assert "ufficioCodice: office.codice || office.codiceMinistero" in page_source
    assert "fromExistingCode?.codice || explicitOfficeCode" in page_source
    assert "Il catalogo uffici non è ancora pronto" in page_source
    assert "if ((query.ufficio || query.ufficioCodice) && !data.offices.length) return" in page_source
    assert "selectedOfficeMatches(office)" in page_source
    assert "/api/v1/ui/local-signer/diagnostics" in page_source
    assert "iusentra-local-signer://update" in page_source
    assert "Aggiorna automaticamente" in page_source
    assert "auto_pst_test" in page_source
    assert "exact?.codice || exact?.codiceMinistero || query.ufficio" in page_source
    assert "office.codiceMinistero || office.codice" not in page_source
    assert "Step 5 - Fascicolo IUSENTRA" in page_source
    assert "Riepilogo sempre visibile" in page_source
    assert "acquisitionVisible" in page_source
    assert "AcquisitionWizardLegacy" not in page_source
    assert "Step {step}/7" in page_source
    assert "Riprova scarico" in page_source
    assert "REACT_ACQUISITION_HISTORY_KEY" in page_source
    assert "Fascicolo non scaricato dal portale" in page_source
    assert "previewPartyCountLabel" in page_source
    assert "nominativi unici" in page_source
    assert "previewParties.slice(0, 8)" not in page_source
    assert "recordAcquisitionHistory('empty'" in page_source
    assert "recordAcquisitionHistory('failed'" in page_source
    assert "auto_pst_test" in page_source
    assert "add('cf'" not in page_source


def test_local_signer_diagnostics_salva_server_studio(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/local-signer/diagnostics",
            json={
                "source": "browser-local-signer",
                "context": {
                    "event": "pst_search_empty",
                    "ufficio": "Tribunale di Palmi",
                    "ufficio_codice": "0910011",
                    "numero": "3441",
                    "anno": "2025",
                },
                "local_signer": {
                    "ok": True,
                    "versione": "1.6.41",
                    "dispositivi": [{"label": "CNS"}],
                },
                "local_logs": {
                    "ok": True,
                    "logs": [{"name": "local_signer.err.log", "tail": "PIN=123456\nPST ricerca-snapshot"}],
                },
            },
        )
        payload = response.get_json()
        latest_response = client.get("/api/v1/ui/local-signer/diagnostics/latest?limit=1")

    latest = latest_response.get_json()
    stored_path = tmp_path / "telematico" / "diagnostica-local-signer" / "eventi.jsonl"
    stored_text = stored_path.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert payload["ok"] is True
    assert latest_response.status_code == 200
    assert latest["items"][0]["context"]["ufficio_codice"] == "0910011"
    assert "PIN=[omesso]" in stored_text
    assert "123456" not in stored_text


def test_react_studio_module_card_e_runtime_non_sono_decorativi(tmp_path: Path):
    import re
    from urllib.parse import urlparse

    from web.bootstrap.react_route_gate import _excluded, _is_react_route, _normalise_path

    source = Path("frontend/src/studioModuleData.ts").read_text(encoding="utf-8")
    app = _app(tmp_path)
    _crea_operatore(app)

    assert "legacy(" not in source
    assert "_legacy=1" not in source
    assert "/lex-operativo" not in source

    hrefs = re.findall(r"href:\s*'([^']+)'", source)
    module_ids = sorted(set(re.findall(r"id:\s*'([^']+)'", source)))
    assert hrefs
    assert module_ids

    for href in hrefs:
        assert href.strip(), href
        assert href != "#", href
        if href.startswith(("http://", "https://")):
            continue
        path = _normalise_path(urlparse(href).path or "/")
        if path.startswith("/app-v2"):
            continue
        if _excluded(path):
            continue
        assert _is_react_route(path), href

    with app.test_client() as client:
        _login(client)
        for module_id in module_ids:
            response = client.get(f"/api/v1/ui/studio-modules/{module_id}", headers={"X-API-Key": "react-test-key"})
            assert response.status_code == 200, module_id
            payload = response.get_json()
            assert payload["source"] == "repository_reali"
            assert payload["contracts"]["mock_fallback"] is False
            assert payload["contracts"]["writes"] == "operational_routes"
            assert payload["operations"], module_id
            for operation in payload["operations"]:
                actions = operation.get("actions") or []
                records = operation.get("records") or []
                form = operation.get("form") or {}
                has_action = any((action.get("href") or "").strip() and action.get("href") != "#" for action in actions)
                has_record = any((record.get("href") or "").strip() and record.get("href") != "#" for record in records)
                has_form = bool((form.get("action") or "").strip() and form.get("action") != "#")
                assert has_action or has_record or has_form, f"{module_id}:{operation.get('id')}"
                for action in actions:
                    href = (action.get("href") or "").strip()
                    assert href and href != "#", f"{module_id}:{operation.get('id')}"
                    method = (action.get("method") or "GET").upper()
                    if method != "GET" or href.startswith(("http://", "https://")):
                        continue
                    path = _normalise_path(urlparse(href).path or "/")
                    if path.startswith("/app-v2") or path.startswith("/api"):
                        continue
                    if _excluded(path):
                        continue
                    assert _is_react_route(path), href


def test_react_studio_module_card_href_interni_raggiungibili(tmp_path: Path):
    """Ogni href dichiarato nelle card Studio deve aprire una route reale.

    Il controllo evita la regressione piu' pericolosa della migrazione React:
    card apparentemente operative che portano a 404, 500 o superfici non montate.
    Download, API e link esterni restano esclusi perche' hanno contratti diversi.
    """

    import re
    from urllib.parse import urlparse

    source = Path("frontend/src/studioModuleData.ts").read_text(encoding="utf-8")
    hrefs = sorted(set(re.findall(r"href:\s*'([^']+)'", source)))
    app = _app(tmp_path)
    _crea_operatore(app)

    checked: list[str] = []
    failures: list[tuple[str, int]] = []
    with app.test_client() as client:
        _login(client)
        for href in hrefs:
            if not href or href == "#" or href.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            path = urlparse(href).path or "/"
            if path.startswith("/api"):
                continue
            if any(token in path for token in ("<", ">", "${")):
                continue
            if path.endswith((".csv", ".pdf", ".zip", ".ics", ".xlsx")):
                continue
            checked.append(href)
            response = client.get(href, follow_redirects=False)
            if response.status_code == 404 or response.status_code >= 500:
                failures.append((href, response.status_code))

    assert len(checked) >= 60
    assert failures == []


def test_react_studio_module_deep_runtime_preventivi_conferimento_e_timesheet(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Roberto", cognome="Alessi")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Danno da sinistro",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Giudice di Pace - Palmi",
    )
    preventivi = GestionePreventivi(app.config["PREVENTIVI_DB"])
    preventivo = preventivi.crea_preventivo(
        id_cliente=cliente.id,
        id_fascicolo=fascicolo.id,
        oggetto="Azione risarcitoria",
        voci=[VocePreventivo("Compenso professionale", 1200.0)],
    )
    preventivi.cambia_stato_preventivo(preventivo.id, StatoPreventivo.ACCETTATO)

    with app.test_client() as client:
        _login(client)
        preventivi_response = client.get(
            "/api/v1/ui/studio-modules/preventivi",
            query_string={
                "path": f"/preventivi/conferimento/nuovo/{cliente.id}",
                "id_preventivo": preventivo.id,
                "from_page": "preventivo",
            },
            headers={"X-API-Key": "react-test-key"},
        )
        timesheet_response = client.get(
            "/api/v1/ui/studio-modules/timesheet",
            query_string={"path": "/timesheet"},
            headers={"X-API-Key": "react-test-key"},
        )

    preventivi_payload = preventivi_response.get_json()
    timesheet_payload = timesheet_response.get_json()
    conferimento = next(item for item in preventivi_payload["operations"] if item["id"] == "conferimento-incarico")
    nuovo_preventivo = next(item for item in preventivi_payload["operations"] if item["id"] == "nuovo-preventivo")
    timesheet_form = next(item for item in timesheet_payload["operations"] if item["id"] == "nuova-attivita")["form"]

    assert preventivi_response.status_code == 200
    assert preventivi_payload["source"] == "repository_reali"
    assert conferimento["form"]["action"] == "/preventivi/conferimento/nuovo"
    fields = {field["name"]: field for field in conferimento["form"]["fields"]}
    assert fields["id_cliente"]["value"] == cliente.id
    assert fields["id_fascicolo"]["value"] == fascicolo.id
    assert fields["id_preventivo"]["value"] == preventivo.id
    assert fields["avvocato_referente"]["required"] is True
    assert "numero_iscrizione_albo" in fields
    assert "ordine_avvocati" in fields
    new_fields = {field["name"]: field for field in nuovo_preventivo["form"]["fields"]}
    assert "voce_descr[]" in new_fields
    assert "voce_importo[]" in new_fields
    assert new_fields["applica_cassa"]["type"] == "checkbox"
    assert new_fields["applica_iva"]["type"] == "checkbox"
    assert timesheet_response.status_code == 200
    assert timesheet_form["action"] == "/timesheet/nuovo"
    assert any(field["name"] == "id_fascicolo" for field in timesheet_form["fields"])


def test_react_strumenti_legali_catalogo_form_e_calcolo_json(tmp_path: Path, monkeypatch):
    from web.blueprints import api_v1_react as react_api

    app = _app(tmp_path)
    _crea_operatore(app)

    def fake_uffici_competenti(
        comune: str,
        *,
        includi_speciali: bool = False,
        tipi_ufficio=None,
        solo_pec: bool = False,
    ):
        assert comune == "Taurianova"
        assert includi_speciali is False
        assert tipi_ufficio == []
        assert solo_pec is False
        return {
            "comune": comune,
            "totalVisible": 2,
            "totalOfficial": 3,
            "notes": ["Ricerca eseguita in tempo reale sulla fonte ministeriale, senza salvare copie locali."],
            "warnings": ["Verifica materia, rito, valore, foro applicabile e norme speciali prima dell'uso."],
            "source": {"title": "Ministero della Giustizia - Giustizia Map", "url": "https://www.giustizia.it/"},
            "offices": [
                {
                    "id": "ufficio-palmi",
                    "name": "Tribunale di PALMI",
                    "kind": "tribunale",
                    "typeLabel": "Tribunale",
                    "primary": True,
                    "address": "Via Roma",
                    "city": "PALMI",
                    "cap": "89015",
                    "phone": "0966 - 4169",
                    "email": "tribunale.palmi@giustizia.it",
                    "pec": "",
                    "site": "",
                    "assistenzaPct": {"orari": "dal lunedì al venerdì"},
                    "casellario": {},
                    "actions": [{"label": "Usa nel fascicolo", "href": "/fascicoli/nuovo", "method": "GET", "tone": "primary"}],
                }
            ],
        }

    monkeypatch.setattr(react_api, "ricerca_uffici_competenti", fake_uffici_competenti)

    with app.test_client() as client:
        _login(client)
        runtime_response = client.get(
            "/api/v1/ui/studio-modules/strumenti-forensi",
            query_string={"tool": "interessi", "app": "calcolo_interessi_di_mora"},
            headers={"X-API-Key": "react-test-key"},
        )
        calc_response = client.post(
            "/api/v1/ui/strumenti-legali/interessi",
            data={
                "int_tipo": "legali",
                "int_capitale": "1000",
                "int_data_inizio": "2024-01-01",
                "int_data_fine": "2024-12-31",
            },
            headers={"X-API-Key": "react-test-key"},
        )
        uffici_response = client.post(
            "/api/v1/ui/strumenti-legali/uffici_competenti",
            data={"comune": "Taurianova"},
            headers={"X-API-Key": "react-test-key"},
        )

    runtime_payload = runtime_response.get_json()
    calc_payload = calc_response.get_json()
    uffici_payload = uffici_response.get_json()
    suite = next(item for item in runtime_payload["operations"] if item["id"] == "suite-strumenti")
    uffici = next(item for item in runtime_payload["operations"] if (item.get("tool") or {}).get("toolId") == "uffici_competenti")
    interessi = next(item for item in runtime_payload["operations"] if (item.get("tool") or {}).get("toolId") == "interessi")
    onorari = next(item for item in runtime_payload["operations"] if (item.get("tool") or {}).get("toolId") == "onorari_forensi")
    uffici_fields = {field["name"]: field for field in uffici["form"]["fields"]}
    interessi_fields = {field["name"]: field for field in interessi["form"]["fields"]}
    onorari_fields = {field["name"]: field for field in onorari["form"]["fields"]}

    assert runtime_response.status_code == 200
    assert runtime_payload["source"] == "repository_reali"
    assert len(suite["records"]) >= 30
    assert any(record["id"] == "calcolo_interessi_di_mora" for record in suite["records"])
    assert uffici["title"] == "Uffici competenti per Comune"
    assert uffici["form"]["action"] == "/api/v1/ui/strumenti-legali/uffici_competenti"
    assert uffici_fields["comune"]["required"] is True
    assert uffici_fields["includi_speciali"]["type"] == "checkbox"
    assert interessi["title"] == "Calcolo Interessi di Mora"
    assert interessi["form"]["action"] == "/api/v1/ui/strumenti-legali/interessi"
    assert interessi_fields["int_capitale"]["type"] == "number"
    assert interessi_fields["int_tipo"]["value"] == "mora_commerciale"
    assert onorari_fields["onorari_fasi"]["type"] == "multiselect"
    assert len(onorari_fields["onorari_fasi"]["options"]) >= 4
    assert onorari_fields["onorari_cliente_qualificato"]["type"] == "select"
    assert onorari_fields["onorari_convenzione_predisposta_avvocato"]["type"] == "select"
    assert onorari_fields["onorari_equo_compenso_verificato"]["type"] == "select"
    assert onorari_fields["onorari_informativa_scritta"]["type"] == "select"

    assert calc_response.status_code == 200
    assert calc_payload["ok"] is True
    assert calc_payload["toolId"] == "interessi"
    assert any(metric["label"] == "Interessi maturati" for metric in calc_payload["metrics"])
    assert calc_payload["tables"][0]["title"] == "Segmenti di calcolo"
    assert uffici_response.status_code == 200
    assert uffici_payload["ok"] is True
    assert uffici_payload["toolId"] == "uffici_competenti"
    assert uffici_payload["offices"][0]["name"] == "Tribunale di PALMI"
    assert uffici_payload["tables"][0]["title"] == "Riepilogo uffici"


def test_endpoint_uffici_competenti_accetta_filtro_tipologia_per_nuovo_fascicolo(tmp_path: Path, monkeypatch):
    from web.blueprints import api_v1_react as react_api

    app = _app(tmp_path)
    _crea_operatore(app)
    calls: list[dict[str, object]] = []

    def fake_uffici_competenti(
        comune: str,
        *,
        includi_speciali: bool = False,
        tipi_ufficio=None,
        solo_pec: bool = False,
    ):
        calls.append({
            "comune": comune,
            "includi_speciali": includi_speciali,
            "tipi_ufficio": list(tipi_ufficio or []),
            "solo_pec": solo_pec,
        })
        return {
            "comune": comune,
            "totalVisible": 1,
            "totalOfficial": 3,
            "notes": ["Ricerca eseguita sulla fonte ministeriale."],
            "warnings": ["Verifica materia, rito, valore e foro applicabile prima dell'uso."],
            "source": {"title": "Ministero della Giustizia - Giustizia Map", "url": "https://www.giustizia.it/"},
            "offices": [
                {
                    "id": "unep-palmi",
                    "name": "Unep presso il Tribunale di PALMI",
                    "kind": "unep",
                    "typeLabel": "UNEP",
                    "primary": True,
                    "codiceMinistero": "0800570094",
                    "codiceGiustiziaLocale": "GLRC",
                    "address": "Via Sauro",
                    "city": "PALMI",
                    "cap": "89015",
                    "phone": "",
                    "email": "",
                    "pec": "unep.tribunale.palmi@giustiziacert.it",
                    "site": "",
                    "assistenzaPct": {},
                    "casellario": {},
                    "actions": [{"label": "Usa nel fascicolo", "href": "/fascicoli/nuovo", "method": "GET", "tone": "primary"}],
                }
            ],
        }

    monkeypatch.setattr(react_api, "ricerca_uffici_competenti", fake_uffici_competenti)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/strumenti-legali/uffici_competenti",
            data={
                "comune": "Taurianova",
                "includi_speciali": "1",
                "tipo_ufficio": "unep",
            },
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()

    assert response.status_code == 200
    assert calls == [{
        "comune": "Taurianova",
        "includi_speciali": True,
        "tipi_ufficio": ["unep"],
        "solo_pec": False,
    }]
    assert payload["ok"] is True
    assert payload["offices"][0]["kind"] == "unep"
    assert payload["offices"][0]["codiceMinistero"] == "0800570094"
    assert payload["offices"][0]["pec"] == "unep.tribunale.palmi@giustiziacert.it"


def test_react_studio_module_frontend_supporta_rotte_profonde_e_form_reali():
    page_source = Path("frontend/src/components/StudioModulePage.tsx").read_text(encoding="utf-8")
    runtime_source = Path("frontend/src/studioModuleRuntime.ts").read_text(encoding="utf-8")

    assert "currentPath.startsWith(`${cardPath}/`)" in page_source
    assert "field.type === 'hidden'" in page_source
    assert "field.type === 'checkbox'" in page_source
    assert "field.type === 'file'" in page_source
    assert "field.type === 'multiselect'" in page_source
    assert "normaliseStudioRuntimeResult" in page_source
    assert "OfficeResultCards" in page_source
    assert "Assistenza depositi telematici" in page_source
    assert "onSubmitOperation(event, operation)" in page_source
    assert "fetch(operation.form.action" in page_source
    assert "toolId: text(tool.toolId)" in runtime_source
    assert "offices: list(item.offices).map(normaliseOffice)" in runtime_source
    assert "encType={operation.form.enctype || undefined}" in page_source
    assert "params.set('path', window.location.pathname)" in runtime_source
    assert "current.forEach((value, key) => params.append(key, value))" in runtime_source


def test_react_migration_matrice_completa_route_api_e_card_operative(tmp_path: Path):
    """Gate finale: ogni voce richiesta deve servire React e avere azioni reali.

    Questo test copre il primo blocco, i servizi telematici, studio e
    amministrazione. Le route di scrittura, download e API restano fuori dal
    gate HTML, ma le card React devono puntare a href/form/endpoint effettivi.
    """

    def _collect_links(value):
        links = []
        if isinstance(value, dict):
            for key, item in value.items():
                key_norm = str(key).lower()
                if isinstance(item, str) and (
                    key_norm == "action"
                    or key_norm == "href"
                    or key_norm.endswith("href")
                    or key_norm.endswith("endpoint")
                    or key_norm in {"list", "detail", "sync", "settings", "compose"}
                    or item.startswith("/")
                    or item.startswith("http://")
                    or item.startswith("https://")
                ):
                    links.append(item)
                else:
                    links.extend(_collect_links(item))
        elif isinstance(value, list):
            for item in value:
                links.extend(_collect_links(item))
        return links

    def _assert_react_shell(client, label: str, path: str):
        response = client.get(path)
        html = response.get_data(as_text=True)
        assert response.status_code == 200, f"{label}: {path}"
        assert '<html lang="it" class="react-shell-document">' in html, f"{label}: {path}"
        assert 'id="root"' in html, f"{label}: {path}"

    def _assert_payload_operativo(client, label: str, path: str, *, require_links: bool = True):
        response = client.get(path, headers={"X-API-Key": "react-test-key"})
        assert response.status_code == 200, f"{label}: {path}"
        assert response.is_json, f"{label}: {path}"
        payload = response.get_json()
        assert isinstance(payload, dict), label
        if "source" in payload:
            assert payload["source"] in {"repository_reali", "errore_controllato"}, label
        contracts = payload.get("contracts") or {}
        if contracts:
            assert contracts.get("mock_fallback") is False, label
        links = [
            link
            for link in _collect_links(payload)
            if isinstance(link, str)
            and link.strip()
            and link.strip() != "#"
            and not link.strip().startswith("javascript:")
        ]
        assert all("_legacy=1" not in link for link in links), label
        if require_links:
            assert links, label
        return payload

    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    studio_source = Path("frontend/src/studioModuleData.ts").read_text(encoding="utf-8")
    assert "_legacy=1" not in studio_source
    assert "legacy(" not in studio_source

    expected_visible_labels = (
        "Panoramica",
        "Regia Operativa",
        "Ricerca Studio",
        "Recenti",
        "Calendario",
        "Nuovo Appuntamento",
        "Timesheet",
        "Tutti i Fascicoli",
        "Nuovo Fascicolo",
        "Archivio",
        "Clienti e Anagrafiche",
        "Nuovo Cliente",
        "Cartelle Condivise",
        "Soggetti e Parti",
        "Nuovo Soggetto",
        "Email PEC",
        "Email ordinaria",
        "PEC",
        "Messaggi",
        "Nuovo SMS/WA",
        "Scadenziario",
        "Nuova Scadenza",
        "Preparazione Udienza Guidata",
        "Controlli Atti",
        "Centro Servizi Telematici",
        "PolisWeb / PST",
        "PDP Penale",
        "PAT Amministrativo",
        "PTT Tributario",
        "Tribunali / PEC",
        "Checklist deposito",
        "Guida firma digitale",
        "Parcelle e Fatture",
        "Preventivi e Incarichi",
        "Compensi Forensi",
        "Editor professionale",
        "Redazione Atti",
        "Statistiche",
        "Ricerca Legale",
        "Archivio Giurisprudenza",
        "Strumenti Forensi",
        "Strumenti Operativi",
        "Sito Studio",
        "Notifiche",
        "Pagamenti",
        "Backup",
        "Impostazioni Studio",
        "Sincronizzazione Calendari",
        "Amministrazione",
        "Importa pratiche da Studio Telematico",
        "Utenti",
        "Profili e Permessi",
        "Registro Attività",
        "Database",
        "Registro GDPR",
    )
    for label in expected_visible_labels:
        assert label in app_source or label in studio_source, label
    assert "2026/004 - N.RG" not in app_source

    app = _app(tmp_path)
    _crea_operatore(app)
    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Matrice", cognome="React")
    soggetto = GestioneSoggetti(app.config["SOGGETTI_DB"], app.config["SOGGETTI_PARTI_DB"]).crea(
        TipoSoggetto.PERSONA_FISICA,
        nome="Parte",
        cognome="Verificata",
    )
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Matrice React completa",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="139",
        anno_rg=2023,
    )
    scadenza = GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"]).nuova(
        "Deposito memoria",
        TipoTermine.DEPOSITO_MEMORIA,
        date.today().isoformat(),
        id_fascicolo=fascicolo.id,
    )

    first_block_routes = {
        "Panoramica": "/",
        "Regia Operativa": "/workspace-intelligente",
        "Ricerca Studio": "/global-search",
        "Recenti": f"/fascicoli/{fascicolo.id}",
        "Calendario": "/agenda",
        "Nuovo Appuntamento": "/agenda/nuovo",
        "Timesheet": "/timesheet",
        "Tutti i Fascicoli": "/fascicoli",
        "Nuovo Fascicolo": "/fascicoli/nuovo",
        "Archivio": "/fascicoli/archivio",
        "Clienti e Anagrafiche": "/clienti",
        "Nuovo Cliente": "/clienti/nuovo",
        "Cartelle Condivise": "/cartelle-condivise",
        "Soggetti e Parti": "/soggetti",
        "Nuovo Soggetto": "/soggetti/nuovo",
        "Email PEC": "/email/",
        "Email ordinaria": "/email-ordinaria/",
        "Messaggi": "/messaggi",
        "Nuovo SMS/WA": "/messaggi/nuovo",
        "Scadenziario": "/scadenziario",
        "Nuova Scadenza": "/scadenziario/nuova",
        "Preparazione Udienza Guidata": "/wizard-pro/",
        "Dettaglio Cliente": f"/clienti/{cliente.id}/cartella",
        "Dettaglio Soggetto": f"/soggetti/{soggetto.id}",
        "Dettaglio Scadenza": f"/scadenziario/{scadenza.id}",
        "Modifica Scadenza": f"/scadenziario/{scadenza.id}/modifica",
    }
    telematico_routes = {
        "Servizi Telematici": "/telematico",
        "Centro Servizi Telematici": "/telematico",
        "PolisWeb / PST": "/polisWeb",
        "PDP Penale": "/pdp",
        "PAT Amministrativo": "/pat",
        "PTT Tributario": "/sigit",
        "Tribunali / PEC": "/tribunali",
        "Guida firma digitale": "/guida/firma-digitale",
    }
    react_studio_routes = {
        "Studio": "/studio",
        "Parcelle e Fatture": "/fatturazione",
        "Preventivi e Incarichi": "/preventivi",
        "Compensi Forensi": "/compensi-forensi",
        "Documenti": "/documenti",
        "Editor professionale": "/editor-professionale",
        "Redazione Atti": "/redazione-atti",
        "Template Atti": "/template-atti",
        "Catalogo Template": "/template-atti/catalogo",
        "Statistiche": "/statistiche",
        "Ricerca Legale": "/ricerca-legale",
        "Archivio Giurisprudenza": "/giurisprudenza",
        "Legal Intelligence": "/legal-intelligence",
        "Controlli Atti": "/deposito/checklist",
        "Strumenti Forensi": "/strumenti-legali/",
        "Strumenti Operativi": "/strumenti-operativi",
        "Amministrazione": "/amministrazione",
        "Importa pratiche da Studio Telematico": "/importa-pratiche-studio-telematico",
        "Incassi e Pagamenti": "/incassi-pagamenti",
        "Pagamenti": "/impostazioni?tab=pagamenti",
        "Canali SdI": "/impostazioni/sdi",
        "Notifiche": "/impostazioni?tab=notifiche",
        "Backup": "/backup",
        "Sincronizzazione Calendari": "/impostazioni/calendario",
        "Sito Studio": "/sito-studio/",
        "Builder Sito Studio": "/sito-studio/builder",
        "Redazione AI Sito Studio": "/sito-studio/redazione-ai",
        "Impostazioni Studio": "/impostazioni-studio",
        "Utenti": "/utenti",
        "Profili e Permessi": "/profili",
        "Registro Attività": "/registro-attivita",
    }
    with app.test_client() as client:
        _login(client)
        for label, path in first_block_routes.items():
            _assert_react_shell(client, label, path)

        _assert_react_shell(client, "Registro GDPR", "/privacy/registro")
        _assert_react_shell(client, "Nuovo trattamento GDPR", "/privacy/registro/nuovo")
        _assert_react_shell(client, "Alias Registro GDPR", "/registro-gdpr")
        _assert_react_shell(client, "Database", "/admin/database")

        for label, path in react_studio_routes.items():
            _assert_react_shell(client, label, path)

        for label, path in telematico_routes.items():
            _assert_react_shell(client, label, path)

        response = client.get("/sigp/")
        assert response.status_code in {302, 303}, "SIGP redirect"
        assert response.headers["Location"].endswith("/portali/pst/acquisizione")

        for label, path in {
            "Panoramica": "/api/v1/ui/dashboard",
            "Regia Operativa": "/api/v1/ui/dashboard?refresh=1",
            "Agenda": "/api/v1/ui/agenda",
            "Fascicoli": "/api/v1/ui/fascicoli",
            "Nuovo Fascicolo": "/api/v1/ui/fascicoli/nuovo",
            "Archivio Fascicoli": "/api/v1/ui/fascicoli/archivio",
            "Clienti": "/api/v1/ui/clienti",
            "Nuovo Cliente": "/api/v1/ui/clienti/nuovo",
            "Cartella Cliente": f"/api/v1/ui/clienti/{cliente.id}/cartella",
            "Soggetti": "/api/v1/ui/soggetti",
            "Email PEC": "/api/v1/ui/email",
            "Email ordinaria": "/api/v1/ui/email-ordinaria",
            "Messaggi": "/api/v1/ui/messaggi",
            "Nuovo SMS/WA": "/api/v1/ui/messaggi/nuovo",
            "Scadenziario": "/api/v1/ui/scadenziario",
            "Nuova Scadenza": "/api/v1/ui/scadenziario/nuova",
            "Builder Sito Studio": "/api/v1/ui/sito-studio/builder",
            "Redazione AI Sito Studio": "/api/v1/ui/sito-studio/redazione-ai",
            "Preparazione Udienza Guidata": "/api/v1/ui/wizard-pro",
            "Controlli Atti": "/api/v1/ui/telematico/surface/checklist",
            "Centro Servizi Telematici": "/api/v1/ui/telematico",
            "PolisWeb / PST": "/api/v1/ui/telematico/surface/polisweb",
            "PDP Penale": "/api/v1/ui/telematico/surface/pdp",
            "PAT Amministrativo": "/api/v1/ui/telematico/surface/pat",
            "PTT Tributario": "/api/v1/ui/telematico/surface/ptt",
            "Tribunali / PEC": "/api/v1/ui/telematico/surface/tribunali",
            "Guida firma digitale": "/api/v1/ui/telematico/surface/firma",
            "Registro GDPR": "/api/v1/ui/privacy/registro",
            "Database": "/api/v1/ui/admin/database",
            "Importa pratiche da Studio Telematico": "/api/v1/ui/import/quickorganizer",
            "Ricerca Studio": "/api/global-search?q=matrice&limit=5",
        }.items():
            _assert_payload_operativo(client, label, path, require_links=label != "Ricerca Studio")

        for module_id in (
            "studio",
            "fatturazione",
            "preventivi",
            "compensi-forensi",
            "documenti",
            "redazione-atti",
            "statistiche",
            "ricerca-legale",
            "giurisprudenza",
            "strumenti-forensi",
            "strumenti-operativi",
            "sito-studio",
            "notifiche-whatsapp",
            "incassi-pagamenti",
            "backup",
            "impostazioni-studio",
            "sincronizzazione-calendari",
            "amministrazione",
            "utenti",
            "profili",
            "registro-attivita",
            "database",
            "gdpr",
        ):
            payload = _assert_payload_operativo(client, module_id, f"/api/v1/ui/studio-modules/{module_id}")
            assert payload.get("operations"), module_id


def test_react_messaggi_bridge_usa_repository_reali(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Marco",
        cognome="Moscato",
        codice_fiscale="MSCMRC75E26L063G",
    )
    cliente_repo.aggiorna_recapiti(cliente.id, email="marco@example.it", cellulare="+393331234567")
    messaggi = GestioneMessaggi(ConfigMessaggistica(), db_path=app.config["MESSAGGI_DB"])
    msg = Messaggio(
        id="msg-react-1",
        id_cliente=cliente.id,
        canale=CanaleMsggio.WHATSAPP,
        stato=StatoMessaggio.IN_CODA,
        nome_destinatario=cliente.nome_completo,
        telefono_destinatario="+393331234567",
        corpo="Promemoria documenti",
        sid_esterno="https://wa.me/393331234567?text=Promemoria",
        creato_il=datetime.now().isoformat(timespec="seconds"),
    )
    messaggi._messaggi[msg.id] = msg
    messaggi._salva()

    list_response = client.get("/api/v1/ui/messaggi", headers={"X-API-Key": "react-test-key"})
    new_response = client.get(
        "/api/v1/ui/messaggi/nuovo",
        query_string={"id_cliente": cliente.id, "canale": "WHATSAPP"},
        headers={"X-API-Key": "react-test-key"},
    )
    list_payload = list_response.get_json()
    new_payload = new_response.get_json()

    assert list_response.status_code == 200
    assert new_response.status_code == 200
    assert list_payload["source"] == "repository_reali"
    assert list_payload["contracts"]["writes"] == "operational_routes"
    assert list_payload["summary"]["total"] == 1
    assert list_payload["summary"]["manualWhatsapp"] == 1
    assert list_payload["items"][0]["channel"] == "WHATSAPP"
    assert list_payload["items"][0]["clientLabel"] == "Moscato Marco"
    from urllib.parse import urlparse

    whatsapp_link = urlparse(list_payload["items"][0]["whatsappLink"])
    assert whatsapp_link.scheme == "https"
    assert whatsapp_link.netloc == "wa.me"
    assert whatsapp_link.path == "/393331234567"
    assert new_payload["contracts"]["writes"] == "operational_routes"
    assert new_payload["query"]["channel"] == "WHATSAPP"
    assert new_payload["clientOptions"][0]["phone"] == "+393331234567"
    assert new_payload["actions"]["sendEndpoint"] == "/messaggi/nuovo"


def test_react_dashboard_usa_bridge_reale_senza_mock(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/dashboard", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] in {"repository_reali", "errore_controllato"}
    assert "stats" in payload
    assert set(payload["stats"]) == {
        "todayAppointments",
        "urgentDeadlines",
        "openMatters",
        "unpaidAmount",
        "documentsToReview",
        "urgentActions",
        "pecUnread",
        "clientMessages",
        "expiringQuotes",
        "missingAssignments",
    }
    assert "fascicoli" in payload
    assert payload["contracts"]["mock_fallback"] is False
    for key in (
        "pec",
        "emails",
        "client_messages",
        "agenda",
        "today_operations",
        "incomplete_registry",
        "missing_engagements",
        "high_priority_matters",
        "deadline_distribution",
        "economic",
        "lex_suggestions",
    ):
        assert key in payload


def test_react_dashboard_cache_breve_e_email_recenti_ordinarie_separate_da_pec(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    GestioneEmailRicevute(app.config["EMAIL_CASELLA_DB"]).aggiungi(
        EmailRicevuta(
            id="pec-dashboard",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@giustiziapec.it",
            mittente_nome="Cancelleria PEC",
            oggetto="PEC da mostrare solo nella card PEC",
            data=datetime.now().isoformat(timespec="seconds"),
            stato_pct="ACCETTATO_PEC",
        )
    )
    GestioneEmailRicevute(app.config["EMAIL_ORDINARIA_DB"]).aggiungi(
        EmailRicevuta(
            id="mail-ordinaria-dashboard",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cliente@example.it",
            mittente_nome="Cliente ordinario",
            oggetto="Email ordinaria da mostrare in Panoramica",
            data=datetime.now().isoformat(timespec="seconds"),
        )
    )

    first = client.get(
        "/api/v1/ui/dashboard",
        query_string={"refresh": "1"},
        headers={"X-API-Key": "react-test-key"},
    )
    second = client.get("/api/v1/ui/dashboard", headers={"X-API-Key": "react-test-key"})
    refreshed = client.get(
        "/api/v1/ui/dashboard",
        query_string={"refresh": "1"},
        headers={"X-API-Key": "react-test-key"},
    )

    payload = first.get_json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert refreshed.status_code == 200
    assert first.headers["X-IUSENTRA-Cache"] == "MISS"
    assert second.headers["X-IUSENTRA-Cache"] == "HIT"
    assert refreshed.headers["X-IUSENTRA-Cache"] == "MISS"
    assert payload["cache"] == {"hit": False, "ttl_seconds": 60}
    assert payload["pec"][0]["id"] == "pec-dashboard"
    assert payload["emails"][0]["id"] == "mail-ordinaria-dashboard"
    assert payload["emails"][0]["href"] == "/email-ordinaria/"
    assert payload["contracts"]["ordinary_email_recent_enabled"] is True
    assert payload["contracts"]["pec_and_ordinary_email_separated"] is True


def test_react_agenda_bridge_usa_agenda_e_scadenziario_reali(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    today = date.today()

    GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
    )
    Agenda(db_path=app.config["AGENDA_DB"]).aggiungi(
        "Udienza civile",
        TipoAppuntamento.UDIENZA,
        datetime.combine(today, datetime.min.time()).replace(hour=10).isoformat(timespec="minutes"),
        luogo="Aula 1",
        cliente="Mario Rossi",
        procedimento=f"RG 123/{today.year}",
        tribunale="Tribunale di Milano",
    )
    scadenziario = GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"])
    scadenziario.nuova(
        "Deposito memoria",
        TipoTermine.DEPOSITO_MEMORIA,
        today.isoformat(),
        id_fascicolo="fasc-test",
    )
    linked_deadline = scadenziario.nuova(
        "Classifica PEC e conferma adempimenti",
        TipoTermine.DEPOSITO_MEMORIA,
        today.isoformat(),
        id_fascicolo="fasc-pec",
    )
    Agenda(db_path=app.config["AGENDA_DB"]).aggiungi(
        "Presidio PEC - Presidio anomalie PEC: POSTA CERTIFICATA: COMUNICAZIONE 3950/2026/LAV",
        TipoAppuntamento.UDIENZA,
        datetime.combine(today, datetime.min.time()).replace(hour=11).isoformat(timespec="minutes"),
        durata_minuti=30,
        cliente="Mario Rossi",
        procedimento=f"RG 3950/{today.year}",
        tribunale="Tribunale di Milano",
        note=(
            f"Scadenza: {linked_deadline.id}\n"
            "Oggetto: FISSAZIONE UDIENZA DI DISCUSSIONE. "
            "Descrizione: FISSATA UDIENZA DI DISCUSSIONE con strumenti audiovisivi."
        ),
    )

    response = client.get(
        "/api/v1/ui/agenda",
        query_string={"from": today.isoformat(), "to": today.isoformat()},
        headers={"X-API-Key": "react-test-key"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is True
    assert {item["source"] for item in payload["events"]} == {"agenda", "scadenziario"}
    assert any(item["title"] == "Udienza civile" for item in payload["events"])
    assert any(item["title"] == "Deposito memoria" for item in payload["events"])
    pec_event = next(item for item in payload["events"] if str(item["title"]).startswith("Presidio PEC"))
    assert pec_event["legalLabel"] == "Fissazione udienza"
    assert pec_event["displayTitle"] == f"Mario Rossi · RG 3950/{today.year}"
    assert "Presidio PEC" not in pec_event["displayTitle"]
    assert any(line.startswith("Oggetto:") for line in pec_event["detailLines"])
    visible = " ".join(
        str(pec_event.get(key) or "")
        for key in ("displayTitle", "subtitle", "notes", "originTitle", "detailTitle")
    )
    visible = " ".join([visible, *pec_event["detailLines"]])
    for token in ("Presidio PEC", "PEC_AUDIT", "pipeline", "audit-grade", "payload", "runtime", "backend", "frontend", "legacy", "json_api"):
        assert token.lower() not in visible.lower()
    assert not any(item["id"] == f"scadenza-{linked_deadline.id}" for item in payload["events"])


def test_react_agenda_bridge_traduce_pec_udienza_in_linguaggio_professionale(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    hearing_day = date(2026, 7, 9)

    appointment = Agenda(db_path=app.config["AGENDA_DB"]).aggiungi(
        "Presidio PEC - Udienza da PEC: POSTA CERTIFICATA: COMUNICAZIONE 274/2026/CC",
        TipoAppuntamento.UDIENZA,
        datetime.combine(hearing_day, datetime.min.time()).replace(hour=9).isoformat(timespec="minutes"),
        durata_minuti=30,
        tribunale="Tribunale di Palmi",
        note=(
            "Data processuale futura letta da corpo PEC: AZZARO FILIPPO "
            "Oggetto: CONFERMA UDIENZA EX ART. 171 BIS 3 c. CPC "
            "Descrizione: CONFERMATA UDIENZA EX ART. 171 BIS 3 c. CPC AL 09/07/2026 09:30 "
            "Note: Notificato alla PEC / in cancelleria."
        ),
    )

    response = client.get(
        "/api/v1/ui/agenda",
        query_string={"from": hearing_day.isoformat(), "to": hearing_day.isoformat(), "selected_id": appointment.id},
        headers={"X-API-Key": "react-test-key"},
    )
    payload = response.get_json()
    event = next(item for item in payload["events"] if item["id"] == appointment.id)
    visible = " ".join(
        str(event.get(key) or "")
        for key in ("displayTitle", "subtitle", "notes", "originTitle", "detailTitle", "timeLabel")
    )
    visible = " ".join([visible, *event["detailLines"]])

    assert response.status_code == 200
    assert event["matter"] == "RG 274/2026"
    assert event["client"] == "AZZARO FILIPPO"
    assert event["displayTitle"] == "AZZARO FILIPPO · RG 274/2026"
    assert event["originTitle"] == "Udienza da comunicazione di cancelleria - RG 274/2026"
    assert event["timeLabel"] == "09:30"
    assert event["start"].startswith("2026-07-09T09:30")
    for token in ("POSTA CERTIFICATA", "Data processuale futura", "Presidio PEC", "PEC_AUDIT", "pipeline", "payload", "runtime", "backend", "frontend", "legacy", "json_api"):
        assert token.lower() not in visible.lower()


def test_react_dashboard_legge_repository_operativi(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    today = date.today()

    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi")

    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Recupero crediti",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="123",
        anno_rg=today.year,
    )

    scadenziario = GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"])
    scadenza = scadenziario.nuova(
        "Deposito memoria",
        TipoTermine.DEPOSITO_MEMORIA,
        today.isoformat(),
        id_fascicolo=fascicolo.id,
    )
    scadenziario.aggiorna(scadenza.id, priorita=PrioritaTermine.ALTA)

    Agenda(db_path=app.config["AGENDA_DB"]).aggiungi(
        "Udienza civile",
        TipoAppuntamento.UDIENZA,
        datetime.combine(today, datetime.min.time()).replace(hour=10).isoformat(timespec="minutes"),
        luogo="Aula 1",
        cliente=cliente.nome_completo,
        procedimento=f"RG 123/{today.year}",
        tribunale="Tribunale di Milano",
    )

    GestioneEmailRicevute(app.config["EMAIL_CASELLA_DB"]).aggiungi(
        EmailRicevuta(
            id="pec-test",
            cartella=CartellaEmail.INBOX,
            stato=StatoEmail.NON_LETTA,
            mittente="cancelleria@pec.giustizia.it",
            mittente_nome="Tribunale di Milano",
            oggetto="Esito deposito telematico",
            data=datetime.now().isoformat(timespec="seconds"),
            stato_pct="ACCETTATO_PEC",
        )
    )

    messaggi = GestioneMessaggi(ConfigMessaggistica(), db_path=app.config["MESSAGGI_DB"])
    msg = Messaggio(
        id="sms-test",
        canale=CanaleMsggio.SMS,
        stato=StatoMessaggio.IN_CODA,
        nome_destinatario=cliente.nome_completo,
        telefono_destinatario="+3900000000",
        corpo="Promemoria udienza",
        creato_il=datetime.now().isoformat(timespec="seconds"),
    )
    messaggi._messaggi[msg.id] = msg
    messaggi._salva()

    preventivi = GestionePreventivi(app.config["PREVENTIVI_DB"])
    preventivo = preventivi.crea_preventivo(
        id_cliente=cliente.id,
        oggetto="Recupero crediti",
        voci=[VocePreventivo("Compenso", 1000.0)],
        data_scadenza=(today + timedelta(days=2)).isoformat(),
    )
    preventivi.cambia_stato_preventivo(preventivo.id, StatoPreventivo.ACCETTATO)

    response = client.get("/api/v1/ui/dashboard", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["stats"]["todayAppointments"] == 1
    assert payload["stats"]["pecUnread"] == 1
    assert payload["stats"]["clientMessages"] == 1
    assert payload["stats"]["missingAssignments"] == 1
    assert payload["pec"][0]["title"] == "Tribunale di Milano"
    assert payload["client_messages"][0]["title"] == "Rossi Mario"
    assert payload["agenda"][0]["title"] == "Udienza civile"
    assert payload["missing_engagements"][0]["title"] == "Rossi Mario"
    assert payload["high_priority_matters"][0]["title"].startswith(f"RG 123/{today.year}")
def test_react_fascicoli_page_collegata_nav_api_e_lex():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    floating_lex = Path("frontend/src/components/FloatingLex.tsx").read_text(encoding="utf-8")

    assert "/fascicoli" in app_source
    assert "isFascicoliPage?<FascicoliPage" in app_source
    assert 'href="/fascicoli"><BriefcaseBusiness size={18}/><span>Fascicoli</span>' in app_source
    assert "getFascicoliPage" in data_source
    assert "/api/v1/ui/fascicoli" in data_source
    assert "FascicoliPage" in page_source
    assert "rawPath.startsWith('/app-v2/fascicoli')" in page_source
    assert "FloatingLex" in page_source
    assert "context=\"fascicoli\"" in page_source
    assert ("/lex" + "?context=fascicolo") not in page_source
    assert ("/lex" + "?context=fascicoli") not in page_source
    assert "IUSENTRA_LEX_CONTEXT" in floating_lex
    assert "iusentra:lex-context" in floating_lex
    assert "return null" in floating_lex
    assert ".iu-fascicoli-page" in css
    assert "@media(max-width:760px)" in css


def test_react_fascicoli_usa_preset_grafico_globale():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    main_source = Path("frontend/src/main.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    preset = Path("frontend/src/components/iusentra/IusentraPreset.tsx").read_text(encoding="utf-8")
    design_css = Path("frontend/src/styles/iusentra-design-system.css").read_text(encoding="utf-8")
    docs = Path("docs/UI_PRESET_IUSENTRA.md").read_text(encoding="utf-8")
    section_header = Path("frontend/src/components/iusentra/IusSectionHeader.tsx").read_text(encoding="utf-8")
    visual_audit = Path("scripts/react-migration/visual-load-audit.mjs").read_text(encoding="utf-8")

    for token in (
        "IusentraPageShell",
        "IusentraMainArea",
        "IusentraMainSurface",
        "IusentraSupportRail",
        "IusentraPanelCard",
        "IusentraDataSurface",
        "IusentraFiltersBar",
        "IusentraContextFilters",
        "IusentraPaginationBar",
        "IusentraActionCard",
        "IusentraEmptyState",
        "IusentraRoutePresetFrame",
    ):
        assert token in preset
        assert token in docs

    assert "ResizeObserver" in preset
    assert "PRESET_ROUTE_LAYOUT_SELECTORS" in preset
    assert "IUSENTRA_PAGE_SEQUENCE" in preset
    assert "IUSENTRA_PAGE_SEQUENCE_VERSION" in preset
    assert "IUSENTRA_SEQUENCE_ROOT_SELECTORS" in preset
    assert "IUSENTRA_ROUTE_PRESET_RUNTIME_CSS" in preset
    assert "data-iusentra-runtime-preset" in preset
    assert "'main[class*=\"-page\"]'" in preset
    assert "'.iusentra-main-area'" in preset
    assert "classifySequenceSlot" in preset
    assert "applyRouteSequencePreset" in preset
    assert "iusentraSequenceManaged" in preset
    assert "applySequencePart" in preset
    assert "classifySequenceSlot(child) ?? 'main-content'" in preset
    assert "/(?:tabs|tablist|switcher)$/" in preset
    assert "/(?:note|summary)$/" in preset
    assert "applyRouteSequencePreset(root)" in preset
    for sequence_slot, sequence_label in (
        ("page-header", "Header pagina"),
        ("operational-subtitle", "Sottotitolo operativo"),
        ("primary-actions", "Azioni principali"),
        ("filters", "Filtri"),
        ("context-filters", "Contesto filtri / riepilogo"),
        ("main-content", "Contenuto principale"),
        ("pagination-footer", "Paginazione / footer"),
        ("support-sidebar", "Sidebar di supporto"),
    ):
        assert f"'{sequence_slot}'" in preset
        assert f'data-iusentra-sequence-slot="{sequence_slot}"' in design_css
        assert sequence_label in docs
    assert "'data-iusentra-sequence-slot': 'page-header'" in section_header
    assert "'data-iusentra-sequence-part': 'page-header'" in section_header
    assert "'data-iusentra-sequence-slot': 'operational-subtitle'" in section_header
    assert "'data-iusentra-sequence-part': 'operational-subtitle'" in section_header
    assert "'data-iusentra-sequence-slot': 'primary-actions'" in section_header
    assert "'data-iusentra-sequence-part': 'primary-actions'" in section_header
    assert "{...headerSequenceProps}" in section_header
    assert "{...descriptionSequenceProps}" in section_header
    assert "{...actionsSequenceProps}" in section_header
    for route_layout in (
        ".iu-ag-layout",
        ".iu-cli-layout",
        ".iu-sogg-layout",
        ".iu-mail-layout",
        ".iu-msg-layout",
        ".iu-scad-layout",
        ".iu-sm-layout",
        ".iu-tel-surface-grid",
        ".iu-tel-tribunali-workspace",
        ".iu-template-compiler-layout",
        ".iu-pwiz-layout",
        ".iu-db-layout",
    ):
        assert route_layout in preset
    assert "--iusentra-support-rail-min-height" in preset
    assert "--iusentra-route-rail-height" in preset
    assert "--iusentra-support-rail-width: 420px" in design_css
    assert "grid-template-columns: minmax(0, 1fr) minmax(380px, var(--iusentra-support-rail-width))" in design_css
    assert "max-height: none;" in design_css
    assert "overflow: visible;" in design_css
    assert ".iusentra-route-preset--active .iusentra-route-grid" in design_css
    assert ".iusentra-route-preset--active .iu-content.iusentra-route-sequence" in design_css
    assert ".iusentra-route-grid > .iusentra-route-rail" in design_css
    assert ".iusentra-route-preset--active .iusentra-route-sequence > :not([data-iusentra-sequence-slot])" in design_css
    assert 'section[class*="-hero"][data-iusentra-sequence-slot="page-header"]' in design_css
    assert "sequenza_header_non_primo" in visual_audit
    assert "builder_preset_attivo" in visual_audit
    assert "dettaglio_fascicolo_preset_attivo" in visual_audit
    assert "support_rail_card_troppo_stretta" in visual_audit
    assert "agenda_settimana_incompleta" in visual_audit
    assert "agenda_supporto_non_verticale" in visual_audit
    assert "email_preview_troppo_stretta" in visual_audit
    assert "header_preset_scuro" in visual_audit
    assert "['Documenti', '/documenti']" in visual_audit
    assert "['Tribunali / PEC', '/tribunali']" in visual_audit
    assert "['Sito Studio Builder', '/sito-studio/builder']" in visual_audit
    assert "['Dettaglio Fascicolo DC5BF1DB', '/fascicoli/DC5BF1DB']" in visual_audit
    assert "name: 'tablet', width: 1024" in visual_audit
    for order in ("order: 10", "order: 20", "order: 30", "order: 40", "order: 50", "order: 60", "order: 70", "order: 80"):
        assert order in design_css
    assert "margin-top: auto" in design_css
    assert "const isFascicoloDetailViewPage = /^\\/fascicoli\\/(?!nuovo$|archivio$|importa$)[^/]+$/.test(routeKey)" in app_source
    assert "const isPresetExcludedPage = isSitoStudioBuilderPage || isFascicoloDetailViewPage" in app_source
    assert "isPresetExcludedPage?'excluded':'active'" in app_source
    assert "IusentraRoutePresetFrame routeKey={routeKey} enabled={!isPresetExcludedPage}" in app_source
    assert "import './index.css'\nimport './styles/iusentra-design-system.css'" in main_source
    assert "iusentra-preset-active" in app_source
    assert "iusentra-preset-excluded" in app_source

    for token in (
        "IusentraPageShell",
        "IusentraMainArea",
        "IusentraMainSurface",
        "IusentraSupportRail",
        "IusentraDataSurface",
        "IusentraFiltersBar",
        "IusentraContextFilters",
    ):
        assert token in page_source
    assert "footer={paginationControls}" in page_source
    assert "className=\"iu-fas-page-size\"" in page_source
    assert "iu-fas-context-summary" in page_source
    assert ".iu-fas-layout.iusentra-main-area" in css
    assert ".iu-fas-insights.iusentra-support-rail" in css
    assert ".iu-fas-table-card.iusentra-data-surface" in css
    assert ".iu-fas-advanced.is-compact" in css
    assert "grid-template-columns:minmax(0,1fr) minmax(340px,360px)" in css


def test_react_fascicoli_bridge_usa_repository_reali(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    today = date.today()

    cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Marco",
        cognome="Moscato",
    )
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Appello civile",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        controparte="Zurich Ass.ni",
        tribunale="Corte d'Appello di Milano",
        numero_rg="001",
        anno_rg=today.year,
    )
    fascicolo = fascicoli.aggiorna(
        fascicolo.id,
        source="PST",
        source_external_id=f"0580010:001:{today.year}:RG",
        sync_status="SINCRONIZZATO",
        source_snapshot={
            "portale": "PST",
            "external_id": f"0580010:001:{today.year}:RG",
            "numero": "001",
            "anno": today.year,
            "ufficio_nome": "Corte d'Appello di Milano",
            "ufficio_codice": "0580010",
            "procedimento": "Contenzioso civile",
            "stato": "Pendente",
            "oggetto": "Appello civile",
            "parti": ["Moscato Marco"],
            "controparti": ["Zurich Ass.ni"],
            "counts": {"parti": 2, "documenti": 3, "depositi": 1, "eventi": 2},
        },
    )
    soggetti = GestioneSoggetti(app.config["SOGGETTI_DB"], app.config["SOGGETTI_PARTI_DB"])
    controparte = soggetti.crea(
        TipoSoggetto.PERSONA_GIURIDICA,
        ragione_sociale="Zurich Ass.ni",
        partita_iva="12345678901",
    )
    soggetti.aggiungi_parte(fascicolo.id, controparte.id, RuoloSoggetto.CONTROPARTE)
    GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"]).nuova(
        "Deposito comparsa conclusionale",
        TipoTermine.DEPOSITO_MEMORIA,
        (today + timedelta(days=10)).isoformat(),
        id_fascicolo=fascicolo.id,
    )

    response = client.get("/api/v1/ui/fascicoli", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is True
    assert payload["summary"]["total"] >= 1
    assert payload["items"][0]["title"] == "Appello civile"
    assert payload["items"][0]["type"] == "civile"
    assert payload["items"][0]["client"] == "Moscato Marco"
    assert payload["items"][0]["nextDeadline"] != "n.d."
    assert payload["items"][0]["href"] == f"/fascicoli/{fascicolo.id}"
    assert payload["items"][0]["editHref"] == f"/fascicoli/{fascicolo.id}/modifica"
    assert not payload["items"][0]["href"].startswith("/app-v2/")


def test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf(tmp_path: Path, monkeypatch):
    import web.blueprints.api_v1_react as react_api_module
    from requests import Response as RequestsResponse
    from requests.cookies import RequestsCookieJar

    app = _app(tmp_path)
    _crea_operatore(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo("Pagamento contributo unificato", TipoFascicolo.CIVILE)
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method: str, url: str, **kwargs):
        calls.append((method, url, kwargs))
        response = RequestsResponse()
        response.status_code = 200
        response.url = url
        response.cookies = RequestsCookieJar()
        response.cookies.set("JSESSIONID", "pst-test")
        if url.endswith("/PST/dwr/interface/PagamentiTelematiciAjaxServices.js"):
            response.headers["Content-Type"] = "text/javascript;charset=utf-8"
            response._content = b"PagamentiTelematiciAjaxServices._path = '/PST/dwr';"
            return response
        if url.endswith("/PST/resources/static/js/pst.js"):
            response.headers["Content-Type"] = "application/javascript"
            response._content = b'window.dwr = { engine: { _execute: function(){ return "/PST/dwr/call"; } } };'
            return response
        if url.endswith("/PST/resources/ricevuta.pdf"):
            response.headers["Content-Type"] = "application/pdf"
            response.headers["Content-Disposition"] = 'inline; filename="ricevuta-pagopa.pdf"'
            response._content = b"%PDF-1.4\nricevuta pagoPA\n%%EOF"
            return response
        if url.endswith("/PST/it/pagopa_nuovarich.wp"):
            response.headers["Content-Type"] = "application/xhtml+xml; charset=utf-8"
        else:
            response.headers["Content-Type"] = "text/html; charset=utf-8"
        response._content = (
            b'<html><head><link href="/PST/resources/static/css/pst.css"></head>'
            b'<body><form method="post" action="/PST/it/pagopa_altripag.wp?action=conferma">'
            b'<input name="codice"></form>'
            b'<a href=/PST/it/pagopa_nuovarich.wp>+ Nuovo pagamento</a>'
            b'<img src=/PST/resources/cms/images/pagoPA_d0.jpg>'
            b'<a href="/PST/resources/ricevuta.pdf">Richiedi ricevuta PDF</a>'
            b'</body></html>'
        )
        return response

    monkeypatch.setattr(react_api_module.requests, "request", fake_request)

    with app.test_client() as client:
        _login(client)
        html_response = client.get(
            f"/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp?iusentra_fascicolo={fascicolo.id}"
        )
        pdf_response = client.get(
            f"/api/v1/ui/pst/pagopa-proxy/resources/ricevuta.pdf?iusentra_fascicolo={fascicolo.id}"
        )
        xhtml_response = client.get(
            f"/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp?iusentra_fascicolo={fascicolo.id}"
        )
        javascript_response = client.get(
            f"/api/v1/ui/pst/pagopa-proxy/resources/static/js/pst.js?iusentra_fascicolo={fascicolo.id}"
        )
        print_css_response = client.get(
            f"/api/v1/ui/pst/pagopa-proxy/resources/static/css/print.css?iusentra_fascicolo={fascicolo.id}"
        )
        dwr_interface_response = client.get(
            f"/api/v1/ui/pst/pagopa-proxy/dwr/interface/PagamentiTelematiciAjaxServices.js?iusentra_fascicolo={fascicolo.id}"
        )
        dwr_response = client.post(
            f"/api/v1/ui/pst/pagopa-proxy/dwr/call/plaincall/PagamentiTelematiciAjaxServices.getUfficiGiudiziari.dwr?iusentra_fascicolo={fascicolo.id}",
            data=(
                "callCount=1\n"
                f"page=%2Fapi%2Fv1%2Fui%2Fpst%2Fpagopa-proxy%2Fit%2Fpagopa_nuovarich.wp%3Fiusentra_fascicolo%3D{fascicolo.id}\n"
                "httpSessionId=\n"
            ),
            headers={
                "Content-Type": "text/plain; charset=UTF-8",
                "Referer": (
                    "http://localhost/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp"
                    f"?iusentra_fascicolo={fascicolo.id}"
                ),
            },
        )
        dwr_response_without_content_type = client.post(
            f"/api/v1/ui/pst/pagopa-proxy/dwr/call/plaincall/__System.pageLoaded.dwr?iusentra_fascicolo={fascicolo.id}",
            data=(
                "callCount=1\n"
                f"page=%2Fapi%2Fv1%2Fui%2Fpst%2Fpagopa-proxy%2Fit%2Fpagopa_altripag.wp%3Fiusentra_fascicolo%3D{fascicolo.id}\n"
                "httpSessionId=\n"
            ),
            headers={
                "Referer": (
                    "http://localhost/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp"
                    f"?iusentra_fascicolo={fascicolo.id}"
                )
            },
        )
        absolute_escape_response = client.get(
            f"/PST/it/pagopa_nuovarich.wp?iusentra_fascicolo={fascicolo.id}",
            follow_redirects=False,
        )

    html = html_response.get_data(as_text=True)
    assert html_response.status_code == 200
    assert html_response.headers.get("X-Frame-Options", "").upper() != "DENY"
    assert f"/api/v1/ui/pst/pagopa-proxy/resources/static/css/pst.css?iusentra_fascicolo={fascicolo.id}" in html
    assert (
        f"/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp?action=conferma&iusentra_fascicolo={fascicolo.id}"
        in html
    )
    assert f"/api/v1/ui/pst/pagopa-proxy/resources/ricevuta.pdf?iusentra_fascicolo={fascicolo.id}" in html
    assert f"/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp?iusentra_fascicolo={fascicolo.id}" in html
    assert f"/api/v1/ui/pst/pagopa-proxy/resources/cms/images/pagoPA_d0.jpg?iusentra_fascicolo={fascicolo.id}" in html
    assert "function proxiedUrl(raw)" in html
    assert "attributeFilter: ['href', 'src', 'action']" in html
    assert "proxyPrefix + proxyPath + absolute.search" in html
    assert "'unsafe-eval'" in html_response.headers["Content-Security-Policy"]
    assert pdf_response.status_code == 200
    assert pdf_response.content_type == "application/pdf"
    assert pdf_response.headers["X-IUSENTRA-Fascicolo"] == fascicolo.id
    assert pdf_response.headers["X-IUSENTRA-Fascicolo-Documento"]
    assert xhtml_response.status_code == 200
    assert xhtml_response.content_type.startswith("text/html")
    assert (
        f"/api/v1/ui/pst/pagopa-proxy/resources/static/css/pst.css?iusentra_fascicolo={fascicolo.id}"
        in xhtml_response.get_data(as_text=True)
    )
    assert javascript_response.status_code == 200
    assert javascript_response.content_type == "application/javascript"
    assert 'return "/PST/dwr/call"' in javascript_response.get_data(as_text=True)
    assert "/api/v1/ui/pst/pagopa-proxy/dwr/call" not in javascript_response.get_data(as_text=True)
    assert print_css_response.status_code == 200
    assert print_css_response.content_type == "text/css; charset=utf-8"
    assert "Foglio di stampa PST" in print_css_response.get_data(as_text=True)
    assert "<html" not in print_css_response.get_data(as_text=True).lower()
    assert dwr_interface_response.status_code == 200
    assert (
        "PagamentiTelematiciAjaxServices._path = '/api/v1/ui/pst/pagopa-proxy/dwr';"
        in dwr_interface_response.get_data(as_text=True)
    )
    assert dwr_response.status_code == 200
    assert dwr_response_without_content_type.status_code == 200
    assert absolute_escape_response.status_code == 302
    assert absolute_escape_response.headers["Location"].endswith(
        f"/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp?iusentra_fascicolo={fascicolo.id}"
    )
    assert calls[0][1] == "https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp"
    assert calls[1][1] == "https://servizipst.giustizia.it/PST/resources/ricevuta.pdf"
    dwr_call = next(call for call in calls if call[1].endswith("PagamentiTelematiciAjaxServices.getUfficiGiudiziari.dwr"))
    assert dwr_call[1] == (
        "https://servizipst.giustizia.it/PST/dwr/call/plaincall/"
        "PagamentiTelematiciAjaxServices.getUfficiGiudiziari.dwr"
    )
    assert dwr_call[2]["headers"]["Referer"] == "https://servizipst.giustizia.it/PST/it/pagopa_nuovarich.wp"
    assert dwr_call[2]["headers"]["Origin"] == "https://servizipst.giustizia.it"
    assert dwr_call[2]["headers"]["Content-Type"] == "text/plain; charset=UTF-8"
    assert "page=%2FPST%2Fit%2Fpagopa_nuovarich.wp" in dwr_call[2]["data"].decode("utf-8")
    assert "httpSessionId=pst-test" in dwr_call[2]["data"].decode("utf-8")
    page_loaded_call = next(call for call in calls if call[1].endswith("__System.pageLoaded.dwr"))
    assert page_loaded_call[2]["headers"]["Content-Type"] == "text/plain"
    assert "page=%2FPST%2Fit%2Fpagopa_altripag.wp" in page_loaded_call[2]["data"].decode("utf-8")
    assert "httpSessionId=pst-test" in page_loaded_call[2]["data"].decode("utf-8")
    assert calls[0][2]["verify"] is not False
    assert react_api_module.PST_PAGOPA_EXTRA_CA_PATH.read_bytes() in Path(calls[0][2]["verify"]).read_bytes()
    fascicolo_aggiornato = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    ).get(fascicolo.id)
    assert fascicolo_aggiornato is not None
    ricevuta = next(doc for doc in fascicolo_aggiornato.documenti if doc.nome == "ricevuta-pagopa.pdf")
    assert ricevuta.fonte_documento == "PORTALE_TELEMATICO"
    assert ricevuta.classificazione_portale == "RICEVUTA_PAGOPA"
    assert "PagoPA" in ricevuta.tags



def test_react_fascicoli_suite_completa_route_componenti_e_lex():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    floating_lex = Path("frontend/src/components/FloatingLex.tsx").read_text(encoding="utf-8")
    bridge = Path("web/services/react_fascicoli_bridge.py").read_text(encoding="utf-8")

    assert "/fascicoli" in app_source
    assert "/fascicoli/nuovo" in app_source
    assert "/fascicoli/archivio" in app_source
    assert "isFascicoliPage?<FascicoliPage" in app_source
    for name in ("FascicoliListPage", "ArchivePage", "FascicoloFormPage", "DetailPage", "QuadroPage", "ExportPage"):
        assert name in page_source
    for endpoint in ("/api/v1/ui/fascicoli", "/api/v1/ui/fascicoli/archivio", "/api/v1/ui/fascicoli/export"):
        assert endpoint in data_source
    assert "/api/v1/ui/fascicoli/${encodeURIComponent(id)}/pagamenti/${kind}" in data_source
    assert "updateFascicoloPayment" in data_source
    assert "EconomicPaymentCell" in page_source
    assert "Stato fascicolo" in page_source
    assert "Solo controllo economico da completare" in page_source
    assert ".iu-fas-table--economic" in css
    assert ".iu-fas-economic-cell__details" in css
    for service_action in ("/documenti/carica", "/documenti/importa-portale", "/attivita/aggiungi", "/definisci", "/archivia", "/ripristina"):
        assert service_action in bridge
    assert "Vista classica" not in page_source
    assert "kind: 'quadro'" in page_source
    assert "rawPath.startsWith('/app-v2/fascicoli')" in page_source
    assert "parts[1] === 'quadro'" in page_source
    assert "quadroHref" in page_source
    assert "fascicolo-quadro" in page_source
    assert "operationalHref}/copertina" in page_source
    assert "<details ref={detailsRef} id={id} open={actualOpen}" in page_source
    assert "onToggle={(event) =>" in page_source
    assert 'className="iu-fas-detail-section" open' not in page_source
    assert "Quadro intelligente" in page_source
    assert "Quadro intelligente AI" in page_source
    assert "<a href={quadroHref}><Gauge size={15}/> Quadro completo</a>" in page_source
    assert 'className="iu-fas-ai-actions"' in page_source
    assert 'href="#uffici-competenti"' in page_source
    assert 'id="uffici-competenti" title="Uffici giudiziari per Comune"' in page_source
    assert "FascicoloUfficiCompetentiPanel" in page_source
    assert "splitOfficeComuneQuery" in page_source
    assert "normaliseStudioRuntimeResult" in page_source
    assert "/api/v1/ui/strumenti-legali/uffici_competenti" in page_source
    assert '<a href="#documenti"><FileText size={15}/> Documenti e atti</a>' in page_source
    assert 'id="documenti" title="Documenti e atti"' in page_source
    assert 'id="editor-professionale" title="Editor professionale e compilatore atti"' not in page_source
    assert "_fatturapa_item" in bridge
    assert "FatturaPA / SDI" in bridge
    assert "Agenzia Entrate" in bridge
    assert '<a href="#documenti"><FileText size={15}/> Documenti e atti</a>' in page_source
    assert "<a href={compilerHref}><ClipboardCheck size={15}/> Compilatore atti</a>" in page_source
    assert '<a href="#documenti"><BrainCircuit size={15}/> Indice Lex</a>' in page_source
    assert "editorWorkspaceHref" not in page_source
    assert "<a href={editorWorkspaceHref}><PencilLine size={15}/> Editor professionale</a>" not in page_source
    assert "<span>Analisi Lex AI</span>" not in page_source
    assert "Compilatore atti" in page_source
    assert "Editor professionale e compilatore atti" not in page_source
    assert "PdfPreviewModal" in page_source
    assert "DocumentUploadWorkspace" in page_source
    assert "classificazione_modalita" in page_source
    assert 'name="files"' in page_source
    assert "PortalImportForm" not in page_source
    assert "Importa dal portale" not in page_source
    assert "iu-fas-doc-workspace__portal" not in css
    assert "iu-fas-confirm-modal" in page_source
    assert "window.confirm" not in page_source
    assert "deleteHref" in data_source
    assert '"deleteHref": f"/fascicoli/{fid}/elimina"' in bridge
    assert 'title="Elimina fascicolo"' in page_source
    assert "handleFascicoloDeleted" in page_source
    assert "onDeleted={handleFascicoloDeleted}" in page_source
    assert "Anteprima interna" in page_source
    assert 'title="Firma digitale"' in page_source
    assert 'title="Modifica documento"' in page_source
    assert "onPreview={setPreviewDoc}" in page_source
    assert "onDone={refreshDetail}" in page_source
    assert "'X-Requested-With': 'XMLHttpRequest'" in page_source
    assert "/template-atti/catalogo?id_fascicolo=" in page_source
    assert "Dati aggiornati - ${data.source}" not in page_source
    assert 'title="Soggetti e parti"' in page_source
    assert 'title="Comunicazioni / Cancelleria"' in page_source
    assert 'title="Servizi telematici"' in page_source
    assert "FascicoloGuardrailsPanel" in page_source
    assert "data.guardrails" in page_source
    assert "Presidio apertura fascicolo" in page_source
    assert "FascicoloFormGuardrails" in data_source
    assert "guardrails: guardrails ?" in data_source
    assert "_new_fascicolo_guardrails" in bridge
    assert "_deposit_channel_for_type" in bridge
    assert "PDP_PENALE" in bridge
    assert "PAT_AMMINISTRATIVO" in bridge
    assert "PTT_TRIBUTARIO" in bridge
    assert "label=\"Attività\"" in page_source
    assert "Conformità" in page_source
    assert "fascicolo-top" in page_source
    assert "iu-fas-compliance-toggle" in page_source
    assert 'name="next"' in page_source
    assert "context=\"fascicoli\"" in page_source
    assert ("/lex" + "?context=fascicolo") not in page_source
    assert ("/lex" + "?context=fascicoli") not in page_source
    assert "IUSENTRA_LEX_CONTEXT" in floating_lex
    assert "iusentra:lex-context" in floating_lex
    assert "return null" in floating_lex
    assert ".iu-fascicoli-page" in css
    assert ".iu-fascicolo-detail-page" in css
    assert ".iu-fascicolo-form-page" in css
    assert ".iu-fas-export-page" in css
    assert ".iu-fas-back-top" in css
    assert ".iu-fas-detail-section__summary" in css
    assert ".iu-fas-smart-board" in css
    assert ".iu-fas-ai-board" in css
    assert ".iu-fas-office-lookup" in css
    assert ".iu-fas-office-window" in css
    assert ".iu-fas-office-card__contacts" in css
    assert ".iu-fas-command-bar" in css
    assert ".iu-fas-preview-modal" in css
    assert "const PAGOPA_PST_URL = 'https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp'" in page_source
    assert "const PAGOPA_PROXY_URL = '/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp'" in page_source
    assert "const PAGOPA_LOGO_URL = '/static/react/pagopa-removebg-preview.png'" in page_source
    assert "function EmbeddedRecordModal" in page_source
    assert "function RecordOverlayButton" in page_source
    assert "function PagoPaActionButton" in page_source
    assert "pagoPaEmbeddedHref" in page_source
    assert "externalHref: PAGOPA_PST_URL" in page_source
    assert "src={record.href}" in page_source
    assert "sandbox={isPagoPa ?" in page_source
    assert "allow-same-origin allow-forms allow-scripts allow-popups" in page_source
    assert "referrerPolicy={isPagoPa ? 'same-origin' : undefined}" in page_source
    assert "Visualizza cliente nel fascicolo" in page_source
    assert "Visualizza soggetti e parti nel fascicolo" in page_source
    assert "Quando richiedi la ricevuta PDF" in page_source
    assert "Apri fuori" in page_source
    assert Path("frontend/public/pagopa-removebg-preview.png").exists()
    assert ".iu-fas-pagopa-button" in css
    assert ".iu-fas-embedded-modal" in css
    assert ".iu-fas-pagopa-proxy-note" in css
    assert ".iu-fas-editor-board" in css
    assert ".iu-fas-action-stack .iu-fas-post" in css
    assert ".iu-fas-compliance-toggle" in css
    assert ".iu-fascicolo-quadro-page" in css
    assert ".iu-fas-quadro-axis" in css
    assert ".iu-fas-quadro-kpis" in css
    assert ".iu-fas-quadro-grid .iu-fas-quadro-axis#economico{order:2}" in css
    assert ".iu-fas-quadro-grid .iu-fas-quadro-axis#documenti{order:4}" in css
    assert ".iu-fas-quadro-grid .iu-fas-quadro-axis#soggetti{order:5}" in css
    assert ".iu-fas-quadro-grid .iu-fas-quadro-axis#conformita{order:8}" in css
    assert "@media(max-width:760px)" in css


def test_react_fascicoli_detail_nav_lessico_e_referente_studio_presidiati():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    base = Path("web/templates/base.html").read_text(encoding="utf-8")
    bridge = Path("web/services/react_fascicoli_bridge.py").read_text(encoding="utf-8")

    assert "Lex - Assistente Legale" not in app_source
    assert "Lex – Assistente Legale" not in base
    assert "false and g.utente_corrente" not in base
    assert "_lead_lawyer_label" in bridge
    assert "_next_hearing_value" in bridge
    assert "_closure_date_value" in bridge
    assert 'className="iu-fas-detail-section" open' not in page_source
    assert "Quadro intelligente" in page_source
    assert ".iu-fas-action-stack .iu-fas-post" in css
    assert ".iu-fas-smart-board" in css


def test_react_fascicoli_api_suite_richiede_auth(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    assert client.get("/api/v1/ui/fascicoli").status_code == 401
    assert client.get("/api/v1/ui/fascicoli/archivio").status_code == 401
    assert client.get("/api/v1/ui/fascicoli/nuovo").status_code == 401
    assert client.get("/api/v1/ui/fascicoli/export").status_code == 401
    assert client.post(
        "/api/v1/ui/fascicoli/fascicolo-demo/pagamenti/contributo_unificato",
        json={"status": "pagato"},
    ).status_code == 401


def test_react_fascicolo_documenti_ajax_non_ricarica_e_cancella_senza_confirm_nativo(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo("Opposizione decreto", TipoFascicolo.CIVILE)
    documento = fascicoli.aggiungi_documento(
        fascicolo.id,
        "bozza.txt",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"bozza documento",
    )

    headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    with app.test_client() as client:
        _login(client)
        upload = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/carica",
            data={
                "file": (io.BytesIO(b"nuovo documento"), "nuovo-documento.txt"),
                "tipo_doc": TipoDocumento.ATTO_GIUDIZIARIO.value,
                "note": "caricamento ajax",
            },
            content_type="multipart/form-data",
            headers=headers,
        )
        multi_auto = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/carica",
            data={
                "files": [
                    (io.BytesIO(b"procura alle liti"), "procura-speciale.pdf"),
                    (io.BytesIO(b"sentenza tribunale"), "sentenza-tribunale.pdf"),
                ],
                "classificazione_modalita": "auto",
            },
            content_type="multipart/form-data",
            headers=headers,
        )
        multi_manuale = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/carica",
            data={
                "files": [
                    (io.BytesIO(b"contenuto generico"), "file-generico-1.bin"),
                    (io.BytesIO(b"contenuto generico"), "file-generico-2.bin"),
                ],
                "classificazione_modalita": "manuale",
                "tipo_doc_0": TipoDocumento.MEMORIA.value,
                "tipo_doc_1": TipoDocumento.CONTRATTO.value,
            },
            content_type="multipart/form-data",
            headers=headers,
        )
        delete_doc = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{documento.id}/elimina",
            headers=headers,
        )

    assert upload.status_code == 200
    assert upload.is_json
    assert upload.get_json()["ok"] is True
    assert upload.get_json()["redirect_url"].endswith("#documenti")
    assert multi_auto.status_code == 200
    assert multi_auto.is_json
    assert len(multi_auto.get_json()["documenti_id"]) == 2
    assert multi_manuale.status_code == 200
    assert multi_manuale.is_json
    assert len(multi_manuale.get_json()["documenti_id"]) == 2
    fascicolo_aggiornato = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    ).get(fascicolo.id)
    assert fascicolo_aggiornato is not None
    docs_by_name = {doc.nome: doc for doc in fascicolo_aggiornato.documenti}
    assert docs_by_name["nuovo-documento.txt"].tipo == TipoDocumento.ATTO_GIUDIZIARIO
    assert docs_by_name["procura-speciale.pdf"].tipo == TipoDocumento.PROCURA
    assert docs_by_name["sentenza-tribunale.pdf"].tipo == TipoDocumento.SENTENZA
    assert docs_by_name["file-generico-1.bin"].tipo == TipoDocumento.MEMORIA
    assert docs_by_name["file-generico-2.bin"].tipo == TipoDocumento.CONTRATTO
    assert delete_doc.status_code == 200
    assert delete_doc.is_json
    assert delete_doc.get_json()["ok"] is True
    with app.test_client() as client:
        _login(client)
        delete_fascicolo = client.post(
            f"/fascicoli/{fascicolo.id}/elimina",
            headers=headers,
        )
    assert delete_fascicolo.status_code == 200
    assert delete_fascicolo.is_json
    assert delete_fascicolo.get_json()["ok"] is True
    assert delete_fascicolo.get_json()["redirect_url"] == "/fascicoli"


def test_react_fascicoli_api_suite_usa_repository_reali(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    today = date.today()

    cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Marco",
        cognome="Moscato",
    )
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Appello civile",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        controparte="Zurich Ass.ni",
        tribunale="Corte d'Appello di Milano",
        numero_rg="001",
        anno_rg=today.year,
    )
    fascicolo = fascicoli.aggiorna(
        fascicolo.id,
        source="PST",
        source_external_id=f"0580010:001:{today.year}:RG",
        sync_status="SINCRONIZZATO",
        source_snapshot={
            "portale": "PST",
            "external_id": f"0580010:001:{today.year}:RG",
            "numero": "001",
            "anno": today.year,
            "ufficio_nome": "Corte d'Appello di Milano",
            "ufficio_codice": "0580010",
            "procedimento": "Contenzioso civile",
            "stato": "Pendente",
            "oggetto": "Appello civile",
            "parti": ["Moscato Marco"],
            "controparti": ["Zurich Ass.ni"],
            "counts": {"parti": 2, "documenti": 3, "depositi": 1, "eventi": 2},
        },
    )
    soggetti = GestioneSoggetti(app.config["SOGGETTI_DB"], app.config["SOGGETTI_PARTI_DB"])
    controparte = soggetti.crea(
        TipoSoggetto.PERSONA_GIURIDICA,
        ragione_sociale="Zurich Ass.ni",
        partita_iva="12345678901",
    )
    soggetti.aggiungi_parte(fascicolo.id, controparte.id, RuoloSoggetto.CONTROPARTE)
    GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"]).nuova(
        "Deposito comparsa conclusionale",
        TipoTermine.DEPOSITO_MEMORIA,
        (today + timedelta(days=10)).isoformat(),
        id_fascicolo=fascicolo.id,
    )
    preventivo = GestionePreventivi(app.config["PREVENTIVI_DB"]).crea_preventivo(
        cliente.id,
        "Istanza sospensione esecuzione",
        [VocePreventivo(descrizione="Studio e deposito", importo=1000.0)],
        tipo_procedimento="Istanza di sospensione dell'esecuzione ex art. 373 c.p.c.",
        id_pratica="sospensione_esecuzione_appello",
        area_pratica="procedimenti_speciali_sommari",
        codice_oggetto_pst="014001",
    )

    list_response = client.get("/api/v1/ui/fascicoli", headers={"X-API-Key": "react-test-key"})
    detail_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}", headers={"X-API-Key": "react-test-key"})
    missing_response = client.get("/api/v1/ui/fascicoli/fascicolo-non-presente", headers={"X-API-Key": "react-test-key"})
    missing_include_all_response = client.get(
        "/api/v1/ui/fascicoli/fascicolo-non-presente?include=all",
        headers={"X-API-Key": "react-test-key"},
    )
    alias_detail_response = client.get("/api/v1/ui/fascicoli/001", headers={"X-API-Key": "react-test-key"})
    form_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/modifica", headers={"X-API-Key": "react-test-key"})
    new_form_response = client.get(
        "/api/v1/ui/fascicoli/nuovo",
        query_string={"tipo": "PENALE"},
        headers={"X-API-Key": "react-test-key"},
    )
    source_form_response = client.get(
        "/api/v1/ui/fascicoli/nuovo",
        query_string={"source_preventivo": preventivo.id},
        headers={"X-API-Key": "react-test-key"},
    )
    export_response = client.get("/api/v1/ui/fascicoli/export", headers={"X-API-Key": "react-test-key"})
    payments_only_response = client.get(
        "/api/v1/ui/fascicoli",
        query_string={"payments_only": "1"},
        headers={"X-API-Key": "react-test-key"},
    )
    payment_blank_response = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/pagamenti/contributo_unificato",
        json={
            "status": "pagato",
            "importo": "",
            "dataPagamento": "2026-06-09",
            "metodo": "F24",
            "note": "Versamento senza importo ancora indicato",
        },
        headers={"X-API-Key": "react-test-key"},
    )
    payment_negative_response = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/pagamenti/fondo_spese",
        json={"status": "pagato", "importo": "-1"},
        headers={"X-API-Key": "react-test-key"},
    )
    updated_list_response = client.get("/api/v1/ui/fascicoli", headers={"X-API-Key": "react-test-key"})

    payload = list_response.get_json()
    detail = detail_response.get_json()
    alias_detail = alias_detail_response.get_json()
    form = form_response.get_json()
    new_form = new_form_response.get_json()
    source_form = source_form_response.get_json()
    export_payload = export_response.get_json()
    payments_only_payload = payments_only_response.get_json()
    payment_blank_payload = payment_blank_response.get_json()
    payment_negative_payload = payment_negative_response.get_json()
    updated_payload = updated_list_response.get_json()

    assert list_response.status_code == 200
    assert missing_response.status_code == 404
    assert missing_response.get_json()["notFound"] is True
    assert missing_include_all_response.status_code == 200
    assert missing_include_all_response.get_json()["notFound"] is True
    assert detail_response.status_code == 200
    assert alias_detail_response.status_code == 200
    assert form_response.status_code == 200
    assert new_form_response.status_code == 200
    assert source_form_response.status_code == 200
    assert export_response.status_code == 200
    assert payments_only_response.status_code == 200
    assert payment_blank_response.status_code == 200
    assert payment_negative_response.status_code == 400
    assert updated_list_response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is True
    assert payload["summary"]["total"] >= 1
    assert any(item["title"] == "Appello civile" for item in payload["items"])
    row = next(item for item in payload["items"] if item["title"] == "Appello civile")
    assert row["href"] == f"/fascicoli/{fascicolo.id}"
    assert row["editHref"] == f"/fascicoli/{fascicolo.id}/modifica"
    assert row["deleteHref"] == f"/fascicoli/{fascicolo.id}/elimina"
    assert not row["href"].startswith("/app-v2/")
    assert row["paymentSummary"]["stato"] == "da_presidiare"
    assert row["paymentSummary"]["items"]["contributo_unificato"]["status"] == "da_registrare"
    assert row["paymentSummary"]["items"]["contributo_unificato"]["importo"] is None
    assert row["paymentSummary"]["items"]["fondo_spese"]["status"] == "da_registrare"
    assert row["paymentSummary"]["items"]["liquidazione_giudice"]["status"] == "non_previsto"
    assert row["paymentSummary"]["items"]["parcella"]["status"] == "da_emettere"
    assert any(item["id"] == fascicolo.id for item in payments_only_payload["items"])
    assert payment_blank_payload["ok"] is True
    assert payment_blank_payload["payment"]["status"] == "pagato"
    assert payment_blank_payload["payment"]["importo"] is None
    assert payment_blank_payload["payment"]["dataPagamento"] == "09/06/2026"
    assert payment_blank_payload["paymentSummary"]["items"]["contributo_unificato"]["status"] == "pagato"
    assert payment_negative_payload["errors"]["importo"] == "L'importo non può essere negativo."
    updated_row = next(item for item in updated_payload["items"] if item["id"] == fascicolo.id)
    assert updated_row["paymentSummary"]["items"]["contributo_unificato"]["status"] == "pagato"
    assert updated_row["paymentSummary"]["items"]["contributo_unificato"]["importo"] is None
    fascicolo_salvato = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    ).get(fascicolo.id)
    assert fascicolo_salvato is not None
    assert fascicolo_salvato.pagamenti["contributo_unificato"]["importo"] is None
    assert fascicolo_salvato.pagamenti["contributo_unificato"]["status"] == "pagato"
    assert detail["fascicolo"]["title"] == "Appello civile"
    assert detail["fascicolo"]["sourceSnapshot"]["portale"] == "PST"
    assert detail["fascicolo"]["sourceSnapshot"]["counts"]["documenti"] == 3
    assert any(item["label"] == "Dati letti dal portale" and "documenti 3" in item["value"] for item in detail["profile"])
    assert alias_detail["fascicolo"]["id"] == fascicolo.id
    assert detail["signature"]["visibleSignatureMode"] == "laterale"
    assert "visibleSignaturePlace" in detail["signature"]
    assert detail["signature"]["visibleSignatureDatetimeMode"] == "data_ora"
    assert any(party["name"] == "Zurich Ass.ni" and party["role"] == "Controparte" for party in detail["parties"])
    assert any(party["name"] == "Moscato Marco" and party["role"] == "Cliente / assistito" for party in detail["parties"])
    assert any(item["label"] == "Parti" and item["value"] == f"{len(detail['parties'])} soggetti" for item in detail["quality"])
    fatturapa = next(item for item in detail["economics"] if item["id"] == "fatturapa")
    assert fatturapa["value"] == "Da creare"
    assert fatturapa["href"] == f"/fatturazione/nuova?id_fascicolo={fascicolo.id}"
    assert "Agenzia Entrate" in fatturapa["note"]
    assert detail["actions"]["uploadDocument"].endswith("/documenti/carica")
    assert form["mode"] == "edit"
    assert form["detailHref"] == f"/fascicoli/{fascicolo.id}"
    assert form["backHref"] == f"/fascicoli/{fascicolo.id}"
    assert form["studio"]["leadLawyer"] == "Avv. Refactor"
    assert form["fascicolo"]["leadLawyer"] == "Avv. Refactor"
    assert form["guardrails"]["channel"] == "PCT_TELEMATICO"
    assert form["guardrails"]["requiredOpeningFields"] == ["titolo", "tipo", "oggetto", "autorità giudiziaria", "controparte"]
    assert new_form["judicialOffices"]
    assert any("Tribunale" in office["label"] for office in new_form["judicialOffices"])
    assert "subjects" in new_form
    assert new_form["guardrails"]["channel"] == "PDP_PENALE"
    assert new_form["guardrails"]["channelLabel"] == "PDP Penale"
    assert new_form["guardrails"]["warnings"][0]["code"] == "DOCUMENTI_PREDEPOSITO_DOPO_CREAZIONE"
    assert source_form["fascicolo"]["practiceId"] == "sospensione_esecuzione_appello"
    assert source_form["fascicolo"]["codiceOggettoPst"] == "014001"
    assert source_form["fascicolo"]["fonteCodiceOggetto"] == "PST_XSD"
    assert export_payload["formats"][0]["href"] == "/fascicoli/export.pdf"
    assert any(field["key"] == "contributo_unificato_stato" for field in export_payload["fields"])
    assert any(field["key"] == "totale_registrato" for field in export_payload["fields"])
    assert export_payload["presets"][-1]["href"] == "/fascicoli/archivio"


def test_react_fascicolo_import_quickorganizer_compila_dati_deposito(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Spagnolo Sara c. MIM",
        TipoFascicolo.LAVORO,
        tribunale="TRIBUNALE DI TORINO",
        numero_rg="3950",
        anno_rg=2026,
        oggetto="222050 - Retribuzione",
        source="QUICKORGANIZER",
        source_external_id="quickorganizer:306",
        source_snapshot={
            "numero_pratica": 306,
            "pratica": "Spagnolo Sara c. MIM",
            "oggetto": "222050 - Retribuzione",
        },
    )
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "20260328104059747.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-atto",
        fonte_documento="IMPORT_ESTERNO",
        nome_originale="20260328104059747.PDF",
        classificazione_portale="QuickOrganizer",
        note="Import QuickOrganizer. ",
    )
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "20260328104100604.PDF",
        TipoDocumento.SENTENZA,
        b"%PDF-provvedimento",
        fonte_documento="IMPORT_ESTERNO",
        nome_originale="20260328104100604.PDF",
        classificazione_portale="QuickOrganizer",
        note="Import QuickOrganizer. ",
    )

    response = client.get(
        f"/api/v1/ui/fascicoli/{fascicolo.id}?include=all",
        headers={"X-API-Key": "react-test-key"},
    )
    payload = response.get_json()
    profile = {item["label"]: item["value"] for item in payload["profile"]}
    documents = payload["documents"]

    assert response.status_code == 200
    assert payload["fascicolo"]["client"] == "Spagnolo Sara (da collegare in anagrafica)"
    assert profile["Cliente"] == "Spagnolo Sara (da collegare in anagrafica)"
    assert payload["fascicolo"]["codiceOggettoPst"] == "222050 - Retribuzione"
    assert profile["Codice oggetto"] == "222050 - Retribuzione"
    assert payload["regia"]["header"]["channel"] == "PCT lavoro / SICID"
    assert payload["regia"]["header"]["channelCode"] == "PCT_LAVORO"
    assert payload["regia"]["profile"]["code"] == "PROC_LAV_RETRIB_001"
    assert payload["regia"]["profile"]["needsManualConfirmation"] is False
    assert payload["regia"]["deposit"]["deliveryPolicy"]["officialChannel"] == "PCT lavoro / SICID"
    assert [doc["name"] for doc in documents[:2]] == ["Atto giudiziario", "Provvedimento - sentenza"]
    imported_documents = [doc for doc in documents if doc["id"] in {documents[0]["id"], documents[1]["id"]}]
    assert all(not doc["name"].startswith("202603") for doc in imported_documents)
    assert all(doc["source"] == "Importazione fascicolo" for doc in imported_documents)
    assert documents[0]["portalClass"] == "Atto giudiziario"
    assert documents[1]["portalClass"] == "Provvedimento - sentenza"
    assert any("Nome file originale: 20260328104059747.PDF" in tag for tag in documents[0]["tags"])


def test_react_fascicolo_dettaglio_normalizza_referente_udienza_e_chiusura(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    imported_at = "2026-04-25"
    imported_at_it = "25/04/2026"
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        udienza_passata = (date.today() - timedelta(days=21)).isoformat()
        fascicolo = fascicoli.nuovo(
            "RG 466/2023 - Azioni di competenza GdP",
            TipoFascicolo.CIVILE,
            avvocato_referente="roberto.montagnese",
            data_prima_udienza=(date.today() - timedelta(days=60)).isoformat(),
            last_sync_at=imported_at,
            note=f"Importato da PolisWeb il {imported_at}",
        )
        fascicoli.aggiungi_attivita(
            fascicolo.id,
            TipoAttivita.UDIENZA,
            udienza_passata,
            "Udienza importata da PolisWeb",
            note=f"Evento acquisito il {imported_at}",
        )
        fascicoli.cambia_stato(fascicolo.id, StatoFascicolo.DEFINITO, avvocato="roberto.montagnese")

    response = client.get(
        f"/api/v1/ui/fascicoli/{fascicolo.id}",
        headers={"X-API-Key": "react-test-key"},
    )
    attivita_response = client.get(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/attivita",
        headers={"X-API-Key": "react-test-key"},
    )
    payload = response.get_json()
    attivita_payload = attivita_response.get_json()
    profile = {item["label"]: item["value"] for item in payload["profile"]}

    assert response.status_code == 200
    assert attivita_response.status_code == 200
    assert payload["fascicolo"]["leadLawyer"] == "Avv. Refactor"
    assert profile["Avv. referente"] == "Avv. Refactor"
    assert profile["Prossima udienza"] != "n.d."
    assert profile["Chiusura"] != "n.d."
    assert profile["Ultimo sync"] == imported_at_it
    assert payload["fascicolo"]["notes"] == f"Importato da PolisWeb il {imported_at_it}"
    assert any(
        item.get("notes") == f"Evento acquisito il {imported_at_it}"
        for item in payload["activities"]
    )
    assert attivita_payload["activities"][0]["notes"] == f"Evento acquisito il {imported_at_it}"
    assert imported_at not in str(payload)


def test_react_fascicolo_dettaglio_pulisce_righe_portale_duplicate(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo("RG 466/2023 - Usucapione", TipoFascicolo.CIVILE)
        fascicoli.aggiungi_attivita(
            fascicolo.id,
            TipoAttivita.UDIENZA,
            "2026-07-09",
            "Udienza importata da PolisWeb",
            descrizione="Udienza RG 466/2023",
        )
        fascicoli.aggiungi_attivita(
            fascicolo.id,
            TipoAttivita.UDIENZA,
            "2026-07-09",
            "Udienza rilevata",
            descrizione="Duplicato portale meno completo",
        )
        documento_portale = {
            "nome": "deposito_note.pdf",
            "tipo": "Documento",
            "data_deposito": "2026-03-10",
            "mittente": "FOTI ALFREDO",
        }
        for external_id in ("DEP-1", "DEP-2"):
            fascicoli.sincronizza_deposito_portale(
                fascicolo.id,
                fonte="PolisWeb / PST",
                id_deposito_esterno=external_id,
                tipo_atto="DepositoNoteConclusionali",
                data_deposito="2026-03-10",
                mittente="FOTI ALFREDO",
                documenti_portale=[documento_portale],
                registrato_da="antmm26051975",
                stato="IMPORTATO_DA_PORTALE",
                servizio_portale="DettaglioIstanze",
            )

    response = client.get(
        f"/api/v1/ui/fascicoli/{fascicolo.id}?include=attivita,depositi",
        headers={"X-API-Key": "react-test-key"},
    )
    payload = response.get_json()
    activities_text = json.dumps(payload["activities"], ensure_ascii=False)

    assert response.status_code == 200
    assert payload["quickCounts"]["attivita"] == 1
    assert len(payload["activities"]) == 1
    assert payload["activities"][0]["title"] == "Udienza importata da PolisWeb"
    assert "Deposito da portale" not in activities_text
    assert payload["quickCounts"]["comunicazioni"] == 1
    assert len(payload["deposits"]) == 1
    assert payload["deposits"][0]["actType"] == "Deposito note conclusionali"
    assert payload["deposits"][0]["message"] == "Deposito: Deposito note conclusionali - 1 documento"
    assert "Metadati importati" not in payload["deposits"][0]["message"]


def test_react_fascicoli_bridge_formatta_date_e_referenti_visibili():
    from web.services.react_fascicoli_bridge import (
        _date_label,
        _italian_dates_in_text,
        _lead_lawyer_label,
    )

    assert _date_label("2026-04-25") == "25/04/2026"
    assert _date_label("25/04/2026") == "25/04/2026"
    assert _italian_dates_in_text("Importato da PolisWeb il 2026-04-25") == "Importato da PolisWeb il 25/04/2026"
    assert _italian_dates_in_text("Errore 2026-99-99 non valido") == "Errore 2026-99-99 non valido"
    assert _lead_lawyer_label("roberto.montagnese", "Avv. Roberto Montagnese") == "Avv. Roberto Montagnese"
    assert _lead_lawyer_label("roberto.montagnese") == "Roberto Montagnese"


def test_fascicolo_form_react_preserva_referente_salvato_su_titolare_studio(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo(
            "Opposizione a decreto",
            TipoFascicolo.CIVILE,
            avvocato_referente="Avv. Referente Salvato",
        )

    response = client.get(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/modifica",
        headers={"X-API-Key": "react-test-key"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["studio"]["leadLawyer"] == "Avv. Refactor"
    assert payload["fascicolo"]["leadLawyer"] == "Avv. Referente Salvato"


def test_post_modifica_fascicolo_salva_avvocato_titolare_se_referente_vuoto(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo("Monitorio", TipoFascicolo.CIVILE)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/fascicoli/{fascicolo.id}/modifica",
            data={
                "titolo": "Monitorio aggiornato",
                "tipo": TipoFascicolo.CIVILE.value,
                "id_cliente": "",
                "controparte": "",
                "tribunale": "",
                "numero_rg": "",
                "anno_rg": "",
                "giudice": "",
                "sezione": "",
                "data_prima_udienza": "",
                "data_notifica_citazione": "",
                "avvocato_referente": "",
                "avvocato_dominus": "",
                "oggetto": "",
                "valore_causa": "",
                "note": "",
            },
            follow_redirects=False,
        )

    aggiornato = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    ).get(fascicolo.id)

    assert response.status_code in {302, 303}
    assert aggiornato is not None
    assert aggiornato.avvocato_referente == "Avv. Refactor"


def test_react_fascicolo_nuovo_form_collassabile_e_fascicolo_veloce():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    codice_search = Path("frontend/src/components/CodiceOggettoPstSearch.tsx").read_text(encoding="utf-8")

    dati_generali = source[
        source.index("CollapsibleFormPanel title={labels.sections.datiGenerali}") :
        source.index('CollapsibleFormPanel title="Parti"')
    ]
    identificazione = source[
        source.index("CollapsibleFormPanel title={labels.sections.identificazioneGiudiziale}") :
        source.index("CollapsibleFormPanel title={labels.sections.annotazioni}")
    ]

    assert "CollapsibleFormPanel" in source
    assert ".iu-fas-form-panel__summary" in css
    assert dati_generali.index("personalizzabile") < dati_generali.index("PraticheCollegateField data={data}") < dati_generali.index("Fascicolo Veloce")
    assert "PraticheCollegateField data={data}" not in identificazione
    assert "ClientChoiceField data={data}" in source
    assert "CounterpartyFields data={data} required={fascicoloVeloce}" in source
    assert "JudicialOfficeField data={data} required={fascicoloVeloce}" in source
    assert "id_soggetto_controparte" in source
    assert "cf_controparte" in source
    assert "fascicolo-uffici-giudiziari" in source
    assert "data.query.ufficio_competente" in source
    assert "Uffici giudiziari per Comune" in source
    assert "FASCICOLO_OFFICE_KIND_FILTERS" in source
    assert "{ value: 'giudice_pace', label: 'GDP' }" in source
    assert "{ value: 'unep', label: 'UNEP' }" in source
    assert "/api/v1/ui/territorio/comuni" in source
    assert "/api/v1/ui/strumenti-legali/uffici_competenti" in source
    assert "body.append('tipo_ufficio', officeKind)" in source
    assert 'name="codice_ministero_autorita"' in source
    assert 'name="codice_ufficio_autorita" value={selectedOfficeCode}' in source
    assert 'name="codice_ministero_autorita" value={selectedPstCode}' in source
    assert 'name="codice_gl_autorita"' in source
    assert 'name="codice_istat_sede_autorita"' in source
    assert "officeDepositoCode" in source
    assert "codice ufficio" in source
    assert "codice PST" in source
    assert "ISTAT sede" in source
    assert "Per deposito o consultazione telematica conferma il canale autorizzato" in source
    assert "office.codiceMinistero || office.codice || office.codiceGiustiziaLocale" not in source
    assert "Usa nel fascicolo" in source
    assert ".iu-fas-office-competence" in css
    assert ".iu-fas-office-kind-filter" in css
    assert 'name="documenti_fascicolo"' in source
    assert 'name="email_fascicolo"' in source
    assert 'accept=".eml,message/rfc822"' in source
    assert "findCodiceOggettoPst(nextQuery.trim())" in codice_search


def test_post_nuovo_fascicolo_con_cliente_apre_il_fascicolo(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    gestore_clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = gestore_clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Fascicolo",
        codice_fiscale="FSRMRA80A01H501U",
    )

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/fascicoli/nuovo",
            data={
                "id_cliente": cliente.id,
                "titolo": "Nuovo fascicolo da cliente",
                "tipo": TipoFascicolo.CIVILE.value,
                "oggetto": "Apertura ordinaria da scheda cliente",
                "tribunale": "Tribunale di Milano",
            },
            follow_redirects=False,
        )
        location = response.headers["Location"]

    assert response.status_code in {302, 303}
    assert "/clienti/" not in location
    assert re.search(r"/fascicoli/[^/]+$", location)


def test_post_nuovo_fascicolo_veloce_carica_documenti_ed_email_eml(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/fascicoli/nuovo",
            data={
                "titolo": "Apertura veloce deposito assistito",
                "tipo": TipoFascicolo.CIVILE.value,
                "oggetto": "Apertura con caricamenti iniziali",
                "tribunale": "Tribunale di Milano",
                "controparte": "Beta Costruzioni Srl",
                "cf_controparte": "12345678901",
                "fascicolo_veloce": "1",
                "personalizzabile": "1",
                "documenti_fascicolo": [
                    (io.BytesIO(b"%PDF-1.4\natto principale"), "atto_principale.pdf"),
                    (io.BytesIO(b"contratto allegato"), "contratto.txt"),
                ],
                "email_fascicolo": [
                    (io.BytesIO(b"From: cancelleria@example.test\nSubject: Ricevuta\n\nOK"), "ricevuta_accettazione.eml"),
                    (io.BytesIO(b"non importare come email"), "nota.txt"),
                ],
            },
            follow_redirects=False,
        )
        location = response.headers["Location"]
        id_fascicolo = location.split("/fascicoli/", 1)[1].split("/", 1)[0]
        detail_response = client.get(
            f"/api/v1/ui/fascicoli/{id_fascicolo}",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = detail_response.get_json()
    fascicolo = payload["fascicolo"]
    documents = payload["documents"]
    nomi_documenti = {doc["name"] for doc in documents}
    email_docs = [doc for doc in documents if "email-iniziali" in doc["tags"]]

    assert response.status_code in {302, 303}
    assert location.endswith(f"/fascicoli/{id_fascicolo}/deposito/prepara")
    assert detail_response.status_code == 200
    assert fascicolo["fascicoloVeloce"] is True
    assert fascicolo["court"] == "Tribunale di Milano"
    assert fascicolo["counterparty"] == "Beta Costruzioni Srl"
    assert fascicolo["counterpartyTaxCode"] == "12345678901"
    assert fascicolo["documentiInizialiCount"] == 2
    assert fascicolo["emailInizialiCount"] == 1
    assert len(documents) == 3
    assert {"atto_principale.pdf", "contratto.txt", "ricevuta_accettazione.eml"} <= nomi_documenti
    assert "nota.txt" not in nomi_documenti
    assert len(email_docs) == 1
    assert email_docs[0]["type"] == TipoDocumento.COMUNICAZIONE.value


def test_post_nuovo_fascicolo_veloce_risolve_codice_oggetto_pst_digitato(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/fascicoli/nuovo",
            data={
                "titolo": "Apertura veloce con codice PST",
                "tipo": TipoFascicolo.CIVILE.value,
                "oggetto": "014001",
                "tribunale": "Tribunale di Milano",
                "controparte": "Delta Recuperi Srl",
                "cf_controparte": "12345678901",
                "fascicolo_veloce": "1",
            },
            follow_redirects=False,
        )
        location = response.headers["Location"]
        id_fascicolo = location.split("/fascicoli/", 1)[1].split("/", 1)[0]
        detail_response = client.get(
            f"/api/v1/ui/fascicoli/{id_fascicolo}",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = detail_response.get_json()
    fascicolo = payload["fascicolo"]

    assert response.status_code in {302, 303}
    assert location.endswith(f"/fascicoli/{id_fascicolo}/deposito/prepara")
    assert detail_response.status_code == 200
    assert fascicolo["codiceOggettoPst"] == "014001"
    assert fascicolo["fonteCodiceOggetto"] == "PST_XSD"
    assert fascicolo["fileFonteCodiceOggetto"].endswith(".xsd")
    assert "Istanza sospensione" in fascicolo["object"]


def test_post_nuovo_fascicolo_da_preventivo_preserva_codice_oggetto_fino_a_deposito(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Paola",
        cognome="Preventivo",
        codice_fiscale="PRVPLA80A41H501X",
    )
    gestore_preventivi = GestionePreventivi(app.config["PREVENTIVI_DB"])
    preventivo = gestore_preventivi.crea_preventivo(
        cliente.id,
        "Istanza sospensione esecuzione",
        [VocePreventivo(descrizione="Studio e deposito", importo=900.0)],
        codice_oggetto_pst="014001",
        fonte_codice_oggetto="PST_XSD",
        file_fonte_codice_oggetto="tipi-base.xsd",
    )
    conferimento = gestore_preventivi.crea_conferimento(
        cliente.id,
        "Istanza sospensione esecuzione",
        avvocato_referente="Avv. Refactor",
        compenso_pattuito=900.0,
        id_preventivo=preventivo.id,
    )

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/fascicoli/nuovo",
            data={
                "source_preventivo": preventivo.id,
                "source_conferimento": conferimento.id,
                "id_cliente": cliente.id,
                "titolo": "Fascicolo da preventivo accettato",
                "tipo": TipoFascicolo.CIVILE.value,
                "oggetto": "Apertura da preventivo accettato",
                "tribunale": "Tribunale di Milano",
                "controparte": "Omega Debitrice Srl",
                "cf_controparte": "12345678901",
                "fascicolo_veloce": "1",
            },
            follow_redirects=False,
        )
        location = response.headers["Location"]
        id_fascicolo = location.split("/fascicoli/", 1)[1].split("/", 1)[0]
        detail_response = client.get(
            f"/api/v1/ui/fascicoli/{id_fascicolo}",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = detail_response.get_json()
    fascicolo = payload["fascicolo"]
    gestore_preventivi_aggiornato = GestionePreventivi(app.config["PREVENTIVI_DB"])
    preventivo_collegato = gestore_preventivi_aggiornato.get_preventivo(preventivo.id)
    conferimento_collegato = gestore_preventivi_aggiornato.get_conferimento(conferimento.id)

    assert response.status_code in {302, 303}
    assert location.endswith(f"/fascicoli/{id_fascicolo}/deposito/prepara")
    assert detail_response.status_code == 200
    assert fascicolo["codiceOggettoPst"] == "014001"
    assert fascicolo["fonteCodiceOggetto"] == "PST_XSD"
    assert preventivo_collegato.id_fascicolo == id_fascicolo
    assert conferimento_collegato.id_fascicolo == id_fascicolo


def test_post_nuovo_fascicolo_veloce_crea_e_collega_soggetto_controparte(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/fascicoli/nuovo",
            data={
                "titolo": "Fascicolo veloce con nuova controparte",
                "tipo": TipoFascicolo.CIVILE.value,
                "oggetto": "Apertura con controparte da censire",
                "tribunale": "Tribunale di Milano",
                "controparte": "Gamma Costruzioni Srl",
                "cf_controparte": "11122233344",
                "fascicolo_veloce": "1",
                "crea_soggetto_controparte": "1",
                "nuovo_soggetto_tipo": TipoSoggetto.PERSONA_GIURIDICA.value,
                "nuovo_soggetto_nome_completo": "Gamma Costruzioni Srl",
                "nuovo_soggetto_identificativo": "11122233344",
                "nuovo_soggetto_email": "amministrazione@gamma.test",
                "nuovo_soggetto_pec": "gamma@pec.test",
            },
            follow_redirects=False,
        )
        location = response.headers["Location"]
        id_fascicolo = location.split("/fascicoli/", 1)[1].split("/", 1)[0]
        detail_response = client.get(
            f"/api/v1/ui/fascicoli/{id_fascicolo}",
            headers={"X-API-Key": "react-test-key"},
        )

    soggetti = GestioneSoggetti(app.config["SOGGETTI_DB"], app.config["SOGGETTI_PARTI_DB"])
    controparte = next(
        soggetto for soggetto in soggetti.tutti()
        if soggetto.nome_completo == "Gamma Costruzioni Srl"
    )
    parti = soggetti.parti_fascicolo(id_fascicolo)
    payload = detail_response.get_json()

    assert response.status_code in {302, 303}
    assert location.endswith(f"/fascicoli/{id_fascicolo}/deposito/prepara")
    assert controparte.partita_iva == "11122233344"
    assert controparte.recapiti.pec == "gamma@pec.test"
    assert any(
        parte.id_soggetto == controparte.id and parte.ruolo == RuoloSoggetto.CONTROPARTE
        for parte, _soggetto in parti
    )
    assert payload["fascicolo"]["counterparty"] == "Gamma Costruzioni Srl"
    assert payload["fascicolo"]["counterpartyTaxCode"] == "11122233344"


def test_post_nuovo_fascicolo_veloce_restituisce_errori_chiari_json(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/fascicoli/nuovo",
            data={
                "titolo": "Apertura incompleta",
                "tipo": TipoFascicolo.CIVILE.value,
                "fascicolo_veloce": "1",
            },
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )

    payload = response.get_json()
    assert response.status_code == 400
    assert payload["ok"] is False
    assert "Per creare il fascicolo veloce mancano" in payload["message"]
    assert "autorità giudiziaria" in payload["message"]
    assert "controparte" in payload["message"]
    assert "Operazione non riuscita" not in payload["message"]


def test_react_clienti_nuovo_e_soggetti_collegati_nav_api_lex_cf():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    new_page = Path("frontend/src/components/NuovoClientePage.tsx").read_text(encoding="utf-8")
    new_data = Path("frontend/src/clientiNuovoData.ts").read_text(encoding="utf-8")
    new_css = Path("frontend/src/components/NuovoClientePage.css").read_text(encoding="utf-8")
    soggetti_page = Path("frontend/src/components/SoggettiPage.tsx").read_text(encoding="utf-8")
    soggetti_data = Path("frontend/src/soggettiData.ts").read_text(encoding="utf-8")
    soggetti_css = Path("frontend/src/components/SoggettiPage.css").read_text(encoding="utf-8")
    fascicoli_page = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    clienti_routes = Path("web/bootstrap/clienti_routes.py").read_text(encoding="utf-8")
    soggetti_model = Path("pct/soggetti.py").read_text(encoding="utf-8")

    assert "/clienti/nuovo" in app_source
    assert "/soggetti" in app_source
    assert "/soggetti/nuovo" in app_source
    assert "isNewClientPage||isNewSubjectPage||isClientEditPage||isSubjectEditPage?<NuovoClientePage/>" in app_source
    assert "isSubjectEditPage" in app_source
    assert "isSoggettiPage?<SoggettiPage/>" in app_source
    assert "{ label: 'Nuovo Cliente', icon: UserPlus, href: '/clienti/nuovo' }" in app_source
    assert "{ label: 'Anagrafica', icon: UsersRound, href: '/soggetti' }" in app_source
    assert "{ label: 'Nuovo Soggetto', icon: UserPlus, href: '/soggetti/nuovo' }" in app_source
    assert "/api/v1/ui/clienti/nuovo" in new_data
    assert "/api/v1/ui/clienti/${encodeURIComponent(decodeURIComponent(editMatch[1]))}/modifica" in new_data
    assert "/api/v1/ui/soggetti/${encodeURIComponent(decodeURIComponent(subjectEditMatch[1]))}/modifica" in new_data
    assert "edit_subject" in new_data
    assert "/api/v1/ui/soggetti" in soggetti_data
    assert "matterIds.includes(matterFilter)" in soggetti_page
    assert "matterIds:" in soggetti_data
    assert "clientRecordHref" in fascicoli_page
    assert "partiesRecordHref" in fascicoli_page
    assert "RecordOverlayButton" in fascicoli_page
    assert "Visualizza cliente nel fascicolo" in fascicoli_page
    assert "Visualizza soggetti e parti nel fascicolo" in fascicoli_page
    assert "/api/cf/calcola" in new_page
    assert "/api/cf/decodifica" in new_page
    assert "Genera CF" in new_page
    assert "Lettore documento" in new_page
    assert "Carica documento" in new_page
    assert "Leggi documento / MRZ" in new_page
    assert "Dati letti dal documento" in new_page
    assert "selectedDocumentFile" in new_page
    assert "IUSENTRA_CLIENTE_NUOVO" in new_page
    assert "applicaDatiDocumento" in new_page
    assert "iusentra:cliente-documento-rilevato" in new_page
    assert "normalizeClientDocumentScan" in new_page
    assert "data.actions.documentReader" in new_page
    assert "target === 'data_nascita'" in new_page
    assert "doc_data_scadenza" in new_page
    assert 'name="provincia_nascita"' in new_page
    assert 'name="crea_preventivo_iniziale"' in new_page
    assert 'name="qualifica"' in new_page
    assert "Tipo soggetto processuale" in new_page
    assert "FloatingLex" in new_page
    assert "context={tab === 'cliente' ? 'nuovo-cliente' : 'nuovo-soggetto'}" in new_page
    assert "SoggettiPage" in soggetti_page
    assert 'context="soggetti"' in soggetti_page
    assert '@api_v1_react.get("/clienti/nuovo")' in api_source
    assert '@api_v1_react.post("/clienti/nuovo/documento/leggi")' in api_source
    assert "read_client_document_upload" in api_source
    assert '@api_v1_react.get("/clienti/<id_cliente>/modifica")' in api_source
    assert '@api_v1_react.get("/soggetti/<id_soggetto>/modifica")' in api_source
    assert '@api_v1_react.get("/soggetti")' in api_source
    assert '"1" in form.getlist("crea_preventivo_iniziale")' in clienti_routes
    assert "provincia_nascita: str = \"\"" in soggetti_model
    assert ".iu-clienti-new-page" in new_css
    assert ".iu-cln-process-grid" in new_css
    assert ".iu-cln-doc-reader" in new_css
    assert ".iu-soggetti-page" in soggetti_css
    assert ".iu-sogg-table" in soggetti_css
    assert "@media(max-width:760px)" in new_css
    assert "@media(max-width:760px)" in soggetti_css


def test_react_clienti_nuovo_e_soggetti_api_usa_repository_reali(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501U",
    )
    soggetti = GestioneSoggetti(app.config["SOGGETTI_DB"], app.config["SOGGETTI_PARTI_DB"])
    soggetto = soggetti.crea(
        TipoSoggetto.PERSONA_FISICA,
        nome="Luigi",
        cognome="Bianchi",
        codice_fiscale="BNCLGU80A01H501B",
        provincia_nascita="RM",
        qualifica="CONTROPARTE",
        id_cliente=cliente.id,
    )
    soggetti.aggiungi_parte("fas-test", soggetto.id, RuoloSoggetto.CONTROPARTE)

    new_response = client.get("/api/v1/ui/clienti/nuovo", headers={"X-API-Key": "react-test-key"})
    subjects_response = client.get("/api/v1/ui/soggetti", headers={"X-API-Key": "react-test-key"})
    new_payload = new_response.get_json()
    subjects_payload = subjects_response.get_json()

    assert new_response.status_code == 200
    assert subjects_response.status_code == 200
    assert new_payload["source"] == "repository_reali"
    assert new_payload["contracts"]["mock_fallback"] is False
    assert new_payload["contracts"]["writes"] == "operational_routes"
    assert new_payload["stats"]["totalClients"] == 1
    assert new_payload["stats"]["totalSubjects"] == 1
    assert new_payload["clientOptions"][0]["id"] == cliente.id
    assert any(item["value"] == "GARANTE" for item in new_payload["options"]["subjectRoles"])
    assert subjects_payload["source"] == "repository_reali"
    assert subjects_payload["contracts"]["read_only"] is False
    assert subjects_payload["contracts"]["writes"] == "operational_routes"
    assert subjects_payload["contracts"]["route_owner"] == "react_shell"
    assert subjects_payload["summary"]["total"] == 1
    assert subjects_payload["items"][0]["id"] == soggetto.id
    assert subjects_payload["items"][0]["clientName"] == cliente.nome_completo
    assert subjects_payload["items"][0]["matterIds"] == ["fas-test"]


def test_codice_fiscale_calcolo_e_decodifica_api_react(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    calculated = client.get(
        "/api/cf/calcola",
        query_string={
            "cognome": "Rossi",
            "nome": "Mario",
            "sesso": "M",
            "data_nascita": "1980-01-01",
            "luogo_nascita": "Roma",
            "provincia_nascita": "RM",
        },
    )
    payload = calculated.get_json()
    decoded = client.get("/api/cf/decodifica", query_string={"cf": payload["codice_fiscale"]}).get_json()

    assert calculated.status_code == 200
    assert payload["codice_fiscale"] == "RSSMRA80A01H501U"
    assert payload["belfiore"] == "H501"
    assert decoded["data_nascita"] == "1980-01-01"
    assert decoded["luogo_nascita"] == "Roma"
    assert decoded["provincia_nascita"] == "RM"


def test_react_wizard_pro_nav_route_api_e_card_operative(tmp_path: Path):
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/WizardProPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/wizardProData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/WizardProPage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    route_source = Path("web/blueprints/wizard_pro.py").read_text(encoding="utf-8")

    assert "{ label: 'Preparazione Udienza Guidata', icon: Building2, href: '/wizard-pro/' }" in app_source
    assert "isWizardProDashboard?<WizardProPage/>" in app_source
    assert "isWizardProStep?<WizardProStepPage/>" in app_source
    assert "isWizardProComplete?<WizardProCompletePage/>" in app_source
    assert "WizardProPage" in app_source
    assert "WizardProStepPage" in app_source
    assert "WizardProCompletePage" in app_source
    assert "getWizardProPage" in data_source
    assert "getWizardProStepPage" in data_source
    assert "getWizardProCompletePage" in data_source
    assert "/api/v1/ui/wizard-pro" in data_source
    assert '@api_v1_react.get("/wizard-pro")' in api_source
    assert '@api_v1_react.get("/wizard-pro/session/<id_sessione>/step/<int:n>")' in api_source
    assert '@api_v1_react.get("/wizard-pro/session/<id_sessione>/completo")' in api_source
    assert "build_react_wizard_pro_payload" in api_source
    assert "render_react_shell_response(\"wizard-pro\")" in route_source
    assert "Vista classica" not in page_source
    assert "_legacy=1" not in page_source
    assert "JsonPostForm action={item.startHref}" in page_source
    assert "item.startHref" in page_source
    assert "Termini collegati" in page_source
    assert "data.actions.lex" in page_source
    assert ".iu-wiz-page" in css
    assert "@media(max-width:980px)" in css

    app = _app(tmp_path)
    _crea_operatore(app)
    with app.test_client() as client:
        _login(client)
        response = client.get("/wizard-pro/")
        legacy = client.get("/wizard-pro/?_legacy=1")
        api_response = client.get("/api/v1/ui/wizard-pro", headers={"X-API-Key": "react-test-key"})

    assert response.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in response.get_data(as_text=True)
    assert legacy.status_code == 200
    assert 'id="root"' not in legacy.get_data(as_text=True)
    assert api_response.status_code == 200
    payload = api_response.get_json()
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["writes"] == "operational_routes"


def test_react_clienti_delete_actions_presenti_e_endpoint_json_elimina(tmp_path: Path):
    source = Path("frontend/src/components/AnagraficaClientiPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/clientiData.ts").read_text(encoding="utf-8")

    assert "Elimina selezione" in source
    assert "deleteCliente" in source
    assert "/api/v1/ui/clienti/delete" in data_source

    app = _app(tmp_path)
    _crea_operatore(app)
    cliente_repo = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente_1 = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Anna", cognome="Rossi")
    cliente_2 = cliente_repo.nuovo(TipoCliente.PERSONA_FISICA, nome="Luca", cognome="Bianchi")

    with app.test_client() as client:
        _login(client)
        payload = client.get("/api/v1/ui/clienti").get_json()
        rows = {item["id"]: item for item in payload["items"]}
        assert rows[cliente_1.id]["deleteHref"].endswith(f"/clienti/{cliente_1.id}/elimina")
        response = client.post("/api/v1/ui/clienti/delete", json={"ids": [cliente_1.id, cliente_2.id]})
        payload_after = client.get("/api/v1/ui/clienti").get_json()

    assert response.status_code == 200
    result = response.get_json()
    assert result["ok"] is True
    assert set(result["deleted"]) == {cliente_1.id, cliente_2.id}
    cliente_ids_after = {item["id"] for item in payload_after["items"]}
    assert cliente_1.id not in cliente_ids_after
    assert cliente_2.id not in cliente_ids_after


def test_react_soggetti_delete_actions_presenti_e_endpoint_json_elimina(tmp_path: Path):
    source = Path("frontend/src/components/SoggettiPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/soggettiData.ts").read_text(encoding="utf-8")

    assert "Elimina selezione" in source
    assert "deleteSoggetto" in source
    assert "/api/v1/ui/soggetti/delete" in data_source

    app = _app(tmp_path)
    _crea_operatore(app)
    soggetti = GestioneSoggetti(app.config["SOGGETTI_DB"], app.config["SOGGETTI_PARTI_DB"])
    soggetto_1 = soggetti.crea(TipoSoggetto.PERSONA_FISICA, nome="Mario", cognome="Verdi")
    soggetto_2 = soggetti.crea(TipoSoggetto.PERSONA_FISICA, nome="Giulia", cognome="Neri")

    with app.test_client() as client:
        _login(client)
        payload = client.get("/api/v1/ui/soggetti").get_json()
        rows = {item["id"]: item for item in payload["items"]}
        assert rows[soggetto_1.id]["deleteHref"].endswith(f"/soggetti/{soggetto_1.id}/elimina")
        response = client.post("/api/v1/ui/soggetti/delete", json={"ids": [soggetto_1.id, soggetto_2.id]})
        payload_after = client.get("/api/v1/ui/soggetti").get_json()

    assert response.status_code == 200
    result = response.get_json()
    assert result["ok"] is True
    assert set(result["deleted"]) == {soggetto_1.id, soggetto_2.id}
    soggetti_ids_after = {item["id"] for item in payload_after["items"]}
    assert soggetto_1.id not in soggetti_ids_after
    assert soggetto_2.id not in soggetti_ids_after


def test_react_fascicolo_relata_notifica_monitorata_in_ui_e_payload():
    page_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    bridge_source = Path("web/services/react_fascicoli_bridge.py").read_text(encoding="utf-8")

    assert "Relata notifica" in page_source
    assert "NotificationRelataMonitor" in page_source
    assert "relataListHref" in page_source
    assert "openDetailSectionById(sectionId)" in page_source
    assert "notificationRelata" in data_source
    assert "relataStatusLabel" in data_source
    assert '"notificationRelata": notification_relata' in bridge_source
    assert '"relataStatusLabel": "Provvedimento da scaricare dal portale"' in bridge_source
    assert '"relata_notifica": relata_count' in bridge_source
