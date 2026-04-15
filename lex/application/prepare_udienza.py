"""Use case di preparazione udienza per Lex."""

from __future__ import annotations


class PrepareUdienzaUseCase:
    def execute(self, service, request):
        request.intent = "prepare_udienza"
        return service.ask(request)
