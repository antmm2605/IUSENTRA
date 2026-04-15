"""Use case di analisi documento per Lex."""

from __future__ import annotations


class AnalyzeDocumentUseCase:
    def execute(self, service, request):
        request.intent = "analyze_document"
        return service.ask(request)
