from dataclasses import dataclass
from pathlib import Path

from pct.document_intelligence.models import DocumentAIPageText, DocumentAIRecord, DocumentAISearchResult, DocumentAIText, utc_now
from lex.tools import fascicolo_documents


@dataclass
class FakeService:
    calls: list

    def list_fascicolo_documents(self, tenant_id, fascicolo_id, user_context):
        self.calls.append(("list", tenant_id, fascicolo_id, user_context))
        return [_record()]

    def get_fascicolo_document(self, tenant_id, fascicolo_id, document_id, user_context):
        self.calls.append(("get", tenant_id, fascicolo_id, document_id, user_context))
        return _record(id=document_id)

    def get_fascicolo_document_text(self, tenant_id, fascicolo_id, document_id, user_context):
        self.calls.append(("text", tenant_id, fascicolo_id, document_id, user_context))
        return DocumentAIText(
            document_id=document_id,
            version_id="ver-1",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            text="Testo del fascicolo",
            pages=[DocumentAIPageText(page_number=1, text="Testo del fascicolo")],
            extraction_engine="test",
            created_at=utc_now(),
        )

    def search_fascicolo_document(self, tenant_id, fascicolo_id, document_id, query, user_context, max_results=20):
        self.calls.append(("search", tenant_id, fascicolo_id, document_id, query, max_results))
        return [
            DocumentAISearchResult(
                document_id=document_id,
                version_id="ver-1",
                page_number=1,
                snippet="Testo del fascicolo",
                start_offset=0,
                end_offset=5,
            )
        ]


def _record(**overrides):
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
        "current_version_id": "ver-1",
        "page_count": 1,
        "created_by": "user",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    payload.update(overrides)
    return DocumentAIRecord(**payload)


def test_lex_tool_list_usa_service():
    service = FakeService([])
    payload = fascicolo_documents.list_fascicolo_documents("fas-1", service=service, tenant_id="tenant-a", user_context={"u": "x"})

    assert payload["documents"][0]["document_id"] == "doc-1"
    assert service.calls[0][:3] == ("list", "tenant-a", "fas-1")


def test_lex_tool_read_usa_service():
    service = FakeService([])
    payload = fascicolo_documents.read_fascicolo_document("fas-1", "doc-1", service=service, tenant_id="tenant-a", user_context={})

    assert payload["text"] == "Testo del fascicolo"
    assert ("text", "tenant-a", "fas-1", "doc-1", {}) in service.calls


def test_lex_tool_find_usa_service():
    service = FakeService([])
    payload = fascicolo_documents.find_in_fascicolo_document(
        "fas-1",
        "doc-1",
        "testo",
        service=service,
        tenant_id="tenant-a",
        user_context={},
    )

    assert payload["results"][0]["page_number"] == 1
    assert service.calls[-1][:5] == ("search", "tenant-a", "fas-1", "doc-1", "testo")


def test_lex_tool_non_legge_file_direttamente():
    source = Path("lex/tools/fascicolo_documents.py").read_text(encoding="utf-8")
    forbidden = ["read_text(", "read_bytes(", "open(", "Path("]
    assert not any(token in source for token in forbidden)
