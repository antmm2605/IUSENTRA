from __future__ import annotations

from pct.procedure_lifecycle_repository import diff_dict, stable_event_hash
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

    first = stable_event_hash({"a": 1, "b": {"c": 2}})
    second = stable_event_hash({"b": {"c": 2}, "a": 1})
    assert first == second
    assert diff_dict({"a": 1}, {"a": 2})["changed_fields"] == ["a"]

    event_hash = repo.audit_log(entity_type="unit", entity_id="1", action="created", after={"ok": True})
    rows = repo.list_audit_log("unit", "1")
    assert rows[0]["event_hash"] == event_hash
    assert rows[0]["after_json"] == {"ok": True}
