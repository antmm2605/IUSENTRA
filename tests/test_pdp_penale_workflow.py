from __future__ import annotations

import sqlite3
from pathlib import Path

from pct.database import SCHEMA_SQL
from pct.pdp_penale_workflow import PDPPenaleWorkflowRepository
from pct.storage import StudioDB


def test_schema_unificato_include_modulo_pdp_penale(tmp_path: Path):
    db_path = tmp_path / "studio.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    views = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()
    }
    conn.close()

    assert "criminal_cases" in tables
    assert "criminal_case_events" in tables
    assert "criminal_case_documents" in tables
    assert "criminal_access_requests" in tables
    assert "criminal_workflow_tasks" in tables
    assert "criminal_access_request_documents" in tables
    assert "pec_messages" in tables
    assert "v_criminal_case_overview" in views


def test_repository_pdp_penale_gestisce_crud_principale(tmp_path: Path):
    repo = PDPPenaleWorkflowRepository(str(tmp_path / "pdp_penale.db"))
    case = repo.create_case(
        practice_id="FASC-001",
        office_name="Procura della Repubblica di Palermo",
        office_type="Procura",
        district="Palermo",
        register_type="RGNR",
        register_number="12345",
        register_year=2026,
        proceeding_type="indagini_preliminari",
        assisted_party_name="Mario Rossi",
        assisted_party_cf="RSSMRA80A01H501Z",
        defense_counsel_name="Avv. Roberto Montagnese",
        defense_counsel_cf="MNTRRT00A00G273X",
        nomination_status="deposited",
        access_status="submitted",
    )

    assert case["practice_id"] == "FASC-001"
    assert case["access_status"] == "submitted"

    case = repo.update_case(
        str(case["id"]),
        nomination_status="accepted",
        current_ministry_status="INVIATO",
        notes="Richiesta accesso preparata e inviata.",
    )
    assert case["nomination_status"] == "accepted"
    assert case["current_ministry_status"] == "INVIATO"

    event = repo.add_event(
        str(case["id"]),
        event_type="access_request_submitted",
        event_source="user",
        title="Richiesta accesso inviata",
        payload_json={"channel": "PDP", "status": "INVIATO"},
    )
    assert event["event_type"] == "access_request_submitted"
    assert '"status": "INVIATO"' in (event["payload_json"] or "")

    document = repo.add_document(
        str(case["id"]),
        document_role="nomination",
        title="Nomina difensore",
        original_filename="nomina.pdf.p7m",
        file_path="/data/fascicoli/FASC-001/nomina.pdf.p7m",
        source_type="manual",
        signed=True,
        verified=True,
    )
    assert document["document_role"] == "nomination"
    assert int(document["signed"]) == 1

    access_request = repo.create_access_request(
        str(case["id"]),
        request_status="submitted",
        ministry_status="INVIATO",
        payment_required=True,
        payment_amount=16.0,
    )
    assert access_request["request_status"] == "submitted"
    assert int(access_request["payment_required"]) == 1

    link = repo.link_document_to_access_request(
        str(access_request["id"]),
        str(document["id"]),
        relation_type="attachment",
    )
    assert link["relation_type"] == "attachment"

    pec = repo.register_pec_message(
        criminal_case_id=str(case["id"]),
        mailbox="difensore@pec.example.it",
        subject="Password accesso fascicolo",
        sender="procura@giustiziapec.it",
        extracted_password="PDP-ABC-123",
        contains_download_notice=True,
    )
    assert int(pec["contains_password"]) == 1

    updated_case = repo.get_case(str(case["id"]))
    assert int(updated_case["pec_password_received"]) == 1

    task = repo.create_task(
        str(case["id"]),
        task_type="download_case_file",
        title="Scaricare fascicolo entro 3 giorni",
        priority="urgent",
    )
    closed_task = repo.close_task(str(task["id"]), completion_note="Download eseguito dall'operatore.")
    assert closed_task["status"] == "done"
    assert closed_task["completed_at"]
    assert "Download eseguito" in (closed_task["description"] or "")

    overview = repo.list_overview_for_practice("FASC-001")
    assert len(overview) == 1
    assert int(overview[0]["documents_count"]) == 1
    assert int(overview[0]["open_tasks_count"]) == 0

    assert len(repo.list_case_events(str(case["id"]))) == 1
    assert len(repo.list_case_documents(str(case["id"]))) == 1
    assert len(repo.list_access_requests(str(case["id"]))) == 1
    assert len(repo.list_pec_messages(str(case["id"]))) == 1

    repo.close()


def test_repository_pdp_penale_funziona_con_studiodb(tmp_path: Path):
    studio_db = StudioDB.get(str(tmp_path / "tenant" / "studio.db"))
    repo = PDPPenaleWorkflowRepository(studio_db)

    case = repo.create_case(
        practice_id="FASC-JSON-01",
        office_name="Procura della Repubblica di Catanzaro",
        register_type="RGNR",
        register_number="7788",
        register_year=2025,
        assisted_party_name="Luigi Verdi",
        defense_counsel_name="Avv. Giulia Neri",
        defense_counsel_cf="NREGLI80A01H501Z",
    )

    loaded = repo.get_case(str(case["id"]))
    assert loaded["office_name"] == "Procura della Repubblica di Catanzaro"
    assert loaded["practice_id"] == "FASC-JSON-01"

