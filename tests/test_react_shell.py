from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from pct.agenda import Agenda, TipoAppuntamento
from pct.clienti import GestioneClienti, TipoCliente
from pct.email_client import CartellaEmail, EmailRicevuta, GestioneEmailRicevute, StatoEmail
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.messaggi import CanaleMsggio, ConfigMessaggistica, GestioneMessaggi, Messaggio, StatoMessaggio
from pct.preventivi import GestionePreventivi, StatoPreventivo, VocePreventivo
from pct.scadenziario import GestioneScadenziario, PrioritaTermine, TipoTermine
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


def test_react_shell_non_sostituisce_ui_storica_e_richiede_login(tmp_path: Path):
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
    assert ".iu-sidebar__nav{min-height:0;scrollbar-width:thin" in css


def test_react_api_bridge_richiede_autenticazione(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/bootstrap")

    assert response.status_code == 401
    assert response.get_json()["errore"] == "Autenticazione richiesta."


def test_react_api_bootstrap_espone_flag_senza_switch(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/bootstrap", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["product"] == "IUSENTRA"
    assert payload["shell"] == "react"
    assert payload["mounted_at"] == "/app-v2"
    assert payload["route_flags"]["replace_dashboard"] is False
    assert payload["route_flags"]["replace_telematico"] is False


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
