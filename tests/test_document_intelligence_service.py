from dataclasses import dataclass
from pathlib import Path

import pytest

from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.models import DocumentAIPageText
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.security import DocumentAINotFound, DocumentAIPermissionDenied, DocumentAIValidationError
from pct.document_intelligence.service import DocumentAIService


@dataclass
class FakeUser:
    id: str = "user-1"
    can_read: bool = True
    can_write: bool = True

    def ha_permesso(self, permission: str) -> bool:
        if permission == "fascicoli.leggi":
            return self.can_read
        if permission == "fascicoli.scrivi":
            return self.can_write
        return False


class FakeFascicoli:
    def get(self, fascicolo_id: str):
        return {"id": fascicolo_id} if fascicolo_id == "fas-1" else None


class FakeUpload:
    filename = "atto.docx"
    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def __init__(self, content: bytes = b"documento"):
        self._content = content

    def read(self):
        return self._content

    def seek(self, _index: int):
        return None


def _service(tmp_path: Path) -> DocumentAIService:
    repo = DocumentAIRepository(tmp_path / "documenti_ai.json", tmp_path / "storage")
    return DocumentAIService(repo, FakeFascicoli())


def _context(user: FakeUser | None = None):
    return {"user": user or FakeUser(), "user_id": "user-1"}


def test_document_ai_service_upload_successo_crea_record_versione_testo_audit(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(
        "pct.document_intelligence.service.extract_text_from_document",
        lambda *_args: ExtractionResult(
            ok=True,
            text="Testo estratto dal documento",
            pages=[DocumentAIPageText(page_number=1, text="Testo estratto dal documento")],
            extraction_engine="test-engine",
        ),
    )

    result = service.upload_document_for_fascicolo("tenant-a", "fas-1", FakeUpload(), _context())
    record = result.document

    assert record.status == "ready"
    assert record.current_version_id
    assert result.version.version_number == 1
    assert result.text is not None
    assert result.extraction_status == "completed"
    assert record.sha256
    assert service.repository.get_extracted_text("tenant-a", "fas-1", record.id) is not None
    assert any(event["event_type"] == "document_ai.upload.completed" for event in service.repository._data["audit_events"])
    assert any(event["event_type"] == "document_ai.version.created" for event in service.repository._data["audit_events"])


def test_document_ai_service_upload_fallimento_estrazione_conserva_originale(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(
        "pct.document_intelligence.service.extract_text_from_document",
        lambda *_args: ExtractionResult(
            ok=False,
            text="",
            pages=[],
            extraction_engine="test-failed",
            error_code="boom",
            error_message="Errore controllato",
        ),
    )

    result = service.upload_document_for_fascicolo("tenant-a", "fas-1", FakeUpload(b"contenuto"), _context())
    record = result.document

    assert record.status == "error"
    assert record.current_version_id
    assert result.text is None
    assert result.extraction_status == "failed"
    stored_files = list((tmp_path / "storage").rglob("*.docx"))
    assert stored_files, "Il file originale deve restare su storage tenant-aware"
    assert service.repository.get_extracted_text("tenant-a", "fas-1", record.id) is None
    assert any(event["event_type"] == "document_ai.upload.failed" for event in service.repository._data["audit_events"])
    assert any(event["event_type"] == "document_ai.extraction.failed" for event in service.repository._data["audit_events"])


def test_document_ai_service_permesso_scrittura_obbligatorio(tmp_path: Path):
    service = _service(tmp_path)
    with pytest.raises(DocumentAIPermissionDenied):
        service.upload_document_for_fascicolo("tenant-a", "fas-1", FakeUpload(), _context(FakeUser(can_write=False)))


def test_document_ai_service_ricerca_registra_audit(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(
        "pct.document_intelligence.service.extract_text_from_document",
        lambda *_args: ExtractionResult(
            ok=True,
            text="Una clausola importante.",
            pages=[],
            extraction_engine="test-engine",
        ),
    )
    record = service.upload_document_for_fascicolo("tenant-a", "fas-1", FakeUpload(), _context()).document

    results = service.search_fascicolo_document("tenant-a", "fas-1", record.id, "clausola", _context())

    assert results
    assert any(event["event_type"] == "document_ai.search" for event in service.repository._data["audit_events"])


def test_document_ai_service_query_vuota_fallisce(tmp_path: Path):
    service = _service(tmp_path)

    with pytest.raises(DocumentAIValidationError):
        service.search_fascicolo_document("tenant-a", "fas-1", "doc-missing", " ", _context())


def test_document_ai_service_get_documento_inesistente_fallisce(tmp_path: Path):
    service = _service(tmp_path)

    with pytest.raises(DocumentAINotFound):
        service.get_fascicolo_document("tenant-a", "fas-1", "doc-missing", _context())


def test_document_ai_service_list_filtra_tenant_fascicolo(tmp_path: Path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(
        "pct.document_intelligence.service.extract_text_from_document",
        lambda *_args: ExtractionResult(ok=True, text="Documento", pages=[], extraction_engine="test-engine"),
    )
    service.upload_document_for_fascicolo("tenant-a", "fas-1", FakeUpload(), _context())

    assert len(service.list_fascicolo_documents("tenant-a", "fas-1", _context())) == 1
    assert service.repository.list_documents("tenant-a", "fas-2") == []
