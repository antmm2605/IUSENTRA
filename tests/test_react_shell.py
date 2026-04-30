from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from pct.agenda import Agenda, TipoAppuntamento
from pct.clienti import GestioneClienti, TipoCliente
from pct.email_client import CartellaEmail, EmailRicevuta, GestioneEmailRicevute, StatoEmail
from pct.fascicoli import GestioneFascicoli, StatoFascicolo, TipoAttivita, TipoFascicolo
from pct.messaggi import CanaleMsggio, ConfigMessaggistica, GestioneMessaggi, Messaggio, StatoMessaggio
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
    return app


def test_react_blueprints_registered(tmp_path: Path):
    app = _app(tmp_path)

    assert "react_shell" in app.blueprints
    assert "api_v1_react" in app.blueprints
    assert any(entry.name == "react_shell" for entry in BLUEPRINT_REGISTRY)
    assert any(entry.name == "api_v1_react" for entry in BLUEPRINT_REGISTRY)


def test_react_shell_primo_blocco_richiede_login(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/app-v2")

    assert response.status_code in {302, 303}
    assert "/login" in response.headers["Location"]


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
        "SIGP - Giudice di Pace",
        "Guida firma digitale",
        "Parcelle e Fatture",
        "Preventivi e Incarichi",
        "Archivio Giurisprudenza",
        "Sincronizzazione Calendari",
        "Profili e Permessi",
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
    assert "useState<Record<string,boolean>>({})" in source
    assert "openSections[section.id] === true" in source
    assert "onCloseMobile" in source
    assert "onNavigate={onCloseMobile}" in source
    assert "mobileOpen ? 'Chiudi menu'" in source
    assert "{ label: 'Regia Operativa', icon: Sparkles, href: '/workspace-intelligente' }" in source
    assert "{ label: 'Nuovo Appuntamento', icon: CirclePlus, href: '/agenda/nuovo' }" in source
    assert "{ label: 'Preparazione Udienza Guidata', icon: Building2, href: '/wizard-pro/' }" in source
    assert ".iu-sidebar.iu-sidebar--mobile-open .iu-sidebar__toggle" in css
    assert "AppErrorBoundary" in source
    assert ".iu-react-error" in css


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
    assert 'href="/lex?context=agenda"' not in agenda_page
    assert "localStorage" in floating_lex
    assert "onPointerDown" in floating_lex
    assert "Math.hypot" in floating_lex
    assert "aria-expanded" in floating_lex
    assert "iusentra:open-floating-lex" in floating_lex
    assert ".iu-agenda-page" in css
    assert ".iu-ag-slot" in css
    assert ".iu-ag-week--month" in css
    assert ".iu-lex-float{display:none}" not in css
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
    assert "action={formAction}" in appointment_page
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
    assert "localStorage" in appointment_page
    assert ".iu-appointment-page" in appointment_css
    assert ".iu-appt-lex-float" in appointment_css
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
    assert "localStorage" in floating_lex
    assert "onPointerDown" in floating_lex
    assert "Math.hypot" in floating_lex
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
    assert 'render_react_shell_response(f"clienti/{id_cliente}")' in clienti_routes
    assert 'render_react_shell_response(f"clienti/{id_cliente}/modifica")' in clienti_routes
    assert "data.actions.newDeadline" in page_source
    assert "data.actions.newMatter" in page_source
    assert "data.actions.newMessage" in page_source
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


def test_react_comunicazioni_email_messaggi_collegate_nav_e_shell():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    email_page = Path("frontend/src/components/EmailPecPage.tsx").read_text(encoding="utf-8")
    email_data = Path("frontend/src/emailData.ts").read_text(encoding="utf-8")
    messaggi_page = Path("frontend/src/components/MessaggiPage.tsx").read_text(encoding="utf-8")
    messaggi_data = Path("frontend/src/messaggiData.ts").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "{ label: 'Email PEC', icon: Mail, href: '/email/', badge: 'PEC' }" in app_source
    assert "{ label: 'Messaggi', icon: MessageCircle, href: '/messaggi' }" in app_source
    assert "{ label: 'Nuovo SMS/WA', icon: Send, href: '/messaggi/nuovo' }" in app_source
    assert "isEmailPage?<EmailPecPage/>" in app_source
    assert "isNewMessagePage?<NuovoMessaggioPage/>" in app_source
    assert "isMessagesPage?<MessaggiPage/>" in app_source
    assert "Casella PEC dello studio" in email_page
    assert "Cartelle PEC" in email_page
    assert "getEmailPecPage" in email_data
    assert "/api/v1/ui/email" in email_data
    assert "Nuovo messaggio" in messaggi_page
    assert "getMessaggiData" in messaggi_data
    assert "sendEndpoint" in messaggi_data
    assert "/api/v1/ui/messaggi" in messaggi_data
    assert '@api_v1_react.get("/email")' in api_source
    assert '@api_v1_react.get("/messaggi")' in api_source
    assert '@api_v1_react.get("/messaggi/nuovo")' in api_source


def test_route_ufficiali_email_messaggi_servono_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)

        for path in ("/email/", "/messaggi", "/messaggi/nuovo"):
            response = client.get(path)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html
            assert 'id="root"' in html

        classic_email = client.get("/email/?_legacy=1")
        classic_messages = client.get("/messaggi?_legacy=1")
        classic_new_message = client.get("/messaggi/nuovo?_legacy=1")

    assert classic_email.status_code == 200
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
    assert "Centro Servizi Telematici" in app_source
    assert "getTelematicoPage" in data_source
    assert "/api/v1/ui/telematico" in data_source
    assert '@api_v1_react.get("/telematico")' in api_source
    assert "FloatingLex" in page_source
    assert 'context="telematico"' in page_source
    assert ".iu-telematico-page" in css
    assert "@media(max-width:760px)" in css


