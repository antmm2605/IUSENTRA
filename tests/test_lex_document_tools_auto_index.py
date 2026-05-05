from dataclasses import dataclass
from pathlib import Path

import pytest

from lex.retrieval.documenti import search_document_sources
from lex.tools import fascicolo_documents
from pct.document_intelligence.models import (
    DocumentAIPageText,
    DocumentAIRecord,
    DocumentAIText,
    utc_now,
)
from pct.document_intelligence.security import DocumentAIValidationError


@dataclass
class FakeIndexService:
    calls: list

    def list_fascicolo_documents(self, tenant_id, fascicolo_id, user_context):
        self.calls.append(("list", tenant_id, fascicolo_id, user_context))
        return [
            _record(id="doc-ready", status="ready", original_filename="atto.pdf"),
            _record(id="doc-error", status="error", original_filename="bozza.pdf"),
        ]

    def get_fascicolo_document(self, tenant_id, fascicolo_id, document_id, user_context):
        self.calls.append(("get", tenant_id, fascicolo_id, document_id, user_context))
        status = "ready" if document_id == "doc-ready" else "error"
        return _record(id=document_id, status=status)

    def get_fascicolo_document_text(self, tenant_id, fascicolo_id, document_id, user_context):
        self.calls.append(("text", tenant_id, fascicolo_id, document_id, user_context))
        return DocumentAIText(
            document_id=document_id,
            version_id="ver-1",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            text="Clausola risolutiva e testo indicizzato.",
            pages=[DocumentAIPageText(page_number=1, text="Clausola risolutiva e testo indicizzato.")],
            extraction_engine="test-index",
            created_at=utc_now(),
        )

    def search_fascicolo_document(self, tenant_id, fascicolo_id, document_id, query, user_context, max_results=20):
        self.calls.append(("search", tenant_id, fascicolo_id, document_id, query, max_results))
        return []


def _record(**overrides):
    payload = {
        "id": "doc-ready",
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


def test_tool_list_mostra_solo_documenti_ready_e_count_non_pronti():
    service = FakeIndexService([])

    payload = fascicolo_documents.list_fascicolo_documents(
        "fas-1",
        service=service,
        tenant_id="tenant-a",
        user_context={"user_id": "lex"},
    )

    assert [item["document_id"] for item in payload["documents"]] == ["doc-ready"]
    assert payload["not_ready_count"] == 1


def test_tool_read_rifiuta_documento_non_ready():
    service = FakeIndexService([])

    with pytest.raises(DocumentAIValidationError):
        fascicolo_documents.read_fascicolo_document(
            "fas-1",
            "doc-error",
            service=service,
            tenant_id="tenant-a",
            user_context={"user_id": "lex"},
        )


def test_retrieval_documenti_usa_indice_automatico_senza_filesystem():
    service = FakeIndexService([])

    items = search_document_sources(
        "fas-1",
        "clausola",
        {
            "document_ai_service": service,
            "document_ai_tenant_id": "tenant-a",
            "document_ai_user_context": {"user_id": "lex"},
        },
    )

    assert any(item.source_type == "documento_indicizzato" for item in items)
    assert any(item.source_type == "documento_indice_stato" for item in items)
    assert "Clausola risolutiva" in " ".join(item.content for item in items)
    assert not any(call[0] == "filesystem" for call in service.calls)


def test_tool_non_legge_file_direttamente():
    source = Path("lex/tools/fascicolo_documents.py").read_text(encoding="utf-8")

    assert "read_text(" not in source
    assert "read_bytes(" not in source
    assert "open(" not in source
    assert "Path(" not in source
