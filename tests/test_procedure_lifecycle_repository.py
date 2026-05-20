from __future__ import annotations

from pathlib import Path

from pct.procedure_lifecycle_repository import diff_dict, sanitize_audit_payload, stable_event_hash
from tests.procedure_pipeline_support import make_repo


def test_extended_schema_idempotente_crea_tabelle_e_audit(tmp_path):
    repo = make_repo(tmp_path)
    repo.ensure_extended_schema()

    expected = {
        "legal_ministerial_xsd_objects",
        "legal_procedure_xsd_map",
        "legal_procedure_source_evidence",
        "procedure_knowledge_cards",
        "procedure_lifecycle_templates",
        "procedure_lifecycle_steps",
        "fascicolo_workflow_instances",
        "fascicolo_workflow_events",
        "digital_signature_events",
        "telematic_deposit_packages",
        "telematic_deposit_receipts",
        "post_acceptance_obligations",
        "notification_events",
        "evidence_documents",
        "procedure_audit_log",
    }
    for table in expected:
        assert repo.table_exists(table)
        with repo.connect() as conn:
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        assert "tenant_id" in columns

    assert Path("pct/sql/20260520_xsd_procedure_lifecycle_knowledge.sql").exists()

    first = stable_event_hash({"a": 1, "b": {"c": 2}})
    second = stable_event_hash({"b": {"c": 2}, "a": 1})
    assert first == second
    assert diff_dict({"a": 1}, {"a": 2})["changed_fields"] == ["a"]

    event_hash = repo.audit_log(entity_type="unit", entity_id="1", action="created", after={"ok": True})
    rows = repo.list_audit_log("unit", "1")
    assert rows[0]["event_hash"] == event_hash
    assert rows[0]["after_json"] == {"ok": True}


def test_audit_maschera_dati_sensibili_e_path(tmp_path):
    repo = make_repo(tmp_path)
    raw = {
        "email": "mario.rossi@example.test",
        "recipient_tax_code": "RSSMRA80A01H501U",
        "iban": "IT60X0542811101000000123456",
        "storage_path": r"C:\\clienti\\mario\\ricevuta.pdf",
        "password": "segreta",
    }

    safe = sanitize_audit_payload(raw)
    assert "mario.rossi@example.test" not in str(safe)
    assert "RSSMRA80A01H501U" not in str(safe)
    assert "IT60X0542811101000000123456" not in str(safe)
    assert "ricevuta.pdf" not in str(safe)
    assert "segreta" not in str(safe)

    repo.audit_log(entity_type="sensitive", entity_id="1", action="created", after=raw)
    row = repo.list_audit_log("sensitive", "1")[0]
    serialized = str(row["after_json"])
    assert "mario.rossi@example.test" not in serialized
    assert "RSSMRA80A01H501U" not in serialized
    assert "IT60X0542811101000000123456" not in serialized
    assert "ricevuta.pdf" not in serialized
