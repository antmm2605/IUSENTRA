"""Tool Lex per Documenti AI Fascicolo.

I tool non leggono file direttamente: passano sempre dal service del dominio
Documenti AI, che applica tenant, permessi e audit.
"""

from __future__ import annotations

from typing import Any

from pct.document_intelligence.security import DocumentAIValidationError

from .base import BaseLexTool


def _runtime_service():
    from web.blueprints.api_v1_documenti_ai import build_document_ai_service

    return build_document_ai_service()


def _runtime_tenant_id() -> str:
    from web.blueprints.api_v1_documenti_ai import _tenant_id

    return _tenant_id()


def _runtime_user_context() -> dict[str, Any]:
    from web.blueprints.api_v1_documenti_ai import _user_context

    return _user_context()


def list_fascicolo_documents(
    fascicolo_id: str,
    *,
    service: Any = None,
    tenant_id: str | None = None,
    user_context: object | None = None,
) -> dict[str, Any]:
    svc = service or _runtime_service()
    tenant = tenant_id or _runtime_tenant_id()
    context = user_context if user_context is not None else _runtime_user_context()
    documents = svc.list_fascicolo_documents(tenant, fascicolo_id, context)
    ready_documents = [document for document in documents if str(document.status or "").lower() == "ready"]
    return {
        "documents": [
            {
                "document_id": document.id,
                "filename": document.original_filename,
                "file_type": document.file_type,
                "status": document.status,
                "page_count": document.page_count,
                "sha256": document.sha256,
            }
            for document in ready_documents
        ],
        "not_ready_count": max(0, len(documents) - len(ready_documents)),
    }


def read_fascicolo_document(
    fascicolo_id: str,
    document_id: str,
    *,
    service: Any = None,
    tenant_id: str | None = None,
    user_context: object | None = None,
) -> dict[str, Any]:
    svc = service or _runtime_service()
    tenant = tenant_id or _runtime_tenant_id()
    context = user_context if user_context is not None else _runtime_user_context()
    document = svc.get_fascicolo_document(tenant, fascicolo_id, document_id, context)
    if str(document.status or "").lower() != "ready":
        raise DocumentAIValidationError("Documento non indicizzato o non pronto per Lex.")
    text = svc.get_fascicolo_document_text(tenant, fascicolo_id, document_id, context)
    return {
        "document_id": document.id,
        "filename": document.original_filename,
        "version_id": text.version_id,
        "sha256": document.sha256,
        "text": text.text,
        "pages": [page.to_dict() for page in text.pages],
    }


def find_in_fascicolo_document(
    fascicolo_id: str,
    document_id: str,
    query: str,
    max_results: int = 20,
    *,
    service: Any = None,
    tenant_id: str | None = None,
    user_context: object | None = None,
) -> dict[str, Any]:
    svc = service or _runtime_service()
    tenant = tenant_id or _runtime_tenant_id()
    context = user_context if user_context is not None else _runtime_user_context()
    document = svc.get_fascicolo_document(tenant, fascicolo_id, document_id, context)
    if str(document.status or "").lower() != "ready":
        raise DocumentAIValidationError("Documento non indicizzato o non pronto per Lex.")
    results = svc.search_fascicolo_document(tenant, fascicolo_id, document_id, query, context, max_results=max_results)
    return {
        "document_id": document_id,
        "query": query,
        "results": [
            {
                "page_number": result.page_number,
                "snippet": result.snippet,
            }
            for result in results
        ],
    }


class ListFascicoloDocumentsTool(BaseLexTool):
    tool_name = "list_fascicolo_documents"

    def run(self, **kwargs):
        return list_fascicolo_documents(str(kwargs.get("fascicolo_id") or ""))


class ReadFascicoloDocumentTool(BaseLexTool):
    tool_name = "read_fascicolo_document"

    def run(self, **kwargs):
        return read_fascicolo_document(
            str(kwargs.get("fascicolo_id") or ""),
            str(kwargs.get("document_id") or ""),
        )


class FindInFascicoloDocumentTool(BaseLexTool):
    tool_name = "find_in_fascicolo_document"

    def run(self, **kwargs):
        return find_in_fascicolo_document(
            str(kwargs.get("fascicolo_id") or ""),
            str(kwargs.get("document_id") or ""),
            str(kwargs.get("query") or ""),
            int(kwargs.get("max_results") or 20),
        )