def test_route_telematico_serve_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/telematico")
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

    assert "const TelematicoSurfacePage" in app_source
    assert "isTelematicoSurfacePage" in app_source
    assert "isTelematicoSurfacePage?<TelematicoSurfacePage/>" in app_source
    assert "{ label: 'PTT Tributario', icon: FileText, href: '/sigit' }" in app_source
    assert "{ label: 'Importa pratica da PST', icon: CloudUpload, href: '/portali/pst/acquisizione' }" in app_source
    assert "getTelematicoSurfacePage" in data_source
    assert "/api/v1/ui/telematico/surface/" in data_source
    assert "OfficeDirectory" in page_source
    assert "SurfaceSidePanels" in page_source
    assert "iu-tel-tribunali-workspace" in page_source
    assert "Checklist operativa" in page_source
    assert "iu-tel-surface-hero__meta" in page_source
    assert "iu-tel-surface-hero__eyebrow" in page_source
    assert '"pst": "Importa pratica da PST"' in bridge_source
    assert '"importa-pratica"' in bridge_source
    assert '@api_v1_react.get("/telematico/surface/<surface>")' in api_source
    assert "build_react_telematico_surface_payload" in api_source
    assert "build_react_tribunali_payload" in api_source
    assert 'render_react_shell_response("polisWeb")' in polisweb_routes
    assert 'render_react_shell_response("pdp")' in portali_routes
    assert 'render_react_shell_response("pat")' in portali_routes
    assert 'render_react_shell_response("sigit")' in portali_routes
    assert 'render_react_shell_response("deposito/checklist")' in deposito_routes
    assert 'render_react_shell_response("guida/firma-digitale")' in deposito_routes
    assert 'render_react_shell_response("tribunali")' in lookup_routes
    assert ".iu-tel-surface-page" in css
    assert ".iu-tel-surface-hero__meta a" in css
    assert "background:rgba(255,255,255,.16)" in css
    assert ".iu-tel-offices" in css
    assert ".iu-tel-tribunali-workspace" in css
    assert "grid-template-columns:minmax(0,1fr) 360px" in css
    assert "@media(max-width:860px)" in css


