"""Use case di confronto documenti per Lex."""

from __future__ import annotations


class CompareDocumentsUseCase:
    def execute(self, service, request):
        request.intent = "compare_documents"
        return service.ask(request)
