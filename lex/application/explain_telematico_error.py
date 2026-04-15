"""Use case di spiegazione errore telematico per Lex."""

from __future__ import annotations


class ExplainTelematicoErrorUseCase:
    def execute(self, service, request):
        request.intent = "explain_telematico_error"
        return service.ask(request)
