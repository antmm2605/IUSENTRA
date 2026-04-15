"""Use case di supporto redazione atti per Lex."""

from __future__ import annotations


class DraftActSupportUseCase:
    def execute(self, service, request):
        request.intent = "draft_act_support"
        return service.ask(request)
