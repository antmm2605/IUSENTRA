import sqlite3
from pathlib import Path

from pct.telematico_workflow import TelematicoWorkflowRepository


def test_telematico_repository_upsert_case_documenti_e_task(tmp_path: Path):
    repo = TelematicoWorkflowRepository(str(tmp_path / "workflow.db"))
    try:
        case = repo.upsert_case(
            practice_id="FASC-001",
            channel_family="ministero",
            service_code="pdp_penale",
            office_name="Procura della Repubblica di Palermo",
            register_type="RGNR",
            register_number="12345",
            register_year=2026,
            subject_name="Mario Rossi",
            counsel_name="Avv. Roberto Montagnese",
            counsel_cf="MNTRRT00A00G273X",
            portal_case_ref="PDP:12345:2026",
            internal_status="download_available",
            native_status="IN_VERIFICA",
        )
        updated = repo.upsert_case(
            practice_id="FASC-001",
            channel_family="ministero",
            service_code="pdp_penale",
            office_name="Procura della Repubblica di Palermo",
            register_type="RGNR",
            register_number="12345",
            register_year=2026,
            subject_name="Mario Rossi",
            counsel_name="Avv. Roberto Montagnese",
            counsel_cf="MNTRRT00A00G273X",
            portal_case_ref="PDP:12345:2026",
            internal_status="import_completed",
            native_status="ACCETTATO",
            workflow_url="/fascicoli/FASC-001/penale/pdp",
        )

        assert case["id"] == updated["id"]
        assert updated["internal_status"] == "import_completed"

        tx = repo.upsert_transmission(
            str(updated["id"]),
            transmission_type="case_import",
            act_type="Richiesta accesso atti",
            portal_reference="DEP-001",
            internal_status="accepted",
        )
        doc = repo.upsert_document(
            str(updated["id"]),
            document_role="main_act",
            title="richiesta_accesso.pdf.p7m",
            original_filename="richiesta_accesso.pdf.p7m",
            source_type="portal",
            portal_document_ref="DOC-001",
            id_deposito="DEP-001",
            tipo_atto="Richiesta accesso atti",
            data_deposito="2026-04-12",
            mittente="Avv. Roberto Montagnese",
            signed=1,
        )
        repo.link_document_to_transmission(str(tx["id"]), str(doc["id"]), relation_type="main_act")
        task = repo.ensure_task(
            str(updated["id"]),
            task_type="download_case_file",
            title="Scaricare il fascicolo",
            priority="urgent",
        )

        cases = repo.list_cases(practice_id="FASC-001")
        stats = repo.case_stats()

        assert len(cases) == 1
        assert cases[0]["documents_count"] == 1
        assert cases[0]["open_tasks_count"] == 1
        assert stats["totale"] == 1
        assert stats["per_service"]["pdp_penale"]["import_completed"] == 1
        assert task["task_type"] == "download_case_file"
        assert doc["id_deposito"] == "DEP-001"
        assert doc["tipo_atto"] == "Richiesta accesso atti"
    finally:
        repo.close()


def test_telematico_repository_recent_events(tmp_path: Path):
    repo = TelematicoWorkflowRepository(str(tmp_path / "workflow.db"))
    try:
        case = repo.upsert_case(
            practice_id="FASC-002",
            channel_family="amministrativo",
            service_code="pat_siga",
            office_name="TAR Lazio",
            register_type="RICORSO",
            register_number="876",
            register_year=2026,
            subject_name="Alfa S.r.l.",
            counsel_name="Avv. Demo",
            counsel_cf="DMEAVV00A00H501Z",
        )
        repo.add_event(
            str(case["id"]),
            event_type="telematico_sync",
            title="PAT sincronizzato",
            event_source="import",
            description="Allineamento iniziale dal portale amministrativo.",
            payload_json={"imported_documents": 3},
        )

        events = repo.list_recent_events(limit=5)

        assert len(events) == 1
        assert events[0]["service_code"] == "pat_siga"
        assert "PAT sincronizzato" in events[0]["title"]
    finally:
        repo.close()


