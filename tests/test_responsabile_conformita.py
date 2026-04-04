from types import SimpleNamespace

from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.preventivi import GestionePreventivi, TipoVoce, VocePreventivo
from pct.responsabile_conformita import build_fascicolo_compliance_summary
from pct.scadenziario import GestioneScadenziario, TipoTermine
from web.app import create_app


def _cfg_web(tmp_path):
    return {
        "TESTING": True,
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "REDACTION_ASSISTANT_DB": str(tmp_path / "assistente_redazionale.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi.json"),
    }


def test_responsabile_conformita_citazione_distinge_quattro_aree_e_blocchi(tmp_path):
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti.json"))
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
    )
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = fascicoli.nuovo(
        titolo="Atto di citazione Rossi c. Alfa",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        controparte="Alfa S.r.l.",
        id_cliente=cliente.id,
    )

    preventivo = SimpleNamespace(
        id="prev-1",
        id_pratica="atto_citazione",
        oggetto="Atto di citazione",
    )

    summary = build_fascicolo_compliance_summary(
        fascicolo=fasc,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=None,
        config={"STUDIO_AVVOCATO": "Avv. Mario Rossi"},
        utente=SimpleNamespace(username="avv.rossi", nome_completo="Avv. Mario Rossi"),
        office_cache_path=str(tmp_path / "uffici.json"),
        parti=[],
    )

    assert summary["available"] is True
    assert summary["general"]["state"] == "blocco"
    assert summary["general"]["score"] < 100
    assert set(summary["sections"].keys()) == {"processuale", "documentale", "tecnico_pst", "redazionale"}
    assert summary["sections"]["processuale"]["blocking_count"] >= 1
    assert summary["sections"]["documentale"]["blocking_count"] >= 1
    assert summary["sections"]["redazionale"]["has_items"] is True
    assert summary["action_gates"]["generate_final_act"]["allowed"] is False
    assert summary["action_gates"]["generate_xml"]["applicable"] is True
    assert summary["action_gates"]["generate_xml"]["allowed"] is False
    assert summary["action_gates"]["prepare_deposit"]["allowed"] is False
    assert any(issue.get("code") == "citazione_udienza_mancante" for issue in summary["blocking_issues"])
    assert any(correction.get("service") for correction in summary["corrections"])
    assert any("prima comparizione" in issue["title"].lower() or "notificazione" in issue["detail"].lower() for issue in summary["blocking_issues"])


def test_dettaglio_fascicolo_mostra_responsabile_conformita(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    clienti = GestioneClienti(db_path=cfg["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Francesco",
        cognome="Stillitano",
        codice_fiscale="STLFNC80A01H501Q",
    )
    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc = fascicoli.nuovo(
        titolo="Atto di citazione demo",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        controparte="Beta S.r.l.",
        id_cliente=cliente.id,
    )
    preventivi = GestionePreventivi(cfg["PREVENTIVI_DB"])
    preventivo = preventivi.crea_preventivo(
        id_cliente=cliente.id,
        oggetto="Atto di citazione",
        voci=[VocePreventivo(descrizione="Compenso", importo=1200.0, tipo=TipoVoce.ONORARIO)],
        creato_da="avv.rossi",
        id_pratica="atto_citazione",
        area_pratica="Civile",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
    )
    preventivi.collega_fascicolo(fasc.id, id_preventivo=preventivo.id)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fasc.id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Profilo fascicolo" in html
    assert "Documenti fascicolo" in html
    assert "Attività processuali" in html
    assert "Udienze e scadenze" in html
    assert "Comunicazioni di cancelleria" in html
    assert "Istanze" in html
    assert "Responsabile di conformita" in html
    assert "Deposito non pronto" in html
    assert "Prossimo passo consigliato" in html
    assert "Checklist operativa del deposito" in html
    assert "Workflow deposito" in html
    assert "Controlli processuali" in html
    assert "Controlli documentali" in html
    assert "Controlli tecnici PST" in html
    assert "Controlli redazionali" in html
    assert "Manca la data della prima comparizione" in html
    assert "Imposta prima udienza" in html
    assert "Inserisci data notifica" in html
    assert "Carica procura" in html
    assert "Apri redattore guidato" in html


def test_dettaglio_fascicolo_separa_istanze_e_scadenze(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc = fascicoli.nuovo(
        titolo="Comparsa e istanza istruttoria",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1234",
        anno_rg=2026,
    )
    fascicoli.aggiungi_documento(
        fasc.id,
        "istanza_fissazione_udienza.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"istanza",
        note="Istanza di fissazione udienza",
    )

    scadenziario = GestioneScadenziario(cfg["SCADENZIARIO_DB"])
    scadenziario.nuova(
        titolo="Deposita memoria 171-ter",
        tipo=TipoTermine.DEPOSITO_MEMORIA,
        data_scadenza="2026-05-10",
        id_fascicolo=fasc.id,
        descrizione="Termine processuale istruttorio",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fasc.id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Deposita memoria 171-ter" in html
    assert "istanza_fissazione_udienza.pdf" in html


def test_responsabile_conformita_non_blocca_data_notifica_se_strutturata(tmp_path):
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti.json"))
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
    )
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = fascicoli.nuovo(
        titolo="Atto di citazione Rossi c. Alfa",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        controparte="Alfa S.r.l.",
        id_cliente=cliente.id,
        data_notifica_citazione="2026-04-03",
    )

    preventivo = SimpleNamespace(id="prev-1", id_pratica="atto_citazione", oggetto="Atto di citazione")
    summary = build_fascicolo_compliance_summary(
        fascicolo=fasc,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=None,
        config={"STUDIO_AVVOCATO": "Avv. Mario Rossi"},
        utente=SimpleNamespace(username="avv.rossi", nome_completo="Avv. Mario Rossi"),
        office_cache_path=str(tmp_path / "uffici.json"),
        parti=[],
    )

    assert all(issue.get("code") != "citazione_data_notifica_non_strutturata" for issue in summary["blocking_issues"])
