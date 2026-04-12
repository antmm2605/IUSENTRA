from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.pdp_penale_workflow import PDPPenaleWorkflowRepository
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
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
    }


def _seed_penal_workspace(cfg: dict) -> tuple[str, str]:
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="admin-penale",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    clienti = GestioneClienti(db_path=cfg["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Mario",
        cognome="Rossi",
        codice_fiscale="RSSMRA80A01H501Z",
        email="mario.rossi@example.com",
    )

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        titolo="Procedimento penale demo",
        tipo=TipoFascicolo.PENALE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Procura della Repubblica di Palermo",
        numero_rg="12345",
        anno_rg=2026,
        giudice="Dott. Bianchi",
        sezione="GIP",
        avvocato_referente="Avv. Roberto Montagnese",
        tipo_procedimento="RGNR",
    )
    doc = fascicoli.aggiungi_documento(
        fascicolo.id,
        "nomina_difensore.pdf.p7m",
        TipoDocumento.PROCURA,
        b"%PDF nomina%",
        firmato=True,
        note="Nomina difensore per accesso atti PDP",
    )
    return fascicolo.id, doc.id


def test_workspace_pdp_penale_renderizza_link_nel_dettaglio(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    fasc_id, _ = _seed_penal_workspace(cfg)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-penale", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        detail = client.get(f"/fascicoli/{fasc_id}", follow_redirects=True)
        html = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert "Workflow PDP" in html
    assert "Workflow PDP Penale" in html


def test_workspace_pdp_penale_registra_case_documenti_accesso_pec_e_task(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    fasc_id, local_doc_id = _seed_penal_workspace(cfg)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-penale", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get(f"/fascicoli/{fasc_id}/penale/pdp", follow_redirects=True)
        assert page.status_code == 200
        assert "Workflow PDP Penale" in page.get_data(as_text=True)

        response = client.post(
            f"/fascicoli/{fasc_id}/penale/pdp/case",
            data={
                "office_name": "Procura della Repubblica di Palermo",
                "office_type": "Procura",
                "district": "Palermo",
                "register_type": "RGNR",
                "register_number": "12345",
                "register_year": "2026",
                "proceeding_type": "indagini_preliminari",
                "assisted_party_name": "Mario Rossi",
                "assisted_party_cf": "RSSMRA80A01H501Z",
                "defense_counsel_name": "Avv. Roberto Montagnese",
                "defense_counsel_cf": "MNTRRT00A00G273X",
                "nomination_status": "deposited",
                "access_status": "submitted",
                "import_status": "not_started",
                "current_ministry_status": "INVIATO",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        repo = PDPPenaleWorkflowRepository(cfg["PDP_PENALE_DB"])
        try:
            cases = repo.list_cases_for_practice(fasc_id)
            assert len(cases) == 1
            case_id = str(cases[0]["id"])

            link_doc = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/document-link",
                data={"local_doc_id": local_doc_id, "document_role": "nomination"},
                follow_redirects=True,
            )
            assert link_doc.status_code == 200

            access_request = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/access-request",
                data={
                    "request_type": "access_to_case_file",
                    "request_status": "submitted",
                    "request_reference": "REQ-001",
                    "ministry_status": "INVIATO",
                    "payment_required": "1",
                    "payment_amount": "16.00",
                    "download_available_until": "2026-04-15T18:00",
                },
                follow_redirects=True,
            )
            assert access_request.status_code == 200

            pec = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/pec",
                data={
                    "mailbox": "difensore@examplepec.it",
                    "sender": "procura@giustiziapec.it",
                    "subject": "Password accesso fascicolo",
                    "extracted_password": "PDP-ABC-123",
                    "download_available_until": "2026-04-15T18:00",
                    "contains_download_notice": "1",
                },
                follow_redirects=True,
            )
            assert pec.status_code == 200

            task = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/task",
                data={
                    "task_type": "download_case_file",
                    "title": "Scaricare fascicolo entro la finestra disponibile",
                    "priority": "urgent",
                    "due_at": "2026-04-15",
                },
                follow_redirects=True,
            )
            assert task.status_code == 200

            tasks = repo.list_tasks(case_id)
            assert len(tasks) == 1
            task_id = str(tasks[0]["id"])

            close_task = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/task/{task_id}/complete",
                data={"completion_note": "Download completato manualmente."},
                follow_redirects=True,
            )
            assert close_task.status_code == 200

            updated_case = repo.get_case(case_id)
            documents = repo.list_case_documents(case_id)
            requests = repo.list_access_requests(case_id)
            pec_messages = repo.list_pec_messages(case_id)
            updated_tasks = repo.list_tasks(case_id)
            events = repo.list_case_events(case_id)

            assert updated_case["nomination_status"] == "deposited"
            assert updated_case["access_status"] == "authorized"
            assert int(updated_case["pec_password_received"]) == 1
            assert updated_case["download_available_until"] == "2026-04-15T18:00"
            assert len(documents) == 1
            assert documents[0]["document_role"] == "nomination"
            assert len(requests) == 1
            assert requests[0]["request_reference"] == "REQ-001"
            assert len(pec_messages) == 1
            assert pec_messages[0]["extracted_password"] == "PDP-ABC-123"
            assert updated_tasks[0]["status"] == "done"
            assert any(event["event_type"] == "task_completed" for event in events)
        finally:
            repo.close()
