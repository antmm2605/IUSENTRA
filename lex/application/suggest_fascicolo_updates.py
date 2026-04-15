"""Use case di suggerimento aggiornamenti fascicolo per Lex."""

from __future__ import annotations


class SuggestFascicoloUpdatesUseCase:
    def execute(self, service, request):
        request.intent = "suggest_fascicolo_updates"
        return service.ask(request)
