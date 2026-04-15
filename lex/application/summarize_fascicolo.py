"""Use case di sintesi fascicolo per Lex."""

from __future__ import annotations


class SummarizeFascicoloUseCase:
    def execute(self, service, request):
        request.intent = "summarize_fascicolo"
        return service.ask(request)
