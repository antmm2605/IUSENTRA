import io
import zipfile
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.email_client import EmailRicevuta, GestioneEmailRicevute
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
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
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

        detail = client.get(f"/fascicoli/{fasc_id}?_legacy=1", follow_redirects=True)
        html = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert "Workflow PDP" in html
    assert "Workflow PDP Penale" in html


def test_dettaglio_penale_importato_nasconde_navigazioni_portale_non_coerenti(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    fasc_id, _ = _seed_penal_workspace(cfg)
    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicoli.aggiorna(fasc_id, source="PDP")

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-penale", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        detail = client.get(f"/fascicoli/{fasc_id}?_legacy=1", follow_redirects=True)
        html = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert "Workflow PDP" in html
    assert "Consulta su PDP" not in html
    assert 'data-bs-target="#modalNavigaPst"' not in html
    assert "Acquisisci fascicolo" not in html


def test_workflow_pdp_apre_acquisizione_guidata_nel_contesto_del_fascicolo(tmp_path: Path):
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

        page = client.get(f"/fascicoli/{fasc_id}/penale/pdp", follow_redirects=True)
        html = page.get_data(as_text=True)

    assert page.status_code == 200
    assert f"/portali/pdp/acquisizione?id_fasc={fasc_id}" in html
    assert "Apri PDP ufficiale" not in html
    assert "Acquisizione guidata" in html


def test_acquisizione_guidata_pdp_con_fascicolo_collegato_mostra_workflow(tmp_path: Path):
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

        page = client.get(f"/portali/pdp/acquisizione?id_fasc={fasc_id}", follow_redirects=True)
        html = page.get_data(as_text=True)

    assert page.status_code == 200
    assert "Acquisizione guidata dentro il workflow PDP" in html
    assert f"/fascicoli/{fasc_id}/penale/pdp" in html
    assert 'data-initial-target="' + fasc_id + '"' in html
    assert 'value="update_existing" checked' in html


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


def test_workspace_pdp_penale_completa_flusso_generazione_deposito_sync_e_import(
    tmp_path: Path,
    monkeypatch,
):
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

        create_case = client.post(
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
                "access_status": "draft",
                "import_status": "not_started",
            },
            follow_redirects=True,
        )
        assert create_case.status_code == 200

        repo = PDPPenaleWorkflowRepository(cfg["PDP_PENALE_DB"])
        try:
            case_id = str(repo.list_cases_for_practice(fasc_id)[0]["id"])

            link_doc = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/document-link",
                data={"local_doc_id": local_doc_id, "document_role": "nomination"},
                follow_redirects=True,
            )
            assert link_doc.status_code == 200

            generated = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/generate-request",
                follow_redirects=True,
            )
            assert generated.status_code == 200

            fascicoli = GestioneFascicoli(
                db_path=cfg["FASCICOLI_DB"],
                documents_dir=cfg["FASCICOLI_DOCS"],
                archive_dir=cfg["FASCICOLI_ARCH"],
            )
            fascicolo = fascicoli.get(fasc_id)
            generated_doc = next(
                doc for doc in fascicolo.documenti
                if doc.nome.startswith("richiesta_accesso_pdp_")
            )
            fascicoli.segna_firmato(fasc_id, generated_doc.id)
            generated_doc.firmato_digitalmente = True

            import pct.pdp as pdp_module

            class _FakePDPClient:
                def deposita_atto(self, **kwargs):
                    assert kwargs["numero_rg"] == "12345"
                    return {
                        "codiceEsito": "0",
                        "descrizioneEsito": "Deposito accettato dal sistema PDP",
                        "idDeposito": "PDP-DEP-001",
                        "dataDeposito": "2026-04-12T10:30",
                        "stato": "INVIATO",
                    }

            monkeypatch.setattr(pdp_module, "crea_client_pdp", lambda demo=False: _FakePDPClient())

            deposit = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/deposit",
                data={
                    "local_doc_id": generated_doc.id,
                    "tipo_atto": "RICHIESTA",
                    "oggetto": "Richiesta accesso atti procedimento 12345/2026",
                    "confirm_lawyer_review": "1",
                },
                follow_redirects=True,
            )
            assert deposit.status_code == 200

            ge = GestioneEmailRicevute(db_path=cfg["EMAIL_CASELLA_DB"])
            ge.aggiungi(
                EmailRicevuta(
                    id="mail-pdp-001",
                    mittente="procura@giustiziapec.it",
                    destinatari="difensore@examplepec.it",
                    oggetto="Password accesso fascicolo RGNR 12345/2026",
                    data="2026-04-12T11:00:00",
                    corpo_testo=(
                        "Procura della Repubblica di Palermo. "
                        "Password di accesso: PDP-ABC-123. "
                        "Documenti disponibili fino al 15/04/2026 18:30."
                    ),
                    message_id="<pdp-mail-001@examplepec.it>",
                )
            )

            sync_pec = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/sync-pec",
                follow_redirects=True,
            )
            assert sync_pec.status_code == 200

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr("verbale_udienza.pdf", b"%PDF-verbale")
                zf.writestr("decreto_giudizio.pdf.p7m", b"FAKE-P7M")
            zip_buffer.seek(0)

            imported = client.post(
                f"/fascicoli/{fasc_id}/penale/pdp/case/{case_id}/import-download",
                data={
                    "note_importazione": "Pacchetto ufficiale scaricato dal PDP",
                    "files": (zip_buffer, "fascicolo_pdp.zip"),
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert imported.status_code == 200

            updated_case = repo.get_case(case_id)
            requests = repo.list_access_requests(case_id)
            pec_messages = repo.list_pec_messages(case_id)
            module_documents = repo.list_case_documents(case_id)
            tasks = repo.list_tasks(case_id)
            events = repo.list_case_events(case_id)

            assert updated_case["access_status"] == "authorized"
            assert updated_case["current_ministry_status"] in {"INVIATO", "ACCETTATO"}
            assert updated_case["download_available_until"] == "2026-04-15T18:30"
            assert updated_case["import_status"] == "completed"
            assert any(row["request_status"] in {"authorized", "downloaded"} for row in requests)
            assert any(row["request_reference"] == "PDP-DEP-001" for row in requests)
            assert len(pec_messages) == 1
            assert pec_messages[0]["extracted_password"] == "PDP-ABC-123"
            assert any(doc["document_role"] == "access_request" for doc in module_documents)
            assert any(doc["document_role"] == "hearing_minutes" for doc in module_documents)
            assert any(doc["document_role"] == "decree" for doc in module_documents)
            assert any(task["task_type"] == "download_case_file" for task in tasks)
            assert any(event["event_type"] == "deposit_submitted" for event in events)
            assert any(event["event_type"] == "download_imported" for event in events)
        finally:
            repo.close()


def test_acquisizione_guidata_pdp_riusa_fascicolo_esistente_e_apre_workflow(tmp_path: Path):
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

        response = client.post(
            "/api/portali/pdp/acquisizione/import",
            json={
                "selection": {
                    "external_id": "PALERMO:12345:2026:RGNR",
                    "numero": "12345",
                    "anno": 2026,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Procura della Repubblica di Palermo",
                    "procedimento": "RGNR",
                    "stato": "PENDENTE",
                    "oggetto": "Procedimento penale demo",
                    "parti": ["Mario Rossi"],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "12345",
                        "anno_rg": 2026,
                        "tipo_registro": "RGNR",
                        "fase": "INDAGINI_PRELIMINARI",
                        "stato": "PENDENTE",
                        "reato": "Procedimento penale demo",
                        "sezione": "GIP",
                        "giudice": "Dott. Bianchi",
                        "data_iscrizione": "2026-01-10",
                        "data_udienza": "2026-06-20",
                        "imputati": ["Mario Rossi"],
                        "parti_offese": [],
                        "nome_ufficio": "Procura della Repubblica di Palermo",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "12345",
                        "anno": 2026,
                        "ufficio_nome": "Procura della Repubblica di Palermo",
                        "ufficio_codice": "0580010",
                        "procedimento": "RGNR",
                        "stato": "PENDENTE",
                        "oggetto": "Procedimento penale demo",
                        "data_udienza": "2026-06-20",
                    },
                    "parti": ["Mario Rossi"],
                    "controparti": [],
                    "eventi": [],
                    "documenti": [],
                    "depositi": [],
                    "counts": {
                        "parti": 1,
                        "documenti": 0,
                        "depositi": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "provvedimenti": 0,
                    },
                },
                "mapping": {"mode": "create_new"},
                "options": {
                    "importa_parti": True,
                    "importa_documenti": False,
                    "importa_scadenze": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                },
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["created"] is False
    assert data["result"]["auto_integrated"] is True
    assert data["result"]["id_fascicolo"] == fasc_id
    assert data["result"]["workflow_url"]

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    assert len(fascicoli.tutti()) == 1
    fascicolo = fascicoli.get(fasc_id)
    assert fascicolo is not None
    assert fascicolo.source == "PDP"

    repo = PDPPenaleWorkflowRepository(cfg["PDP_PENALE_DB"])
    try:
        cases = repo.list_cases_for_practice(fasc_id)
        assert len(cases) == 1
        assert cases[0]["register_number"] == "12345"
    finally:
        repo.close()


def test_route_importa_pdp_riusa_fascicolo_esistente_senza_duplicarlo(tmp_path: Path, monkeypatch):
    cfg = _cfg_web(tmp_path)
    fasc_id, _ = _seed_penal_workspace(cfg)

    import pct.pdp as pdp_module

    def _client_non_atteso(*args, **kwargs):
        raise AssertionError("L'import diretto PDP non deve creare un nuovo fascicolo se esiste già.")

    monkeypatch.setattr(pdp_module, "crea_client_pdp", _client_non_atteso)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-penale", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        response = client.post(
            "/pdp/importa",
            data={
                "demo_mode": "1",
                "numero_rg": "12345",
                "anno_rg": "2026",
                "tipo_registro": "RGNR",
                "fase": "INDAGINI_PRELIMINARI",
                "stato": "PENDENTE",
                "reato": "Procedimento penale demo",
                "sezione": "GIP",
                "giudice": "Dott. Bianchi",
                "data_iscrizione": "2026-01-10",
                "data_udienza": "2026-06-20",
                "imputati_json": '["Mario Rossi"]',
                "parti_offese_json": "[]",
                "codice_ufficio": "",
                "nome_ufficio": "Procura della Repubblica di Palermo",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert f"/fascicoli/{fasc_id}" in response.headers["Location"]

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    assert len(fascicoli.tutti()) == 1

    repo = PDPPenaleWorkflowRepository(cfg["PDP_PENALE_DB"])
    try:
        assert len(repo.list_cases_for_practice(fasc_id)) == 1
    finally:
        repo.close()