def test_telematico_repository_filtra_pratiche_esistenti_e_cancella_collegamento(tmp_path: Path):
    repo = TelematicoWorkflowRepository(str(tmp_path / "workflow.db"))
    try:
        valid = repo.upsert_case(
            practice_id="FASC-VALIDO",
            channel_family="ministero",
            service_code="polisweb_consultazione",
            office_name="Tribunale di Torino",
            register_type="CC",
            register_number="3950",
            register_year=2026,
            subject_name="Parte valida",
            counsel_name="Avv. Demo",
            counsel_cf="DMEAVV00A00H501Z",
        )
        orphan = repo.upsert_case(
            practice_id="FASC-ELIMINATO",
            channel_family="ministero",
            service_code="polisweb_consultazione",
            office_name="Tribunale di Torino",
            register_type="CC",
            register_number="3951",
            register_year=2026,
            subject_name="Parte eliminata",
            counsel_name="Avv. Demo",
            counsel_cf="DMEAVV00A00H501Z",
        )
        repo.add_event(str(valid["id"]), event_type="sync", title="Evento valido")
        repo.add_event(str(orphan["id"]), event_type="sync", title="Evento orfano")
        repo.upsert_document(
            str(orphan["id"]),
            document_role="other",
            title="Catalogo senza file",
            source_type="portal",
            portal_document_ref="DOC-ORFANO",
        )
        repo.conn.execute(
            """
            INSERT INTO telematic_pec_messages
                (id, telematic_case_id, mailbox, subject)
            VALUES (?, ?, ?, ?)
            """,
            ("pec-preservata", orphan["id"], "studio@pec.example", "Comunicazione conservata"),
        )
        repo.conn.commit()

        assert [row["practice_id"] for row in repo.list_cases(practice_ids={"FASC-VALIDO"})] == ["FASC-VALIDO"]
        assert repo.case_stats(practice_ids={"FASC-VALIDO"})["totale"] == 1
        assert [row["title"] for row in repo.list_recent_events(practice_ids={"FASC-VALIDO"})] == ["Evento valido"]

        assert repo.delete_cases_for_practice("FASC-ELIMINATO") == 1
        assert repo.delete_cases_for_practice("FASC-ELIMINATO") == 0
        assert repo.get_case(str(orphan["id"])) is None
        assert repo.conn.execute(
            "SELECT COUNT(*) FROM telematic_documents WHERE telematic_case_id = ?",
            (orphan["id"],),
        ).fetchone()[0] == 0
        pec_row = repo.conn.execute(
            "SELECT telematic_case_id FROM telematic_pec_messages WHERE id = ?",
            ("pec-preservata",),
        ).fetchone()
        assert pec_row is not None
        assert pec_row[0] is None
    finally:
        repo.close()


def test_telematico_repository_recupera_errore_sqlite_spazio_temporaneo(tmp_path: Path, monkeypatch):
    repo = TelematicoWorkflowRepository(str(tmp_path / "workflow.db"))
    try:
        repo.upsert_case(
            practice_id="FASC-003",
            channel_family="ministero",
            service_code="pdp_penale",
            office_name="Procura della Repubblica di Palermo",
            register_type="RGNR",
            register_number="444",
            register_year=2026,
            subject_name="Mario Rossi",
            counsel_name="Avv. Roberto Montagnese",
            counsel_cf="MNTRRT00A00G273X",
            portal_case_ref="PDP:444:2026",
            internal_status="import_completed",
        )

        original_execute = repo._execute_raw
        state = {"failed_once": False}

        def flaky_execute(sql, params=()):
            if "v_telematic_case_overview" in sql and not state["failed_once"]:
                state["failed_once"] = True
                raise sqlite3.OperationalError("database or disk is full")
            return original_execute(sql, params)

        monkeypatch.setattr(repo, "_execute_raw", flaky_execute)

        rows = repo.list_cases(practice_id="FASC-003")

        assert len(rows) == 1
        assert rows[0]["practice_id"] == "FASC-003"
        assert state["failed_once"] is True
    finally:
        repo.close()
