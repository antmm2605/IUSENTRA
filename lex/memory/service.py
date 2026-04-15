"""Servizio memoria del bounded context Lex."""

from __future__ import annotations


class LexMemoryService:
    def __init__(self) -> None:
        self.session = {}
        self.case = {}

    def persist(self, request, workflow, context, response):
        self.session[request.session_id] = {
            "last_query": request.query,
            "last_answer": response.answer,
            "workflow": workflow,
        }

        if request.fascicolo_id:
            self.case[request.fascicolo_id] = {
                "last_query": request.query,
                "last_answer": response.answer,
            }
