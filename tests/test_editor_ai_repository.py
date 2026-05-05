from __future__ import annotations

import pytest

from pct.editor_ai.models import AttoAIEditProposal, AttoAIRecord, AttoAIVersion, utc_now
from pct.editor_ai.repository import EditorAIRepository
from pct.editor_ai.validators import EditorAIValidationError


def _record(record_id: str, tenant_id: str = "tenant-a", fascicolo_id: str = "fas-1") -> AttoAIRecord:
    now = utc_now()
    return AttoAIRecord(
        id=record_id,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        tipo_atto="Comparsa",
        template_id="comparsa",
        title="Comparsa",
        status="draft",
        editor_document_id=f"doc-{record_id}",
        current_version_id=None,
        created_by="operatore",
        created_at=now,
        updated_at=now,
    )


def _version(record: AttoAIRecord, number: int = 1) -> AttoAIVersion:
    return AttoAIVersion(
        id=f"ver-{record.id}-{number}",
        atto_ai_id=record.id,
        tenant_id=record.tenant_id,
        fascicolo_id=record.fascicolo_id,
        version_number=number,
        source="ai_generation",
        editor_document_snapshot={"text": "snapshot"},
        docx_path=None,
        pdf_path=None,
        created_by="operatore",
        created_at=utc_now(),
    )


def test_repository_sqlite_filtra_tenant_fascicolo_e_versiona(tmp_path):
    repo = EditorAIRepository.from_sqlite_db(tmp_path / "editor_ai.sqlite")
    record = repo.create_record(_record("atto-1"))
    repo.create_record(_record("atto-2", tenant_id="tenant-b"))
    repo.create_version(_version(record))
    record.current_version_id = "ver-atto-1-1"
    repo.update_record(record)

    assert [item.id for item in repo.list_records("tenant-a", "fas-1")] == ["atto-1"]
    assert repo.get_record("tenant-b", "fas-1", "atto-1") is None
    assert repo.get_record_by_editor_document("tenant-a", "fas-1", "doc-atto-1").id == "atto-1"
    assert repo.list_versions("tenant-a", "fas-1", "atto-1")[0].version_number == 1

    with pytest.raises(EditorAIValidationError):
        repo.create_version(_version(record))

    repo.close()


def test_repository_sqlite_modifiche_e_audit(tmp_path):
    repo = EditorAIRepository.from_sqlite_db(tmp_path / "editor_ai.sqlite")
    record = repo.create_record(_record("atto-1"))
    proposal = AttoAIEditProposal(
        id="edit-1",
        atto_ai_id=record.id,
        version_id="ver-1",
        status="pending",
        operation_type="add_section",
        target_block_id=None,
        find_text=None,
        replace_text=None,
        insert_text="<p>Nuova sezione</p>",
        reason="Richiesta utente.",
        created_by="operatore",
        created_at=utc_now(),
    )
    repo.create_edit_proposal(proposal)
    proposal.status = "rejected"
    repo.update_edit_proposal(proposal)
    repo.append_audit_event(
        {
            "id": "audit-1",
            "tenant_id": "tenant-a",
            "fascicolo_id": "fas-1",
            "atto_ai_id": "atto-1",
            "user_id": "operatore",
            "event_type": "editor_ai.test",
            "html": "<p>non loggare</p>",
        }
    )

    assert repo.list_edit_proposals("atto-1")[0].status == "rejected"
    repo.close()
