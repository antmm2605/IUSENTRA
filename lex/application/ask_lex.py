"""Use case di domanda generale a Lex."""

from __future__ import annotations


class AskLexUseCase:
    def execute(self, service, request):
        return service.ask(request)
