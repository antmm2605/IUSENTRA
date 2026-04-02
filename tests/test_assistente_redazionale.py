from types import SimpleNamespace

from pct.assistente_redazionale import AssistenteRedazionale
from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.compilatore_atti import prefill_payload
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.pst_catalog import PST_WEB_SERVICES_DOC_VERSION
from web.app import create_app


def _fake_utente():
    return SimpleNamespace(
        id="USR123",
        username="admin",
        nome_completo="Avv. Mario Rossi",
    )


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
    }


def test_assistente_redazionale_civile_restituisce_schema_e_blocchi_guidati(tmp_path):
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti.json"))
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi", codice_fiscale="RSSMRA80A01H501Z")
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = fascicoli.nuovo(
        titolo="Comparsa Rossi c. Alfa",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        controparte="Alfa S.r.l.",
        id_cliente=cliente.id,
    )
    payload = prefill_payload(
        "CIV_COM_001",
        fascicolo=fasc,
        cliente=cliente,
        utente=_fake_utente(),
        config={"STUDIO_AVVOCATO": "Avv. Mario Rossi", "SMTP_FROM": "studio@examplepec.it"},
    )
    payload.update(
        {
            "proceeding_number": "RG 1025/2024",
            "position_on_facts": "Si contestano integralmente i fatti allegati nell'atto di citazione.",
            "procedural_exceptions": "Si eccepisce incompetenza territoriale ove ritenuta fondata.",
            "merit_exceptions": "Nel merito si nega la sussistenza del credito azionato.",
            "requests_or_conclusions": "Rigettare le domande attoree con vittoria di spese.",
            "attachments_list": "procura_alle_liti.pdf\nindice_allegati.pdf",
        }
    )

    analysis = AssistenteRedazionale(
        audit_db_path=str(tmp_path / "assist_audit.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    ).analyze(
        "CIV_COM_001",
        payload,
        fascicolo=fasc,
        cliente=cliente,
        utente=_fake_utente(),
    )

    assert analysis.profile["channel"] == "PCT_TELEMATICO"
    assert analysis.schema_channel["supports_xml"] is True
    assert analysis.profile["registry_suggestion"] == "RG"
    assert analysis.semaforo["tecnico_ministeriale"] == "ok"
    assert any(section["key"] == "parti" for section in analysis.sections)
    assert analysis.snapshot["pst_webservices_doc_version"] == PST_WEB_SERVICES_DOC_VERSION


def test_api_assistente_redazionale_restituisce_riepilogo_intelligente(tmp_path):
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
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Elisa", cognome="Bianchi", codice_fiscale="BNCLSE80A41H501Q")
    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc = fascicoli.nuovo(
        titolo="Ricorso TAR demo",
        tipo=TipoFascicolo.AMMINISTRATIVO,
        tribunale="TAR Calabria",
        controparte="Comune di Palmi",
        id_cliente=cliente.id,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/template-atti/api/assistente-redazionale/AMM_RIC_001",
            data={
                "id_cliente": cliente.id,
                "id_fascicolo": fasc.id,
                "model_code": "AMM_RIC_001",
                "title": "Ricorso al TAR",
                "area": "AMMINISTRATIVO",
                "act_type": "Ricorso al TAR",
                "case_id": fasc.id,
                "matter": "AMMINISTRATIVO",
                "recipient_or_court": "TAR Calabria",
                "client_or_sender": cliente.nome_completo,
                "counterparty_or_recipient": "Comune di Palmi",
                "lawyer": "Avv. Mario Rossi",
                "subject": "Impugnazione provvedimento amministrativo",
                "facts": "Il ricorrente impugna il provvedimento lesivo notificato in data 1 aprile.",
                "requests_or_conclusions": "Annullare il provvedimento impugnato e adottare le misure cautelari richieste.",
                "place": "Palmi",
                "document_date": "2026-04-02",
                "signature": "Avv. Mario Rossi",
                "attachments_list": "procura.pdf\nrelata_notifica.pdf",
                "author_user_id": "USR1",
                "version": "1.0",
                "status": "BOZZA",
                "competent_tar": "TAR Calabria",
                "claimant": cliente.nome_completo,
                "respondent_administration": "Comune di Palmi",
                "challenged_administrative_act": "Determinazione n. 55/2026",
                "legal_arguments": "Violazione di legge ed eccesso di potere.",
            },
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["analysis"]["profile"]["channel"] == "PAT_AMMINISTRATIVO"
    assert data["analysis"]["schema_channel"]["label"] == "Processo amministrativo telematico"
    assert "next_steps" in data["analysis"]
    assert data["analysis"]["snapshot"]["pst_webservices_doc_version"] == PST_WEB_SERVICES_DOC_VERSION


def test_compila_template_post_usa_id_fascicolo_del_form_anche_se_query_vuota(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    utente = gu.crea(
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
        titolo="Causa di risarcimento danni",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1234",
        anno_rg=2026,
        controparte="SeiDonne S.a.s.",
        id_cliente=cliente.id,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/template-atti/compila/STR_DIFF_001?model_code=STR_DIFF_001&id_cliente={cliente.id}&id_fascicolo=",
            data={
                "id_cliente": cliente.id,
                "id_fascicolo": fasc.id,
                "model_code": "STR_DIFF_001",
                "title": "Diffida",
                "area": "STRAGIUDIZIALE",
                "act_type": "Diffida",
                "case_id": fasc.id,
                "matter": "STRAGIUDIZIALE",
                "recipient_or_court": "Invio / notifica a mezzo PEC",
                "client_or_sender": cliente.nome_completo,
                "counterparty_or_recipient": "SeiDonne S.a.s.",
                "lawyer": "Avv. Mario Rossi",
                "subject": "Diffida",
                "facts": "La controparte permane inadempiente nonostante i precedenti solleciti.",
                "requests_or_conclusions": "Si intima l'adempimento entro il termine assegnato.",
                "place": "Palmi",
                "document_date": "2026-04-02",
                "signature": "Avv. Mario Rossi",
                "attachments_list": "contratto.pdf\npec_precedente.eml",
                "author_user_id": utente.id,
                "version": "1.0",
                "status": "BOZZA",
                "sender": cliente.nome_completo,
                "recipient": "seidonnesas@legalmail.it",
                "breach_description": "Mancato pagamento del corrispettivo dovuto.",
                "specific_request": "Versare quanto dovuto entro il termine indicato.",
                "deadline_assigned": "2026-04-03",
                "final_warning": "In difetto si procedera senza ulteriore avviso.",
            },
        )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Bozza professionale" in html
    assert "Campo redazionale obbligatorio: case_id" not in html
    assert "Pratica Collegata obbligatorio." not in html
