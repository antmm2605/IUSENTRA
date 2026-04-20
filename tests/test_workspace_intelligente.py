from datetime import date, timedelta
from pathlib import Path

from pct.agenda import Agenda, TipoAppuntamento
from pct.auth import GestioneUtenti, RuoloUtente
from pct.calendar_sync import GestioneCalendarSync
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, StatoFascicolo, TipoDocumento, TipoFascicolo
from pct.giurisprudenza import GestioneGiurisprudenza
from pct.scadenziario import GestioneScadenziario, TipoTermine
from pct.workspace_intelligente import WorkspaceIntelligenteService
from web.app import create_app


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
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(tmp_path / "workspace_intelligence.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
    }


def _seed_workspace(tmp_path: Path):
    tomorrow = date.today() + timedelta(days=1)
    due_day = date.today() + timedelta(days=2)

    clienti = GestioneClienti(db_path=str(tmp_path / "clienti.json"))
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Anna",
        cognome="Verdi",
        codice_fiscale="VRDNNA80A41H501Z",
        email="anna.verdi@example.com",
    )

    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = fascicoli.nuovo(
        titolo="Opposizione a decreto ingiuntivo banca",
        tipo=TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="1234",
        anno_rg=2026,
        oggetto="Opposizione a decreto ingiuntivo e anatocismo",
    )

    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    agenda.aggiungi(
        titolo="Riunione strategica opposizione DI",
        tipo=TipoAppuntamento.RIUNIONE,
        data_ora=f"{tomorrow.isoformat()}T10:00:00",
        durata_minuti=60,
        cliente=cliente.nome_completo,
        id_cliente=cliente.id,
        procedimento=fascicolo.numero,
    )

    scadenziario = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = scadenziario.nuova(
        titolo="Deposita comparsa di costituzione",
        tipo=TipoTermine.DEPOSITO_MEMORIA,
        data_scadenza=due_day.isoformat(),
        id_fascicolo=fascicolo.id,
        perentorio=True,
    )
    scadenziario.aggiorna(
        scadenza.id,
        judicial_office_name="Tribunale di Milano",
        judicial_office_patron_name="Sant Ambrogio",
        judicial_office_patron_day=7,
        judicial_office_patron_month=12,
        judicial_office_source_url="https://www.giustizia.it/",
        legal_due_at=f"{due_day.isoformat()}T23:59:00",
        operational_due_at=f"{tomorrow.isoformat()}T18:00:00",
        deadline_profile_code="TERM_30_DAYS",
        trace_json='["Escluso il giorno iniziale", "Proroga finale non necessaria"]',
    )

    sync = GestioneCalendarSync(db_path=str(tmp_path / "calendar_sync.json"))
    profile = sync.create_profile(
        nome="Google Studio",
        provider="google",
        source_url="https://example.test/calendar.ics",
    )
    sync.update_profile(
        profile["id"],
        last_status="ok",
        last_sync_at=f"{date.today().isoformat()}T06:00:00",
        last_message="Creati 1, aggiornati 0, saltati 0, conflitti 0.",
    )

    giurisprudenza = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    giurisprudenza.salva(
        {
            "titolo": "Cassazione sull'opposizione a decreto ingiuntivo bancario",
            "source_system": "cassazione",
            "area": "Civile",
            "branca": "Obbligazioni e contratti",
            "sottobranca": "Nullita / annullabilita / risoluzione / rescissione",
            "microtema": "decreto ingiuntivo",
            "numero_provvedimento": "1234/2026",
            "data_deposito": date.today().isoformat(),
            "massima": "Nei rapporti bancari l'opposizione richiede prova puntuale dei fatti estintivi.",
        }
    )

    return fascicolo, agenda, scadenziario, fascicoli, sync, giurisprudenza


def test_workspace_intelligente_aggrega_moduli(tmp_path: Path):
    fascicolo, agenda, scadenziario, fascicoli, sync, giurisprudenza = _seed_workspace(tmp_path)

    service = WorkspaceIntelligenteService(
        agenda=agenda,
        scadenziario=scadenziario,
        fascicoli=fascicoli,
        calendar_sync=sync,
        giurisprudenza=giurisprudenza,
    )

    overview = service.panoramica(horizon_days=14)

    assert overview["summary"]["scadenze_urgenti"] >= 1
    assert overview["summary"]["appuntamenti_orizzonte"] >= 1
    assert overview["summary"]["fascicoli_attenzionati"] >= 1
    assert overview["sync_profiles"][0]["provider_label"] == "Google Calendar"
    assert any(item["id"] == fascicolo.id for item in overview["fascicoli_hot"])


def test_workspace_intelligente_propone_sentenza_per_fascicolo(tmp_path: Path):
    fascicolo, agenda, scadenziario, fascicoli, sync, giurisprudenza = _seed_workspace(tmp_path)

    service = WorkspaceIntelligenteService(
        agenda=agenda,
        scadenziario=scadenziario,
        fascicoli=fascicoli,
        calendar_sync=sync,
        giurisprudenza=giurisprudenza,
    )

    quadro = service.per_fascicolo(fascicolo)

    assert quadro["has_items"] is True
    assert quadro["giurisprudenza"]
    assert "decreto ingiuntivo" in quadro["giurisprudenza"][0]["titolo"].lower()
    assert quadro["next_actions"]