def test_route_ufficiali_superfici_telematiche_servono_react_con_legacy(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        for path in ("/polisWeb", "/pdp", "/pat", "/sigit", "/tribunali", "/deposito/checklist", "/guida/firma-digitale"):
            response = client.get(path)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, path
            assert '<html lang="it" class="react-shell-document">' in html
            assert 'id="root"' in html

        for path in ("/polisWeb?_legacy=1", "/pdp?_legacy=1", "/pat?_legacy=1", "/sigit?_legacy=1", "/tribunali?_legacy=1", "/deposito/checklist?_legacy=1", "/guida/firma-digitale?_legacy=1"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert 'id="root"' not in response.get_data(as_text=True)


def test_react_superfici_telematiche_api_payload_reale(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

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
    assert polisweb_payload["channel"]["quickActions"][1]["label"] == "Importa pratica da PST"
    assert tribunali.status_code == 200
    assert tribunali_payload["surface"]["id"] == "tribunali"
    assert tribunali_payload["officeSummary"]["perType"] is not None
    assert tribunali_payload["officeSummary"]["sources"]
    assert "PEC di deposito" in tribunali_payload["officeSummary"]["policy"]
    assert any(row["indirizziTelematici"] for row in tribunali_payload["offices"] if row["pec"])


def test_route_importa_pratica_pst_resta_raggiungibile_dalla_nav(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/portali/pst/acquisizione")
        shortcut = client.get("/polisWeb/acquisizione")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Importa pratica da PST" in html
    assert "/api/portali/pst/acquisizione/search" in html
    assert shortcut.status_code in {302, 303}
    assert shortcut.headers["Location"].endswith("/portali/pst/acquisizione")


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
            f"/fascicoli/{fascicolo.id}/modifica",
            f"/fascicoli/{fascicolo.id}/quadro",
            "/telematico",
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
        classic_telematico = client.get("/telematico?_legacy=1")

    assert classic_dashboard.status_code == 200
    assert classic_workspace.status_code == 200
    assert classic_search.status_code == 200
    assert classic_agenda.status_code == 200
    assert classic_fascicoli.status_code == 200
    assert classic_telematico.status_code == 200
    assert 'id="root"' not in classic_dashboard.get_data(as_text=True)
    assert 'id="root"' not in classic_fascicoli.get_data(as_text=True)
    assert 'id="root"' not in classic_telematico.get_data(as_text=True)


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
    assert list_payload["items"][0]["whatsappLink"].startswith("https://wa.me/")
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
    assert 'href="/fascicoli"><BriefcaseBusiness size={18}/>Fascicoli' in app_source
    assert "getFascicoliPage" in data_source
    assert "/api/v1/ui/fascicoli" in data_source
    assert "FascicoliPage" in page_source
    assert "rawPath.startsWith('/app-v2/fascicoli')" in page_source
    assert "FloatingLex" in page_source
    assert "context=\"fascicoli\"" in page_source
    assert "localStorage" in floating_lex
    assert "onPointerDown" in floating_lex
    assert "Math.hypot" in floating_lex
    assert ".iu-fascicoli-page" in css
    assert "@media(max-width:760px)" in css


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
    for service_action in ("/documenti/carica", "/documenti/importa-portale", "/attivita/aggiungi", "/definisci", "/archivia", "/ripristina"):
        assert service_action in bridge
    assert "Vista classica" not in page_source
    assert "kind: 'quadro'" in page_source
    assert "rawPath.startsWith('/app-v2/fascicoli')" in page_source
    assert "parts[1] === 'quadro'" in page_source
    assert "quadroHref" in page_source
    assert "fascicolo-quadro" in page_source
    assert "operationalHref}/copertina" in page_source
    assert "<details id={id}" in page_source
    assert 'className="iu-fas-detail-section" open' not in page_source
    assert "Quadro intelligente" in page_source
    assert "Dati aggiornati - ${data.source}" not in page_source
    assert 'title="Soggetti e parti"' in page_source
    assert 'title="Cancelleria e istanze"' in page_source
    assert 'title="Servizi telematici"' in page_source
    assert "FascicoloGuardrailsPanel" in page_source
    assert "data.guardrails" in page_source
    assert "Guardrail deposito telematico" in page_source
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
    assert "localStorage" in floating_lex
    assert "onPointerDown" in floating_lex
    assert "Math.hypot" in floating_lex
    assert ".iu-fascicoli-page" in css
    assert ".iu-fascicolo-detail-page" in css
    assert ".iu-fascicolo-form-page" in css
    assert ".iu-fas-export-page" in css
    assert ".iu-fas-back-top" in css
    assert ".iu-fas-detail-section__summary" in css
    assert ".iu-fas-smart-board" in css
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

    list_response = client.get("/api/v1/ui/fascicoli", headers={"X-API-Key": "react-test-key"})
    detail_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}", headers={"X-API-Key": "react-test-key"})
    form_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/modifica", headers={"X-API-Key": "react-test-key"})
    new_form_response = client.get(
        "/api/v1/ui/fascicoli/nuovo",
        query_string={"tipo": "PENALE"},
        headers={"X-API-Key": "react-test-key"},
    )
    export_response = client.get("/api/v1/ui/fascicoli/export", headers={"X-API-Key": "react-test-key"})

    payload = list_response.get_json()
    detail = detail_response.get_json()
    form = form_response.get_json()
    new_form = new_form_response.get_json()
    export_payload = export_response.get_json()

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert form_response.status_code == 200
    assert new_form_response.status_code == 200
    assert export_response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is True
    assert payload["summary"]["total"] >= 1
    assert any(item["title"] == "Appello civile" for item in payload["items"])
    row = next(item for item in payload["items"] if item["title"] == "Appello civile")
    assert row["href"] == f"/fascicoli/{fascicolo.id}"
    assert row["editHref"] == f"/fascicoli/{fascicolo.id}/modifica"
    assert not row["href"].startswith("/app-v2/")
    assert detail["fascicolo"]["title"] == "Appello civile"
    assert any(party["name"] == "Zurich Ass.ni" and party["role"] == "Controparte" for party in detail["parties"])
    assert any(party["name"] == "Moscato Marco" and party["role"] == "Cliente / assistito" for party in detail["parties"])
    assert any(item["label"] == "Parti" and item["value"] == f"{len(detail['parties'])} soggetti" for item in detail["quality"])
    assert detail["actions"]["uploadDocument"].endswith("/documenti/carica")
    assert form["mode"] == "edit"
    assert form["detailHref"] == f"/fascicoli/{fascicolo.id}"
    assert form["backHref"] == f"/fascicoli/{fascicolo.id}"
    assert form["studio"]["leadLawyer"] == "Avv. Refactor"
    assert form["fascicolo"]["leadLawyer"] == "Avv. Refactor"
    assert form["guardrails"]["channel"] == "PCT_TELEMATICO"
    assert form["guardrails"]["requiredOpeningFields"] == ["titolo", "tipo", "oggetto", "tribunale"]
    assert new_form["guardrails"]["channel"] == "PDP_PENALE"
    assert new_form["guardrails"]["channelLabel"] == "PDP Penale"
    assert new_form["guardrails"]["warnings"][0]["code"] == "DOCUMENTI_PREDEPOSITO_DOPO_CREAZIONE"
    assert export_payload["formats"][0]["href"] == "/fascicoli/export.pdf"
    assert export_payload["presets"][-1]["href"] == "/fascicoli/archivio"


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
    payload = response.get_json()
    profile = {item["label"]: item["value"] for item in payload["profile"]}

    assert response.status_code == 200
    assert payload["fascicolo"]["leadLawyer"] == "Avv. Refactor"
    assert profile["Avv. referente"] == "Avv. Refactor"
    assert profile["Prossima udienza"] != "n.d."
    assert profile["Chiusura"] != "n.d."
    assert profile["Ultimo sync"] == imported_at_it
    assert payload["fascicolo"]["notes"] == f"Importato da PolisWeb il {imported_at_it}"
    assert payload["activities"][0]["notes"] == f"Evento acquisito il {imported_at_it}"
    assert imported_at not in str(payload)


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


def test_react_clienti_nuovo_e_soggetti_collegati_nav_api_lex_cf():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    new_page = Path("frontend/src/components/NuovoClientePage.tsx").read_text(encoding="utf-8")
    new_data = Path("frontend/src/clientiNuovoData.ts").read_text(encoding="utf-8")
    new_css = Path("frontend/src/components/NuovoClientePage.css").read_text(encoding="utf-8")
    soggetti_page = Path("frontend/src/components/SoggettiPage.tsx").read_text(encoding="utf-8")
    soggetti_data = Path("frontend/src/soggettiData.ts").read_text(encoding="utf-8")
    soggetti_css = Path("frontend/src/components/SoggettiPage.css").read_text(encoding="utf-8")
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
    assert "/api/cf/calcola" in new_page
    assert "/api/cf/decodifica" in new_page
    assert "Genera CF" in new_page
    assert 'name="provincia_nascita"' in new_page
    assert 'name="crea_preventivo_iniziale"' in new_page
    assert 'name="qualifica"' in new_page
    assert "Tipo soggetto processuale" in new_page
    assert "FloatingLex" in new_page
    assert 'context="clienti-nuovo"' in new_page
    assert "SoggettiPage" in soggetti_page
    assert 'context="soggetti"' in soggetti_page
    assert '@api_v1_react.get("/clienti/nuovo")' in api_source
    assert '@api_v1_react.get("/clienti/<id_cliente>/modifica")' in api_source
    assert '@api_v1_react.get("/soggetti/<id_soggetto>/modifica")' in api_source
    assert '@api_v1_react.get("/soggetti")' in api_source
    assert '"1" in form.getlist("crea_preventivo_iniziale")' in clienti_routes
    assert "provincia_nascita: str = \"\"" in soggetti_model
    assert ".iu-clienti-new-page" in new_css
    assert ".iu-cln-process-grid" in new_css
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
    assert "isWizardProPage?<WizardProPage/>" in app_source
    assert "WizardProPage" in app_source
    assert "getWizardProPage" in data_source
    assert "/api/v1/ui/wizard-pro" in data_source
    assert '@api_v1_react.get("/wizard-pro")' in api_source
    assert "build_react_wizard_pro_payload" in api_source
    assert "render_react_shell_response(\"wizard-pro\")" in route_source
    assert "Vista classica tecnica" in page_source
    assert 'method="post"' in page_source
    assert "item.startHref" in page_source
    assert "Termini collegati" in page_source
    assert "Chiedi a Lex" in page_source
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
