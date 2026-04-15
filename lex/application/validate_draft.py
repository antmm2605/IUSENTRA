"""Use case di validazione bozza per Lex."""

from __future__ import annotations


class ValidateDraftUseCase:
    def execute(self, service, request):
        request.intent = "validate_draft"
        return service.ask(request)
