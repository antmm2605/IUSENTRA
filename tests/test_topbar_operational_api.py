import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from pct.agenda import Agenda, TipoAppuntamento
from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.email_client import EmailRicevuta, GestioneEmailRicevute, StatoEmail
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.scadenziario import GestioneScadenziario, PrioritaTermine, TipoTermine
from web.app import create_app


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Topbar Test",
                    "avvocato": "Avv. Test",
                    "email": "studio@example.it",
                    "pec": "studio@pec.example.it",
                }
            }
        ),
        encoding="utf-8",
    )


def _cfg_web(tmp_path: Path) -> dict:
    _write_studio_config(tmp_path / "config" / "studio.json")
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "STORAGE_MODE_DEFAULT": "JSON",
        "SQLITE_MODE": False,
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(tmp_path / "bootstrap_admin.json"),
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(tmp_path / "clienti" / "condivisioni.json"),
        "NOTE_FALDONE_DB": str(tmp_path / "clienti" / "note_faldone.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "PRACTICE_ENGINE_DB": str(tmp_path / "fascicoli" / "practice_engine.json"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "CALENDAR_SYNC_DB": str(tmp_path / "agenda" / "calendar_sync.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "TIMESHEET_DB": str(tmp_path / "timesheet" / "entries.json"),
        "TIME_TRACKING_DB": str(tmp_path / "timesheet" / "time_tracking.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione" / "parcelle.json"),
        "PAGAMENTI_DIR": str(tmp_path / "pagamenti"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(tmp_path / "email" / "ordinaria.json"),
        "NOTIFICHE_LOG": str(tmp_path / "notifiche" / "log.json"),
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "GLOBAL_SEARCH_INDEX": str(tmp_path / "search" / "global_search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "soggetti" / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "portale" / "import_pst"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
        "PORTALE_IMPORT_LOG_DB": str(tmp_path / "portale" / "import_log.json"),
        "VALIDATION_RUNS_DB": str(tmp_path / "intelligence" / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "workspace.json"),
        "LOCAL_AI_DB": str(tmp_path / "intelligence" / "local_ai.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "prefs.json"),
        "REDACTION_ASSISTANT_DB": str(tmp_path / "template_atti" / "redaction.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "WIZARD_PRO_DB": str(tmp_path / "wizard_pro" / "sessioni.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "UFFICI_GIUDIZIARI_DB": str(tmp_path / "uffici.json"),
        "REGINDE_DB": str(tmp_path / "reginde.json"),
        "STUDIO_NOME": "Studio Topbar Test",
    }


def _create_user(app, username: str, password: str, ruolo=RuoloUtente.AMMINISTRATORE, permessi_negati=None) -> None:
    with app.app_context():
        gestore = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
            bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
        )
        if not any(user.username == username for user in gestore.tutti()):
            gestore.crea(
                username=username,
                password=password,
                ruolo=ruolo,
                email=f"{username}@example.it",
                nome_completo=f"Operatore {username}",
                permessi_negati=permessi_negati or [],
                must_change_password=False,
            )


def _login(client, username="operatore", password="Operatore123!") -> None:
    response = client.post("/login", data={"username": username, "password": password}, follow_redirects=True)
    assert response.status_code == 200


def _seed_domain(app) -> tuple[str, str]:
    today = datetime.now().date()
    clienti = GestioneClienti(app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Maria", cognome="Verdi")
    fascicoli = GestioneFascicoli(
        app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Recupero credito Alfa",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        numero_rg="1234",
        anno_rg=2026,
    )
    GestioneScadenziario(app.config["SCADENZIARIO_DB"]).nuova(
        "Deposito memoria istruttoria",
        TipoTermine.DEPOSITO_ATTO,
        today.isoformat(),
        id_fascicolo=fascicolo.id,
        priorita=PrioritaTermine.CRITICA,
        perentorio=True,
    )
    Agenda(app.config["AGENDA_DB"]).aggiungi(
        "Udienza precisazione conclusioni",
        TipoAppuntamento.UDIENZA,
        datetime.combine(today, datetime.min.time()).replace(hour=10).isoformat(),
        cliente=cliente.nome_completo,
        id_cliente=cliente.id,
        procedimento="RG 1234/2026",
    )
    GestioneEmailRicevute(app.config["EMAIL_CASELLA_DB"]).aggiungi(
        EmailRicevuta(
            id="pec-1",
            stato=StatoEmail.NON_LETTA,
            oggetto="Comunicazione cancelleria",
            mittente="cancelleria@example.it",
            data=datetime.now().isoformat(),
            corpo_testo="Avviso operativo reale",
        )
    )
    return cliente.id, fascicolo.id


def test_topbar_search_valida_query_auth_e_permessi(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _create_user(app, "operatore", "Operatore123!")
    _create_user(
        app,
        "bloccato",
        "Bloccato123!",
        ruolo=RuoloUtente.SEGRETERIA,
        permessi_negati=[
            "fascicoli.leggi",
            "clienti.leggi",
            "agenda.leggi",
            "scadenziario.leggi",
            "messaggi.leggi",
        ],
    )
    _seed_domain(app)

    with app.test_client() as client:
        assert client.get("/api/search/global?q=Recupero").status_code == 401
        _login(client)
        too_short = client.get("/api/search/global?q=a")
        assert too_short.status_code == 400
        too_long = client.get("/api/search/global?q=" + ("x" * 140))
        assert too_long.status_code == 400
        response = client.get("/api/search/global?q=Recupero&limit=8")
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["ok"] is True
        assert any(item["type"] == "case" and "Recupero" in item["title"] for item in payload["results"])

    with app.test_client() as client:
        _login(client, "bloccato", "Bloccato123!")
        denied = client.get("/api/search/global?q=Recupero")
        assert denied.status_code == 403


def test_topbar_today_notifications_deadlines_recent_and_timer(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    _create_user(app, "operatore", "Operatore123!")
    cliente_id, fascicolo_id = _seed_domain(app)

    with app.test_client() as client:
        _login(client)
        today = client.get("/api/dashboard/today").get_json()
        assert today["summary"]["hearingsToday"] == 1
        assert today["summary"]["deadlinesToday"] == 1
        assert today["summary"]["unreadCommunications"] == 1

        deadlines = client.get("/api/deadlines/quick-summary").get_json()
        assert deadlines["summary"]["today"] == 1
        assert deadlines["summary"]["urgent"] >= 1
        assert deadlines["deadlines"][0]["caseId"] == fascicolo_id

        notifications_response = client.get("/api/notifications")
        notifications = notifications_response.get_json()
        assert notifications_response.status_code == 200
        assert notifications["unreadCount"] >= 1
        first_id = notifications["items"][0]["id"]
        read_response = client.patch(f"/api/notifications/{quote(first_id, safe='')}/read")
        assert read_response.status_code == 200
        read_all = client.patch("/api/notifications/read-all")
        assert read_all.status_code == 200
        assert read_all.get_json()["unreadCount"] == 0

        recent_empty = client.get("/api/recent")
        assert recent_empty.status_code == 200
        tracked = client.post("/api/recent", json={"entityType": "case", "entityId": fascicolo_id})
        assert tracked.status_code == 200
        assert tracked.get_json()["items"][0]["href"] == f"/fascicoli/{fascicolo_id}"

        active = client.get("/api/time-tracking/active")
        assert active.status_code == 200
        assert active.get_json()["timer"] is None
        started = client.post(
            "/api/time-tracking/start",
            json={
                "caseId": fascicolo_id,
                "clientId": cliente_id,
                "activityType": "research",
                "description": "Studio fascicolo",
            },
        )
        assert started.status_code == 200
        timer_id = started.get_json()["timer"]["id"]
        conflict = client.post("/api/time-tracking/start", json={"activityType": "call"})
        assert conflict.status_code == 409
        paused = client.patch(f"/api/time-tracking/{timer_id}/pause")
        assert paused.status_code == 200
        assert paused.get_json()["timer"]["status"] == "paused"
        resumed = client.patch(f"/api/time-tracking/{timer_id}/resume")
        assert resumed.status_code == 200
        assert resumed.get_json()["timer"]["status"] == "running"
        stopped = client.patch(f"/api/time-tracking/{timer_id}/stop")
        assert stopped.status_code == 200
        assert stopped.get_json()["timer"]["status"] == "stopped"
        assert stopped.get_json()["timeEntry"]["href"] == "/timesheet"