def test_workspace_intelligente_calcola_presidio_reale_per_pratica_definita(tmp_path: Path):
    fascicolo, agenda, scadenziario, fascicoli, sync, giurisprudenza = _seed_workspace(tmp_path)
    scadenze = scadenziario.tutte(id_fascicolo=fascicolo.id, solo_aperte=True)
    for item in scadenze:
        scadenziario.completa(item.id)

    fascicoli.aggiungi_documento(
        fascicolo.id,
        nome_file="SentenzaDefinitiva_33581101.pdf.p7m",
        tipo=TipoDocumento.SENTENZA,
        contenuto=b"sentenza definitiva",
        fonte_documento="PORTALE_TELEMATICO",
        nome_portale="SentenzaDefinitiva_33581101.pdf.p7m",
        classificazione_portale="SENTENZA",
        tipo_atto_portale="Sentenza definitiva",
        servizio_portale="DocumentiFascicolo",
        mittente_portale="cancelleria@tribunale.palmi.giustiziapec.it",
        data_deposito_portale="2026-04-10",
        id_documento_portale="DOC-SENT-01",
    )
    fascicoli.cambia_stato(fascicolo.id, StatoFascicolo.DEFINITO, note="Pratica definita con sentenza")
    fascicolo = fascicoli.get(fascicolo.id)
    fascicolo.data_prima_udienza = "2024-12-12"
    fascicoli._salva()

    service = WorkspaceIntelligenteService(
        agenda=agenda,
        scadenziario=scadenziario,
        fascicoli=fascicoli,
        calendar_sync=sync,
        giurisprudenza=giurisprudenza,
    )

    quadro = service.per_fascicolo(fascicolo)

    assert quadro["presidio"]["progress_percent"] == 100
    assert quadro["presidio"]["summary"] == "Pratica chiusa e coerente"
    assert quadro["presidio"]["udienza_passata_non_allineata"] is False
    assert quadro["provvedimenti"]
    assert not any("udienza da portale" in action.lower() for action in quadro["next_actions"])
    assert not any("preparare subito" in action.lower() for action in quadro["next_actions"])


def test_workspace_intelligente_riconosce_stato_chiuso_legacy_e_deduplica_provvedimenti(tmp_path: Path):
    fascicolo, agenda, scadenziario, fascicoli, sync, giurisprudenza = _seed_workspace(tmp_path)
    for idx in range(2):
        fascicoli.aggiungi_documento(
            fascicolo.id,
            nome_file=f"SentenzaDefinitiva_33581101_dup_{idx}.pdf.p7m",
            tipo=TipoDocumento.SENTENZA,
            contenuto=b"sentenza definitiva",
            fonte_documento="PORTALE_TELEMATICO",
            nome_portale="SentenzaDefinitiva_33581101.pdf.p7m",
            classificazione_portale="SENTENZA",
            tipo_atto_portale="Sentenza definitiva",
            servizio_portale="DocumentiFascicolo",
            mittente_portale="cancelleria@tribunale.palmi.giustiziapec.it",
            data_deposito_portale="2026-04-10",
            id_documento_portale=f"DOC-SENT-LEGACY-{idx}",
        )
    fascicoli.cambia_stato(fascicolo.id, StatoFascicolo.DEFINITO, note="Pratica definita con sentenza")
    fascicolo = fascicoli.get(fascicolo.id)
    fascicolo.stato = "DEFINITO"

    service = WorkspaceIntelligenteService(
        agenda=agenda,
        scadenziario=scadenziario,
        fascicoli=fascicoli,
        calendar_sync=sync,
        giurisprudenza=giurisprudenza,
    )
    quadro = service.per_fascicolo(fascicolo)

    assert quadro["presidio"]["stato_chiusura"] is True
    assert quadro["presidio"]["progress_percent"] >= 80
    assert len(quadro["provvedimenti"]) == 1


def test_workspace_intelligente_web_e_fascicolo_renderizzano(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    ).crea(
        username="admin-workspace",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )
    fascicolo, *_ = _seed_workspace(tmp_path)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-workspace", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        workspace = client.get("/workspace-intelligente", follow_redirects=True)
        fascicolo_detail = client.get(f"/fascicoli/{fascicolo.id}", follow_redirects=True)

    workspace_html = workspace.get_data(as_text=True)
    fascicolo_html = fascicolo_detail.get_data(as_text=True)

    assert workspace.status_code == 200
    assert "Cabina Intelligente" in workspace_html
    assert "Fascicoli attenzionati" in workspace_html
    assert fascicolo_detail.status_code == 200
    assert "Quadro intelligente fascicolo" in fascicolo_html
    assert "Affidabilita' controlli pratica" in fascicolo_html
    assert "Provvedimenti e sentenze utili" in fascicolo_html
