"""Use case di prossima azione per Lex."""

from __future__ import annotations


class SuggestNextActionUseCase:
    def execute(self, service, request):
        request.intent = "suggest_next_action"
        return service.ask(request)
