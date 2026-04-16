import json
from datetime import date, timedelta
from pathlib import Path

from pct.agenda import Agenda, TipoAppuntamento
from pct.auth import GestioneUtenti, RuoloUtente
from pct.calendar_sync import GestioneCalendarSync
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.scadenziario import GestioneScadenziario, TipoTermine
from pct.telematico_workflow import TelematicoWorkflowRepository
from web.app import create_app


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Operativo",
                    "avvocato": "Avv. Operativo",
                    "email": "studio@example.it",
                },
                "pec": {
                    "indirizzo": "studio@pec.example.it",
                    "smtp_host": "smtp.pec.example.it",
                },
                "smtp": {
                    "host": "smtp.office365.com",
                },
                "ai": {
                    "enabled": True,
                    "base_url": "http://127.0.0.1:11434/api",
                    "chat_model": "gemma3:1b",
                    "embed_model": "embeddinggemma:300m",
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
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "CALENDAR_SYNC_DB": str(tmp_path / "calendar_sync.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "GIURISPRUDENZA_DB": str(tmp_path / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(tmp_path / "workspace_intelligence.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
    }


def _seed_runtime(cfg: dict) -> str:
    utenti = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    utenti.crea(
        username="admin-operativo",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )
    utenti.crea(
        username="superadmin-operativo",
        password="Admin1234!",
        ruolo=RuoloUtente.SUPERADMIN,
        email="superadmin@example.com",
    )

    clienti = GestioneClienti(db_path=cfg["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Anna",
        cognome="Verdi",
        codice_fiscale="VRDNNA80A41H501Z",
        email="anna.verdi@example.com",
    )

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        titolo="Opposizione a decreto ingiuntivo",
        tipo=TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="1234",
        anno_rg=2026,
        oggetto="Opposizione e anatocismo",
    )

    agenda = Agenda(db_path=cfg["AGENDA_DB"])
    agenda.aggiungi(
        titolo="Udienza opposizione",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=f"{(date.today() + timedelta(days=2)).isoformat()}T09:30:00",
        durata_minuti=45,
        cliente=cliente.nome_completo,
        id_cliente=cliente.id,
        procedimento=fascicolo.numero,
        tribunale="Tribunale di Milano",
    )

    scadenziario = GestioneScadenziario(db_path=cfg["SCADENZIARIO_DB"])
    scadenziario.nuova(
        titolo="Deposita memoria integrativa",
        tipo=TipoTermine.DEPOSITO_MEMORIA,
        data_scadenza=(date.today() + timedelta(days=1)).isoformat(),
        id_fascicolo=fascicolo.id,
        perentorio=True,
    )

    sync = GestioneCalendarSync(db_path=cfg["CALENDAR_SYNC_DB"])
    profile = sync.create_profile(
        nome="Google Studio",
        provider="google",
        source_url="https://example.test/calendar.ics",
    )
    sync.update_profile(
        profile["id"],
        last_status="ok",
        last_sync_at=f"{date.today().isoformat()}T07:15:00",
        last_message="Creati 1, aggiornati 0, saltati 0, conflitti 0.",
    )

    repo = TelematicoWorkflowRepository(cfg["TELEMATICO_DB"])
    try:
        case = repo.upsert_case(
            practice_id=fascicolo.id,
            channel_family="ministero",
            service_code="polisweb_consultazione",
            office_name="Tribunale di Milano",
            register_type="RG",
            register_number="1234",
            register_year=2026,
            subject_name=cliente.nome_completo,
            counsel_name="Avv. Operativo",
            counsel_cf="CFAVVOCATO01",
            internal_status="manual_review_required",
            last_sync_at=f"{date.today().isoformat()}T08:10:00",
        )
        repo.add_event(
            case["id"],
            event_type="warning",
            title="Import incompleto dal portale",
            event_source="import",
            description="Manca il collegamento di due allegati da verificare.",
        )
    finally:
        repo.close()

    return fascicolo.id


def test_lex_operativo_e_control_tower_renderizzano(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    _seed_runtime(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-operativo", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get("/lex-operativo", follow_redirects=True)
        api = client.get("/api/lex-operativo")
        telematico = client.get("/telematico", follow_redirects=True)

    assert page.status_code == 200
    assert "Lex Fascicolo" in page.get_data(as_text=True)
    assert "Control Tower telematica" in page.get_data(as_text=True)
    assert api.get_json()["ok"] is True
    assert "fascicolo" in api.get_json()
    assert telematico.status_code == 200
    assert "Regia telematica operativa" in telematico.get_data(as_text=True)


def test_superadmin_product_surfaces_renderizzano(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    _seed_runtime(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "superadmin-operativo", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        stato = client.get("/admin/stato-installazione", follow_redirects=True)
        migrazione = client.get("/admin/assistente-migrazione", follow_redirects=True)
        salute = client.get("/admin/salute-sistema", follow_redirects=True)
        scorecard = client.get("/admin/lex-scorecard", follow_redirects=True)

    assert stato.status_code == 200
    assert "Stato installazione studio" in stato.get_data(as_text=True)
    assert migrazione.status_code == 200
    assert "Assistente migrazione dati" in migrazione.get_data(as_text=True)
    assert salute.status_code == 200
    assert "Salute sistema" in salute.get_data(as_text=True)
    assert scorecard.status_code == 200
    assert "Eval suite e scorecard Lex" in scorecard.get_data(as_text=True)
