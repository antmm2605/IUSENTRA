from pathlib import Path

import pytest

from pct.document_intelligence.models import DocumentAIPageText, DocumentAIRecord, DocumentAIText, DocumentAIVersion, utc_now
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.security import DocumentAIValidationError


def _repo(tmp_path: Path) -> DocumentAIRepository:
    return DocumentAIRepository(tmp_path / "documenti_ai.json", tmp_path / "storage")


def _record(**overrides) -> DocumentAIRecord:
    payload = {
        "id": "doc-1",
        "tenant_id": "tenant-a",
        "fascicolo_id": "fas-1",
        "original_filename": "atto.pdf",
        "safe_filename": "atto.pdf",
        "file_type": "pdf",
        "mime_type": "application/pdf",
        "size_bytes": 10,
        "sha256": "a" * 64,
        "status": "ready",
        "current_version_id": None,
        "page_count": None,
        "created_by": "user",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    payload.update(overrides)
    return DocumentAIRecord(**payload)


def _version(document_id: str = "doc-1", version_number: int = 1) -> DocumentAIVersion:
    return DocumentAIVersion(
        id=f"ver-{version_number}",
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        document_id=document_id,
        version_number=version_number,
        source="upload",
        storage_path="tenant-a/fas-1/doc-1/file.pdf",
        extracted_text_path=None,
        pdf_preview_path=None,
        sha256="a" * 64,
        created_by="user",
        created_at=utc_now(),
    )


def test_document_ai_repository_filtra_tenant_e_fascicolo(tmp_path: Path):
    repo = _repo(tmp_path)
    repo.create_document_record(_record())
    repo.create_document_record(_record(id="doc-2", tenant_id="tenant-b"))
    repo.create_document_record(_record(id="doc-3", fascicolo_id="fas-2"))

    assert [doc.id for doc in repo.list_documents("tenant-a", "fas-1")] == ["doc-1"]
    assert repo.get_document("tenant-b", "fas-1", "doc-1") is None


def test_document_ai_repository_search_non_esce_dal_fascicolo(tmp_path: Path):
    repo = _repo(tmp_path)
    repo.create_document_record(_record())
    version = repo.create_version(_version())
    repo.set_current_version("tenant-a", "fas-1", "doc-1", version.id, status="ready", page_count=1)
    repo.save_extracted_text(
        DocumentAIText(
            document_id="doc-1",
            version_id=version.id,
            tenant_id="tenant-a",
            fascicolo_id="fas-1",
            text="Il contratto contiene una clausola risolutiva.",
            pages=[DocumentAIPageText(page_number=1, text="Il contratto contiene una clausola risolutiva.")],
            extraction_engine="test",
            created_at=utc_now(),
        )
    )

    assert repo.search_extracted_text("tenant-a", "fas-1", "doc-1", "clausola")
    assert repo.search_extracted_text("tenant-a", "fas-2", "doc-1", "clausola") == []


def test_document_ai_repository_version_number_univoco(tmp_path: Path):
    repo = _repo(tmp_path)
    repo.create_document_record(_record())
    repo.create_version(_version())
    with pytest.raises(DocumentAIValidationError):
        repo.create_version(_version())


def test_document_ai_repository_current_version_aggiornato(tmp_path: Path):
    repo = _repo(tmp_path)
    repo.create_document_record(_record(status="processing"))
    version = repo.create_version(_version())
    repo.set_current_version("tenant-a", "fas-1", "doc-1", version.id, status="ready", page_count=3)

    document = repo.get_document("tenant-a", "fas-1", "doc-1")
    assert document is not None
    assert document.current_version_id == version.id
    assert document.status == "ready"
    assert document.page_count == 3
